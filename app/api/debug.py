"""
Отладочный эндпоинт: полный дамп графа (остановки + рёбра).
Используется страницей debug_map.html для визуализации транспортной сети.

Подключить в app/main.py:
    from app.api import debug
    app.include_router(debug.router, prefix="/api/v1", tags=["debug"])
"""

from fastapi import APIRouter

from app.api.models import ApiResponse
from app.db.repository import list_active_routes, list_active_stops, list_route_stops, list_transfers
from app.routing.graph import AUTO_TRANSFER_RADIUS_M
from app.utils.geo import haversine_distance

router = APIRouter()


@router.get("/debug/graph", response_model=ApiResponse)
async def debug_graph():
    """Все остановки и рёбра графа для отладочной карты."""

    stops = list_active_stops()
    stop_index = {s["id"]: s for s in stops}

    routes = {r["id"]: r for r in list_active_routes()}
    route_stops = list_route_stops()

    edges = []

    # Транзитные рёбра (перегоны по маршрутам)
    by_route: dict[int, list] = {}
    for rs in route_stops:
        by_route.setdefault(rs["route_id"], []).append(rs)

    for route_id, entries in by_route.items():
        route = routes.get(route_id)
        if not route:
            continue
        entries.sort(key=lambda x: x["stop_sequence"])
        for i in range(len(entries) - 1):
            a, b = entries[i], entries[i + 1]
            if a["stop_id"] not in stop_index or b["stop_id"] not in stop_index:
                continue
            edges.append({
                "from_id": a["stop_id"],
                "to_id": b["stop_id"],
                "type": "transit",
                "transport_type": route["transport_type"],
                "route_number": route["route_number"],
                "color": route.get("color"),
            })

    # Явные пересадки из БД
    for tr in list_transfers():
        edges.append({
            "from_id": tr["from_stop_id"],
            "to_id": tr["to_stop_id"],
            "type": "transfer",
            "transport_type": "walk",
            "route_number": None,
            "color": None,
        })

    # Автоматические пересадки (те же 300 м что в graph.py)
    node_ids = list(stop_index.keys())
    for i, a in enumerate(node_ids):
        for b in node_ids[i + 1:]:
            na, nb = stop_index[a], stop_index[b]
            d = haversine_distance(na["latitude"], na["longitude"],
                                   nb["latitude"], nb["longitude"])
            if d <= AUTO_TRANSFER_RADIUS_M:
                edges.append({
                    "from_id": a, "to_id": b,
                    "type": "transfer", "transport_type": "walk",
                    "route_number": None, "color": None,
                })

    return ApiResponse(success=True, data={"stops": stops, "edges": edges})
