"""
Эндпоинты работы с остановками.
См. ТЗ Приложение Г, п. Г.4 и Г.5.
"""

from fastapi import APIRouter, HTTPException

from app.api.models import ApiResponse
from app.db.repository import find_nearby_stops, get_routes_through_stop, get_stop_by_id

router = APIRouter()


@router.get("/stops/nearby", response_model=ApiResponse)
async def nearby_stops(lat: float, lon: float, radius_m: int = 500, limit: int = 20):
    """Получить список остановок в радиусе от точки."""
    if not (55.0 <= lat <= 56.5 and 36.0 <= lon <= 38.5):
        raise HTTPException(status_code=400, detail="координаты вне зоны покрытия")
    stops = find_nearby_stops(lat, lon, radius_m, limit=limit)
    return ApiResponse(success=True, data={"stops": stops})


@router.get("/stops/{stop_id}", response_model=ApiResponse)
async def stop_details(stop_id: int):
    """Подробная информация об остановке и маршрутах, проходящих через неё."""
    stop = get_stop_by_id(stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="остановка не найдена")
    stop["routes"] = get_routes_through_stop(stop_id)
    # TODO: Здесь планируется подключение расписания (schedules).
    return ApiResponse(success=True, data=stop)
