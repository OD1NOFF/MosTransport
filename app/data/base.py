"""
Интерфейс источника данных.
Паттерн Strategy: позволяет заменять источники без изменения бизнес-логики.
Соответствует ТЗ п. 4.5.2.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StopData:
    external_id: str
    name: str
    latitude: float
    longitude: float
    stop_type: str  # bus_stop | tram_stop | trolleybus_stop | metro_station
    metro_line: Optional[str] = None
    metro_line_color: Optional[str] = None


@dataclass
class RouteData:
    external_id: str
    route_number: str
    transport_type: str  # bus | trolleybus | tram | metro
    route_name: Optional[str] = None
    direction: Optional[str] = None
    color: Optional[str] = None


@dataclass
class RouteStopData:
    route_external_id: str
    stop_external_id: str
    sequence: int


class DataSource(ABC):
    """Базовый интерфейс поставщика транспортных данных."""

    name: str = "base"

    @abstractmethod
    async def fetch_stops(self) -> List[StopData]: ...

    @abstractmethod
    async def fetch_routes(self) -> List[RouteData]: ...

    @abstractmethod
    async def fetch_route_stops(self) -> List[RouteStopData]: ...


# TODO: Здесь планируется добавить базовый класс CachedDataSource, который будет
# кэшировать ответы внешних API в БД для устойчивости при недоступности источников
# (см. ТЗ п. 4.4.3.1 — меры обеспечения безотказности).
