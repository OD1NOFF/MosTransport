"""
Адаптер OpenStreetMap (Overpass API).

См. ТЗ Приложение К, п. К.3. Используется для получения линий и станций Московского
метрополитена, а также для верификации координат наземных остановок.
"""

from typing import List

import httpx

from app.data.base import DataSource, RouteData, RouteStopData, StopData
from app.utils.logger import get_logger

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass QL: станции Московского метрополитена
METRO_STATIONS_QUERY = """
[out:json][timeout:60];
area["ISO3166-2"="RU-MOW"]->.moscow;
(
  node["railway"="station"]["station"="subway"](area.moscow);
);
out body;
"""

# Цветовая схема линий метро (основные, для наглядности)
METRO_LINE_COLORS = {
    "1": "#EF161E",  # Сокольническая
    "2": "#2DBE2C",  # Замоскворецкая
    "3": "#0078BE",  # Арбатско-Покровская
    "4": "#19C1E3",  # Филёвская
    "5": "#894E35",  # Кольцевая
    "6": "#F58631",  # Калужско-Рижская
    "7": "#8D5B2D",  # Таганско-Краснопресненская
    "8": "#FFCD1C",  # Калининская
    "9": "#999999",  # Серпуховско-Тимирязевская
    "10": "#B1D332",  # Люблинско-Дмитровская
    "11": "#83C1C1",  # Большая кольцевая
    "14": "#FFA8AF",  # МЦК
    "15": "#DC477D",  # Некрасовская
}


class OsmDataSource(DataSource):
    """Адаптер OpenStreetMap через Overpass API."""

    name = "osm"

    async def fetch_stops(self) -> List[StopData]:
        """Загрузить станции Московского метрополитена."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                OVERPASS_URL,
                data={"data": METRO_STATIONS_QUERY},
                headers={"User-Agent": "MosTransport/0.1 (educational project, MAI)"},
            )
            resp.raise_for_status()
            payload = resp.json()

        stops: List[StopData] = []
        for el in payload.get("elements", []):
            if el.get("type") != "node":
                continue
            tags = el.get("tags", {})
            name = tags.get("name:ru") or tags.get("name")
            if not name:
                continue
            line = _extract_line_ref(tags)
            stops.append(StopData(
                external_id=f"osm_{el.get('id')}",
                name=str(name).strip(),
                latitude=float(el["lat"]),
                longitude=float(el["lon"]),
                stop_type="metro_station",
                metro_line=line,
                metro_line_color=METRO_LINE_COLORS.get(line) if line else None,
            ))
        logger.info("Загружено %d станций метро из OSM", len(stops))
        return stops

    async def fetch_routes(self) -> List[RouteData]:
        # TODO: Здесь планируется загрузка relation "route_master"="subway" для формирования
        # линий метро как маршрутов. Требуется более сложный Overpass-запрос.
        return []

    async def fetch_route_stops(self) -> List[RouteStopData]:
        # TODO: Здесь планируется извлечение порядка станций из relation="route".
        return []


def _extract_line_ref(tags: dict) -> str | None:
    """Попытаться извлечь номер линии из тегов OSM (ref, line, colour)."""
    return tags.get("ref") or tags.get("line") or None
