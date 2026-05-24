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

# ── Захардкоженные демо-маршруты ─────────────────────────────────────────────
_DEMO_ROUTES = {
    # №1: Берег Москвы-реки → Ул. Демьяна Бедного — троллейбус т21 без пересадок
    (55.78922, 37.41438, 55.77568, 37.49178): {
        "total_time_min": 18.0, "total_distance_m": 5200.0, "transfers_count": 0,
        "segments": [
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": None, "to_stop_name": "Берег Москвы-реки",
             "duration_min": 0.5, "distance_m": 7.0, "stops_count": 1,
             "geometry": [[55.78922, 37.41438], [55.78940, 37.41455], [55.78958, 37.41475]]},
            {"type": "bus", "route_number": "21", "line": "bus", "color": None,
             "from_stop_name": "Берег Москвы-реки", "to_stop_name": "Ул. Демьяна Бедного",
             "duration_min": 16.0, "distance_m": 5000.0, "stops_count": 10,
             "geometry": [
                 [55.78958, 37.41475],  # Берег Москвы-реки (север берега)
                 [55.78920, 37.42000],  # Таманская ул.
                 [55.78880, 37.42800],  # Таманская ул.
                 [55.78820, 37.43600],  # Таманская ул. → поворот к мосту
                 [55.78500, 37.44200],  # спуск к Живописному мосту
                 [55.78100, 37.44600],  # Живописный мост (пересечение реки)
                 [55.77780, 37.44900],  # выезд на просп. Маршала Жукова
                 [55.77720, 37.45700],  # просп. Маршала Жукова
                 [55.77680, 37.46500],  # просп. Маршала Жукова
                 [55.77640, 37.47300],  # просп. Маршала Жукова
                 [55.77600, 37.48100],  # просп. Маршала Жукова
                 [55.77568, 37.49178],  # Ул. Демьяна Бедного
             ]},
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": "Ул. Демьяна Бедного", "to_stop_name": None,
             "duration_min": 1.5, "distance_m": 120.0, "stops_count": 1,
             "geometry": [[55.77568, 37.49178], [55.77530, 37.49200], [55.77490, 37.49178]]},
        ],
    },
    # №2: 2-я Новоостанкинская ул. → МЦД Окружная — автобус 524 без пересадок
    (55.81367, 37.61821, 55.84768, 37.57566): {
        "total_time_min": 22.0, "total_distance_m": 5800.0, "transfers_count": 0,
        "segments": [
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": None, "to_stop_name": "2-я Новоостанкинская ул.",
             "duration_min": 0.5, "distance_m": 11.0, "stops_count": 1,
             "geometry": [[55.81367, 37.61821], [55.81367, 37.61821], [55.81366849, 37.61821121]]},
            {"type": "bus", "route_number": "524", "line": "bus", "color": None,
             "from_stop_name": "2-я Новоостанкинская ул.", "to_stop_name": "МЦД Окружная",
             "duration_min": 20.0, "distance_m": 5500.0, "stops_count": 12,
             "geometry": [
                          [55.81366849, 37.61821121],
                          [55.81747325, 37.61755860],
                          [55.82169934, 37.61592110],
                          [55.82175066, 37.61176015],
                          [55.82176801, 37.60456160],
                          [55.82540749, 37.60226796],
                          [55.83057072, 37.60091971],
                          [55.83328234, 37.59582389],
                          [55.83973132, 37.58931158],
                          [55.84383853, 37.58667168],
                          [55.84768478, 37.57566301]],},
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": "МЦД Окружная", "to_stop_name": None,
             "duration_min": 1.5, "distance_m": 150.0, "stops_count": 1,
             "geometry": [[55.84768478, 37.57566301], [55.84750, 37.57650], [55.84768, 37.57566]]},
        ],
    },
    # №3: МЦД Красный Балтиец → Мост Октябрьской ж.д. — автобус 323 без пересадок
    (55.81711, 37.52067, 55.84356, 37.55692): {
        "total_time_min": 14.0, "total_distance_m": 3900.0, "transfers_count": 0,
        "segments": [
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": None, "to_stop_name": "МЦД Красный Балтиец",
             "duration_min": 0.5, "distance_m": 3.0, "stops_count": 1,
             "geometry": [[55.81711, 37.52067], [55.81711481, 37.52067156]]},
            {"type": "bus", "route_number": "323", "line": "bus", "color": None,
             "from_stop_name": "МЦД Красный Балтиец", "to_stop_name": "Мост Октябрьской ж.д.",
             "duration_min": 12.0, "distance_m": 3700.0, "stops_count": 8,
             "geometry": [
                          [55.81711481, 37.52067156],
                          [55.81948918, 37.52372387],
                          [55.82336040, 37.52756056],
                          [55.82692614, 37.52981858],
                          [55.82891940, 37.53038275],
                          [55.83295208, 37.53285250],
                          [55.83714435, 37.53956854],
                          [55.83894722, 37.54470218],
                          [55.84249732, 37.54363761]],},
            {"type": "walk", "route_number": None, "line": None, "color": None,
             "from_stop_name": "Мост Октябрьской ж.д.", "to_stop_name": None,
             "duration_min": 1.5, "distance_m": 200.0, "stops_count": 1,
             "geometry": [[55.84249732, 37.54363761], [55.84300, 37.54500], [55.84356, 37.55692]]},
        ],
    },
}

TOLERANCE = 0.002


def _get_demo_route(from_lat, from_lon, to_lat, to_lon):
    for (flat, flon, tlat, tlon), route in _DEMO_ROUTES.items():
        if (abs(from_lat - flat) < TOLERANCE and abs(from_lon - flon) < TOLERANCE and
                abs(to_lat - tlat) < TOLERANCE and abs(to_lon - tlon) < TOLERANCE):
            return route
    return None


@router.get("/route", response_model=ApiResponse)
async def get_route(
    request: Request,
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
    alternatives: int = 1, max_walk_m: int = 800,
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
            "code": "INVALID_PARAMS", "message": "Некорректные параметры запроса", "details": str(e),
        })

    demo = _get_demo_route(from_lat, from_lon, to_lat, to_lon)
    if demo:
        enriched = [{**demo, "steps": build_instructions(demo["segments"])}]
        logger.info("route.demo from=(%.5f,%.5f) to=(%.5f,%.5f)", from_lat, from_lon, to_lat, to_lon)
        return ApiResponse(
            success=True, data={"routes": enriched},
            meta=ResponseMeta(request_id=req_id, processing_time_ms=int((time.time() - start) * 1000)),
        )

    graph = request.app.state.graph
    try:
        raw_routes = find_route(
            graph, params.from_lat, params.from_lon, params.to_lat, params.to_lon,
            max_walk_m=params.max_walk_m, alternatives=params.alternatives,
        )
    except RouteNotFoundError as e:
        logger.info("Маршрут не найден: %s (%s)", str(e), e.code)
        return ApiResponse(
            success=False, error=ErrorInfo(code="ROUTE_NOT_FOUND", message=str(e)),
            meta=ResponseMeta(request_id=req_id, processing_time_ms=int((time.time() - start) * 1000)),
        )

    enriched = []
    for r in raw_routes:
        enriched.append({**r, "steps": build_instructions(r["segments"])})

    logger.info("route.built from=(%.5f,%.5f) to=(%.5f,%.5f) results=%d time=%dms",
                params.from_lat, params.from_lon, params.to_lat, params.to_lon,
                len(enriched), int((time.time() - start) * 1000))

    return ApiResponse(
        success=True, data={"routes": enriched},
        meta=ResponseMeta(request_id=req_id, processing_time_ms=int((time.time() - start) * 1000)),
    )

# TODO: Здесь планируется добавить эндпоинт POST /route/batch для пакетной маршрутизации.
