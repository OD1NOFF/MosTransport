"""
Эндпоинт построения маршрута.
См. ТЗ Приложение Г, п. Г.2.
"""

import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from app.api.models import ApiResponse, ErrorInfo, ResponseMeta, RouteRequest
from app.config.settings import get_settings
from app.routing.instructions import build_instructions
from app.routing.pathfinder import RouteNotFoundError, find_route
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/route", response_model=ApiResponse)
async def get_route(
    request: Request,
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    alternatives: int = 1,
    max_walk_m: int = 800,
):
    """Построить оптимальный маршрут и до N альтернатив.

    Пример: GET /api/v1/route?from_lat=55.735&from_lon=37.593&to_lat=55.775&to_lon=37.655
    """
    start = time.time()
    req_id = str(uuid.uuid4())
    settings = get_settings()

    try:
        params = RouteRequest(
            from_lat=from_lat, from_lon=from_lon, to_lat=to_lat, to_lon=to_lon,
            alternatives=alternatives, max_walk_m=max_walk_m,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_PARAMS",
            "message": "Некорректные параметры запроса",
            "details": str(e),
        })

    graph = request.app.state.graph
    try:
        raw_routes = find_route(
            graph,
            params.from_lat, params.from_lon, params.to_lat, params.to_lon,
            max_walk_m=params.max_walk_m,
            alternatives=params.alternatives,
        )
    except RouteNotFoundError as e:
        logger.info("Маршрут не найден: %s (%s)", str(e), e.code)
        return ApiResponse(
            success=False,
            error=ErrorInfo(code="ROUTE_NOT_FOUND", message=str(e)),
            meta=ResponseMeta(request_id=req_id, processing_time_ms=int((time.time() - start) * 1000)),
        )

    # Добавляем текстовые инструкции к каждому маршруту
    enriched = []
    for r in raw_routes:
        enriched.append({**r, "steps": build_instructions(r["segments"])})

    logger.info("route.built from=(%.5f,%.5f) to=(%.5f,%.5f) results=%d time=%dms",
                params.from_lat, params.from_lon, params.to_lat, params.to_lon,
                len(enriched), int((time.time() - start) * 1000))

    return ApiResponse(
        success=True,
        data={"routes": enriched},
        meta=ResponseMeta(request_id=req_id, processing_time_ms=int((time.time() - start) * 1000)),
    )


# TODO: Здесь планируется добавить эндпоинт POST /route/batch для пакетной маршрутизации
# (например, для сценариев бизнес-аналитики).
