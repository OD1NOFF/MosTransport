"""
Адаптер для загрузки данных из локального JSON-кэша.
Использовать после однократного запуска fetch_and_cache.py.

Подключить в updater.py:
    from app.data.cached import CachedDataSource
    sources = [CachedDataSource(), OsmDataSource()]
"""

import json
from pathlib import Path
from typing import List, Optional

from app.config.settings import get_settings
from app.data.base import DataSource, RouteData, RouteStopData, StopData
from app.utils.logger import get_logger

logger = get_logger(__name__)

ROUTE_TYPE_MAP = {
    0: "tram", 1: "metro", 3: "bus", 11: "trolleybus", 800: "trolleybus",
}


class CachedDataSource(DataSource):
    """Читает данные из data/cache/*.json — мгновенно, без запросов к API."""

    name = "cached"

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_dir = cache_dir or Path("data/cache")

    async def fetch_stops(self) -> List[StopData]:
        path = self.cache_dir / "stops.json"
        if not path.exists():
            logger.warning("Кэш остановок не найден: %s", path)
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        stops = []
        for row in raw:
            cells = row.get("Cells", row)
            stop = _parse_stop(cells)
            if stop:
                stops.append(stop)
        logger.info("Кэш: загружено %d остановок", len(stops))
        return stops

    async def fetch_routes(self) -> List[RouteData]:
        path = self.cache_dir / "routes.json"
        if not path.exists():
            logger.warning("Кэш маршрутов не найден: %s", path)
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        routes, seen = [], set()
        for row in raw:
            cells = row.get("Cells", row)
            route = _parse_route(cells)
            if route and route.external_id not in seen:
                seen.add(route.external_id)
                routes.append(route)
        logger.info("Кэш: загружено %d маршрутов", len(routes))
        return routes

    async def fetch_route_stops(self) -> List[RouteStopData]:
        path = self.cache_dir / "route_stops.json"
        if not path.exists():
            logger.warning("Кэш связей не найден: %s", path)
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        result = []
        for item in raw:
            try:
                result.append(RouteStopData(
                    route_external_id=item["route_id"],
                    stop_external_id=item["stop_id"],
                    sequence=item["sequence"],
                ))
            except (KeyError, TypeError):
                continue
        logger.info("Кэш: загружено %d связей маршрут-остановка", len(result))
        return result


def _parse_stop(cells: dict) -> Optional[StopData]:
    stop_id = cells.get("ID")
    name = (cells.get("StationName") or cells.get("Name") or "").strip()
    try:
        lat = float(cells["Latitude_WGS84"])
        lon = float(cells["Longitude_WGS84"])
    except (KeyError, TypeError, ValueError):
        return None
    if not stop_id or not name:
        return None
    return StopData(
        external_id=f"datamos_{stop_id}",
        name=name, latitude=lat, longitude=lon, stop_type="bus_stop",
    )


def _parse_route(cells: dict) -> Optional[RouteData]:
    route_id = str(cells.get("route_id") or "").strip()
    short_name = str(cells.get("route_short_name") or "").strip()
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
        route_name=str(cells.get("route_long_name") or "") or None,
    )
