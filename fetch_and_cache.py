"""
Скрипт для однократной загрузки данных из data.mos.ru и сохранения в кэш-файлы.
После запуска данные хранятся локально — повторные update_data работают мгновенно.

Запуск: py fetch_and_cache.py
Результат: data/cache/stops.json, routes.json, trips.json (по выборке маршрутов)
"""

import asyncio
import json
import os
from pathlib import Path

import httpx

API_KEY = os.getenv("DATAMOS_API_KEY", "d65782bde5d471b24782b170da2ce6f0")
BASE_URL = "https://apidata.mos.ru/v1"
CACHE_DIR = Path("data/cache")

DATASET_STOPS   = 752
DATASET_ROUTES  = 60664
DATASET_TRIPS   = 60665
DATASET_TIMES   = 60661

CONCURRENCY = 5  # параллельных запросов


async def fetch(client: httpx.AsyncClient, dataset_id: int,
                filter_expr: str = "") -> list:
    params = f"?api_key={API_KEY}"
    if filter_expr:
        params += f"&$filter={filter_expr}"
    url = f"{BASE_URL}/datasets/{dataset_id}/rows{params}"
    r = await client.get(url)
    r.raise_for_status()
    return r.json()


async def main():
    if not API_KEY:
        print("Укажи DATAMOS_API_KEY в .env или передай через переменную окружения")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=120.0) as client:

        # 1. Остановки
        stops_file = CACHE_DIR / "stops.json"
        if stops_file.exists():
            print(f"[SKIP] {stops_file} уже есть")
        else:
            print("Загружаю остановки (датасет 752)...")
            stops = await fetch(client, DATASET_STOPS)
            stops_file.write_text(json.dumps(stops, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            print(f"  Сохранено {len(stops)} остановок -> {stops_file}")

        # 2. Маршруты
        routes_file = CACHE_DIR / "routes.json"
        if routes_file.exists():
            print(f"[SKIP] {routes_file} уже есть")
            routes = json.loads(routes_file.read_text(encoding="utf-8"))
        else:
            print("Загружаю маршруты (датасет 60664)...")
            routes = await fetch(client, DATASET_ROUTES)
            routes_file.write_text(json.dumps(routes, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            print(f"  Сохранено {len(routes)} маршрутов -> {routes_file}")

        # 3. Связи маршрут-остановка (через trips + times)
        route_stops_file = CACHE_DIR / "route_stops.json"
        if route_stops_file.exists():
            print(f"[SKIP] {route_stops_file} уже есть")
        else:
            print(f"Загружаю связи для {len(routes)} маршрутов...")
            sem = asyncio.Semaphore(CONCURRENCY)

            async def process_route(route: dict) -> list:
                cells = route.get("Cells", route)
                route_id = str(cells.get("route_id", "")).strip()
                if not route_id:
                    return []
                async with sem:
                    try:
                        trips = await fetch(
                            client, DATASET_TRIPS,
                            f"Cells/route_id eq '{route_id}'"
                        )
                    except Exception as e:
                        print(f"  WARN trips {route_id}: {e}")
                        return []

                # Берём по одному trip_id на direction
                direction_trip: dict[int, str] = {}
                for row in trips:
                    c = row.get("Cells", row)
                    trip_id = str(c.get("trip_id", "")).strip()
                    try:
                        direction = int(c.get("direction_id", 0))
                    except (TypeError, ValueError):
                        direction = 0
                    if trip_id and direction not in direction_trip:
                        direction_trip[direction] = trip_id

                result = []
                for direction, trip_id in direction_trip.items():
                    async with sem:
                        try:
                            times = await fetch(
                                client, DATASET_TIMES,
                                f"Cells/trip_id eq '{trip_id}'"
                            )
                        except Exception as e:
                            print(f"  WARN times {trip_id}: {e}")
                            continue
                    for row in times:
                        c = row.get("Cells", row)
                        try:
                            result.append({
                                "route_id": f"datamos_{route_id}",
                                "stop_id": f"datamos_{int(c['stop_id'])}",
                                "sequence": int(c["stop_sequence"]),
                            })
                        except (KeyError, TypeError, ValueError):
                            continue
                return result

            tasks = [process_route(r) for r in routes]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_rs = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    cells = routes[i].get("Cells", routes[i])
                    print(f"  ERR route {cells.get('route_id')}: {res}")
                else:
                    all_rs.extend(res)

            route_stops_file.write_text(
                json.dumps(all_rs, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"  Сохранено {len(all_rs)} связей -> {route_stops_file}")

    print("\nГотово! Теперь отредактируй .env:")
    print("  USE_CACHE=true")
    print("  CACHE_DIR=data/cache")


if __name__ == "__main__":
    asyncio.run(main())
