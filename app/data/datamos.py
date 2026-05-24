"""
Адаптер для портала открытых данных Правительства Москвы (data.mos.ru).

Датасеты (все через API v1):
  752   — Остановочные пункты (ID, StationName, Latitude_WGS84, Longitude_WGS84, RouteNumbers)
  60664 — Маршруты НГПТ    (route_id, route_short_name, route_type)
  60665 — Рейсы маршрутов  (route_id → trip_id, direction_id)
  60661 — Расписание рейсов (trip_id → stop_id, stop_sequence)

Стратегия загрузки route_stops:
  Для каждого маршрута:
    1. GET /60665?$filter=Cells/route_id eq '{id}' — берём 1 trip_id на направление
    2. GET /60661?$filter=Cells/trip_id eq '{trip_id}' — получаем stop_sequence

  Это позволяет не выгружать датасет 60661 целиком (он содержит миллионы строк).

См. ТЗ Приложение К, п. К.2.
"""

import asyncio
from typing import Dict, List, Optional, Tuple

import httpx

from app.config.settings import get_settings
from app.data.base import DataSource, RouteData, RouteStopData, StopData
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Идентификаторы датасетов ──────────────────────────────────────────────────
DATASET_STOPS_ID  = 752    # Остановочные пункты (v1, старый формат)
DATASET_ROUTES_ID = 60664  # Маршруты НГПТ
DATASET_TRIPS_ID  = 60665  # Рейсы маршрутов
DATASET_TIMES_ID  = 60661  # Расписание рейсов (stop_times)

PAGE_SIZE = 5000

# Одновременных запросов при обходе маршрутов (не перегружаем API)
CONCURRENCY = 5

# GTFS route_type → transport_type
ROUTE_TYPE_MAP: Dict[int, str] = {
    0: "tram",
    1: "metro",
    3: "bus",
    11: "trolleybus",
    800: "trolleybus",
}


class DataMosDataSource(DataSource):
    """Адаптер data.mos.ru — остановки, маршруты и порядок остановок по маршрутам."""

    name = "datamos"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or get_settings().datamos_api_key
        self.base_url = get_settings().datamos_base_url
        if not self.api_key:
            logger.warning("datamos_api_key не задан — запросы будут отклонены API")

    # ── Публичный интерфейс ───────────────────────────────────────────────────

    async def fetch_stops(self) -> List[StopData]:
        """Загрузить остановки из датасета 752."""
        if not self.api_key:
            return []
        raw = await self._fetch_all(DATASET_STOPS_ID)
        stops: List[StopData] = []
        for row in raw:
            cells = row.get("Cells", row)
            stop = _parse_stop(cells)
            if stop:
                stops.append(stop)
        logger.info("Загружено %d остановок из data.mos.ru (датасет %d)",
                    len(stops), DATASET_STOPS_ID)
        return stops

    async def fetch_routes(self) -> List[RouteData]:
        """Загрузить маршруты из датасета 60664."""
        if not self.api_key:
            return []
        raw = await self._fetch_all(DATASET_ROUTES_ID)
        routes: List[RouteData] = []
        seen: set = set()
        for row in raw:
            cells = row.get("Cells", row)
            route = _parse_route(cells)
            if route and route.external_id not in seen:
                seen.add(route.external_id)
                routes.append(route)
        logger.info("Загружено %d маршрутов из data.mos.ru (датасет %d)",
                    len(routes), DATASET_ROUTES_ID)
        return routes

    async def fetch_route_stops(self) -> List[RouteStopData]:
        """
        Загрузить порядок остановок по маршрутам с фильтрацией.

        Для каждого маршрута делаем два отфильтрованных запроса:
          1. /60665?$filter=Cells/route_id eq '{route_id}' — один trip_id на направление
          2. /60661?$filter=Cells/trip_id eq '{trip_id}' — stop_sequence для этого рейса
        """
        if not self.api_key:
            return []

        routes = await self.fetch_routes()
        if not routes:
            return []

        logger.info("Загрузка связей для %d маршрутов...", len(routes))

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def process_route(route: RouteData) -> List[RouteStopData]:
            async with semaphore:
                return await self._fetch_route_stops_for(route)

        tasks = [process_route(r) for r in routes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_route_stops: List[RouteStopData] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning("Ошибка загрузки связей для маршрута %s: %s",
                               routes[i].route_number, res)
            else:
                all_route_stops.extend(res)

        logger.info("Сформировано %d связей маршрут-остановка", len(all_route_stops))
        return all_route_stops

    # ── Внутренние методы ─────────────────────────────────────────────────────

    async def _fetch_route_stops_for(self, route: RouteData) -> List[RouteStopData]:
        """Загрузить stop_sequence для одного маршрута."""
        raw_route_id = route.external_id.removeprefix("datamos_")

        # Шаг 1: получаем по одному trip_id на каждое направление
        trips_raw = await self._fetch_filtered(
            DATASET_TRIPS_ID,
            f"Cells/route_id eq '{raw_route_id}'"
        )

        direction_trip: Dict[int, str] = {}
        for row in trips_raw:
            cells = row.get("Cells", row)
            trip_id = str(cells.get("trip_id", "")).strip()
            try:
                direction = int(cells.get("direction_id", 0))
            except (TypeError, ValueError):
                direction = 0
            if trip_id and direction not in direction_trip:
                direction_trip[direction] = trip_id

        if not direction_trip:
            return []

        # Шаг 2: для каждого trip_id загружаем упорядоченные остановки
        result: List[RouteStopData] = []
        for _direction, trip_id in direction_trip.items():
            times_raw = await self._fetch_filtered(
                DATASET_TIMES_ID,
                f"Cells/trip_id eq '{trip_id}'"
            )
            entries: List[Tuple[int, int]] = []
            for row in times_raw:
                cells = row.get("Cells", row)
                try:
                    seq     = int(cells["stop_sequence"])
                    stop_id = int(cells["stop_id"])
                except (KeyError, TypeError, ValueError):
                    continue
                entries.append((seq, stop_id))

            entries.sort(key=lambda x: x[0])
            for seq, stop_id in entries:
                result.append(RouteStopData(
                    route_external_id=route.external_id,
                    stop_external_id=f"datamos_{stop_id}",
                    sequence=seq,
                ))

        return result

    async def _fetch_all(self, dataset_id: int) -> List[dict]:
        """Загрузка всех записей датасета без параметров."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            url = f"{self.base_url}/datasets/{dataset_id}/rows?api_key={self.api_key}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Датасет %d: загружено %d записей", dataset_id, len(data))
            return data

    async def _fetch_filtered(self, dataset_id: int, filter_expr: str) -> List[dict]:
        """Загрузить записи датасета с OData-фильтром."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            url = (
                f"{self.base_url}/datasets/{dataset_id}/rows"
                f"?api_key={self.api_key}"
                f"&$filter={filter_expr}"
            )
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()


# ── Парсеры ───────────────────────────────────────────────────────────────────

def _parse_stop(cells: dict) -> Optional[StopData]:
    """Распарсить строку датасета 752 → StopData."""
    stop_id = cells.get("ID")
    name    = (cells.get("StationName") or cells.get("Name") or "").strip()
    lat     = _to_float(cells.get("Latitude_WGS84"))
    lon     = _to_float(cells.get("Longitude_WGS84"))

    if not stop_id or not name or lat is None or lon is None:
        return None

    return StopData(
        external_id=f"datamos_{stop_id}",
        name=name,
        latitude=lat,
        longitude=lon,
        stop_type="bus_stop",
    )


def _parse_route(cells: dict) -> Optional[RouteData]:
    """Распарсить строку датасета 60664 → RouteData."""
    route_id   = str(cells.get("route_id") or "").strip()
    short_name = str(cells.get("route_short_name") or "").strip()
    long_name  = str(cells.get("route_long_name") or "").strip()

    if not route_id or not short_name:
        return None

    try:
        route_type = int(cells.get("route_type", 3))
    except (TypeError, ValueError):
        route_type = 3

    return RouteData(
        external_id=f"datamos_{route_id}",
        route_number=short_name,
        transport_type=ROUTE_TYPE_MAP.get(route_type, "bus"),
        route_name=long_name or None,
    )


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None