"""
Эндпоинт геокодирования.
См. ТЗ Приложение Г, п. Г.3 и п. 4.4.
"""

from fastapi import APIRouter, HTTPException, Query

from app.api.models import ApiResponse
from app.geocoder.nominatim import geocode_query

router = APIRouter()


@router.get("/geocode", response_model=ApiResponse)
async def geocode(q: str = Query(..., min_length=2, max_length=200), limit: int = 5):
    """Геокодирование: преобразование текстового адреса в координаты.

    Источник — Nominatim (OpenStreetMap). Ответ ограничен территорией Москвы.
    """
    try:
        results = await geocode_query(q, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"сервис геокодирования недоступен: {e}")
    return ApiResponse(success=True, data={"results": results})
