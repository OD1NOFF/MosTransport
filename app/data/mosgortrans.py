"""
Адаптер для API ГУП «Мосгортранс».

См. ТЗ Приложение К, п. К.1. Класс реализует интерфейс DataSource и готов к использованию
после получения API-ключа Мосгортранса. В текущей редакции — заглушка с корректной
сигнатурой методов.
"""

from typing import List, Optional

import httpx

from app.config.settings import get_settings
from app.data.base import DataSource, RouteData, RouteStopData, StopData
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MosgortransDataSource(DataSource):
    """Адаптер API ГУП «Мосгортранс»."""

    name = "mosgortrans"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or get_settings().mosgortrans_api_key
        self.base_url = get_settings().mosgortrans_base_url

    async def fetch_stops(self) -> List[StopData]:
        if not self.api_key:
            logger.info("mosgortrans_api_key не задан — пропускаем загрузку из Мосгортранса")
            return []
        # TODO: Здесь планируется реализация после получения документации API Мосгортранса.
        # Шаблон запроса:
        #   async with httpx.AsyncClient(timeout=30.0) as client:
        #       resp = await client.get(f"{self.base_url}/stops",
        #                               headers={"X-API-Key": self.api_key})
        #       resp.raise_for_status()
        #       data = resp.json()
        # Формат ответа предполагается в виде JSON-массива объектов
        # {id, name, lat, lon, type}. При изменении формата — адаптировать парсинг ниже.
        return []

    async def fetch_routes(self) -> List[RouteData]:
        # TODO: Здесь планируется загрузка списка маршрутов (автобусы, троллейбусы, трамваи).
        return []

    async def fetch_route_stops(self) -> List[RouteStopData]:
        # TODO: Здесь планируется загрузка порядка следования остановок по маршрутам.
        return []
