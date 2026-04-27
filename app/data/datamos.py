"""
Адаптер для портала открытых данных Правительства Москвы (data.mos.ru).

См. ТЗ Приложение К, п. К.2. Документация API: https://apidata.mos.ru/Docs
Ключ запрашивается на https://data.mos.ru и передаётся в параметре api_key.
"""

from typing import List, Optional

import httpx

from app.config.settings import get_settings
from app.data.base import DataSource, RouteData, RouteStopData, StopData
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Идентификаторы наборов данных на data.mos.ru (уточнить перед запуском):
#   624 — Остановки наземного городского транспорта
#   752 — Маршруты НГПТ
# Фактические id следует сверить по https://data.mos.ru (раздел «Транспорт»).
DATASET_STOPS_ID = 624


class DataMosDataSource(DataSource):
    """Адаптер data.mos.ru."""

    name = "datamos"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or get_settings().datamos_api_key
        self.base_url = get_settings().datamos_base_url
        if not self.api_key:
            logger.warning("datamos_api_key не задан — запросы будут отклонены API")

    async def fetch_stops(self) -> List[StopData]:
        """Получить список остановок из набора данных «Остановки НГПТ»."""
        if not self.api_key:
            return []
        url = f"{self.base_url}/datasets/{DATASET_STOPS_ID}/rows"
        params = {"api_key": self.api_key, "$top": 5000}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        stops: List[StopData] = []
        for row in payload:
            cells = row.get("Cells", {})
            lat = _pick_float(cells, ["Latitude_WGS84", "Latitude"])
            lon = _pick_float(cells, ["Longitude_WGS84", "Longitude"])
            name = cells.get("Name") or cells.get("StopName") or ""
            ext_id = str(row.get("global_id") or row.get("Number"))
            if lat is None or lon is None or not name or not ext_id:
                continue
            stops.append(StopData(
                external_id=f"datamos_{ext_id}",
                name=str(name).strip(),
                latitude=lat,
                longitude=lon,
                stop_type="bus_stop",
            ))
        logger.info("Загружено %d остановок из data.mos.ru", len(stops))
        return stops

    async def fetch_routes(self) -> List[RouteData]:
        # TODO: Здесь планируется реализация после получения id датасета маршрутов.
        return []

    async def fetch_route_stops(self) -> List[RouteStopData]:
        # TODO: Здесь планируется реализация после получения id датасета маршрутов.
        return []


def _pick_float(cells: dict, keys: List[str]) -> Optional[float]:
    for k in keys:
        v = cells.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None
