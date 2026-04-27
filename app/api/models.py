"""
Pydantic-модели запросов и ответов REST API.
Соответствует ТЗ Приложение Г и Приложение Л.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: Optional[List[dict]] = None


class ResponseMeta(BaseModel):
    request_id: str
    processing_time_ms: int
    api_version: str = "v1"


class ApiResponse(BaseModel):
    """Унифицированный формат ответа API (см. ТЗ п. Л.1)."""
    success: bool
    data: Optional[dict | list] = None
    error: Optional[ErrorInfo] = None
    meta: Optional[ResponseMeta] = None


class RouteSegment(BaseModel):
    type: str = Field(..., description="walk | transfer | bus | trolleybus | tram | metro")
    route_number: Optional[str] = None
    line: Optional[str] = None
    color: Optional[str] = None
    from_stop_id: Optional[int | str] = None
    from_stop_name: Optional[str] = None
    to_stop_id: Optional[int | str] = None
    to_stop_name: Optional[str] = None
    duration_min: float
    distance_m: float
    stops_count: int
    geometry: List[List[float]]


class Route(BaseModel):
    total_time_min: float
    total_distance_m: float
    transfers_count: int
    segments: List[RouteSegment]
    steps: List[str]


class RouteRequest(BaseModel):
    """Параметры запроса на построение маршрута.

    См. ТЗ Приложение Г, п. Г.2 и п. Л.3 (валидация).
    """
    from_lat: float = Field(..., ge=55.0, le=56.5, description="Широта начальной точки")
    from_lon: float = Field(..., ge=36.0, le=38.5, description="Долгота начальной точки")
    to_lat: float = Field(..., ge=55.0, le=56.5)
    to_lon: float = Field(..., ge=36.0, le=38.5)
    alternatives: int = Field(1, ge=1, le=3)
    max_walk_m: int = Field(800, ge=100, le=2000)

    @field_validator("from_lat", "from_lon", "to_lat", "to_lon")
    @classmethod
    def _check_finite(cls, v: float) -> float:
        if v != v:  # NaN check
            raise ValueError("координата должна быть конечным числом")
        return v


class Stop(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    stop_type: str
    metro_line: Optional[str] = None
    distance_m: Optional[float] = None


class GeocodeResult(BaseModel):
    name: str
    lat: float
    lon: float
    display_name: Optional[str] = None


class HealthStatus(BaseModel):
    status: str  # ok | degraded | error
    database_status: str
    graph_nodes: int
    graph_edges: int
    last_data_update: Optional[str] = None
    uptime_seconds: int
    version: str
