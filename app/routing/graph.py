"""
Построение транспортного графа.
Соответствует ТЗ п. 4.2.1 (подсистема маршрутизации) и Приложению Е.
"""

from typing import Optional

import networkx as nx

from app.db.repository import list_active_routes, list_active_stops, list_route_stops, list_transfers
from app.utils.geo import TRANSPORT_SPEEDS, haversine_distance, travel_time_min
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Штраф за пересадку (минуты), см. ТЗ п. Е.1
TRANSFER_PENALTY_MIN = 3.0
AUTO_TRANSFER_RADIUS_M = 300


def build_graph() -> nx.MultiDiGraph:
    """Построить мультиграф транспортной сети по данным из БД.

    Вершины — остановки. Рёбра трёх типов: transit, transfer, walk.
    См. ТЗ Приложение Е, п. Е.1 (формирование транспортного графа).
    """
    g = nx.MultiDiGraph()

    stops = list_active_stops()
    for s in stops:
        g.add_node(s["id"], **s)

    if not stops:
        logger.warning("В БД нет остановок. Граф пустой. Запустите загрузку данных.")
        return g

    routes = {r["id"]: r for r in list_active_routes()}
    rs = list_route_stops()

    # Группировка по маршруту для получения последовательных перегонов
    by_route: dict[int, list[dict]] = {}
    for x in rs:
        by_route.setdefault(x["route_id"], []).append(x)

    for route_id, entries in by_route.items():
        route = routes.get(route_id)
        if not route:
            continue
        entries.sort(key=lambda x: x["stop_sequence"])
        for i in range(len(entries) - 1):
            a = entries[i]
            b = entries[i + 1]
            # Вес ребра: время проезда (из расписания либо рассчитанное по скорости)
            if b.get("travel_time_min") is not None:
                t = float(b["travel_time_min"])
            else:
                lat1, lon1 = g.nodes[a["stop_id"]]["latitude"], g.nodes[a["stop_id"]]["longitude"]
                lat2, lon2 = g.nodes[b["stop_id"]]["latitude"], g.nodes[b["stop_id"]]["longitude"]
                d = haversine_distance(lat1, lon1, lat2, lon2)
                t = travel_time_min(d, route["transport_type"])
            g.add_edge(a["stop_id"], b["stop_id"],
                       key=f"r{route_id}_s{a['stop_sequence']}",
                       edge_type="transit",
                       route_id=route_id,
                       route_number=route["route_number"],
                       transport_type=route["transport_type"],
                       color=route.get("color"),
                       weight=t)

    # Явные пересадки из БД
    for tr in list_transfers():
        g.add_edge(tr["from_stop_id"], tr["to_stop_id"],
                   key=f"t_{tr['from_stop_id']}_{tr['to_stop_id']}",
                   edge_type="transfer",
                   transfer_type=tr["transfer_type"],
                   weight=float(tr["walk_time_min"]) + TRANSFER_PENALTY_MIN)

    # Автоматические пересадки между близкими остановками (см. ТЗ п. Е.1)
    _add_auto_transfers(g)

    logger.info("Граф построен: %d вершин, %d рёбер", g.number_of_nodes(), g.number_of_edges())
    return g


def _add_auto_transfers(g: nx.MultiDiGraph) -> None:
    """Автоматическое создание пересадочных рёбер между остановками в пределах 300 м.

    Упрощённая реализация O(n²). Для продакшена планируется заменить на пространственный
    индекс (rtree или grid). См. ТЗ п. Е.1.
    """
    node_ids = list(g.nodes)
    added = 0
    for i, a in enumerate(node_ids):
        for b in node_ids[i + 1:]:
            na, nb = g.nodes[a], g.nodes[b]
            d = haversine_distance(na["latitude"], na["longitude"],
                                   nb["latitude"], nb["longitude"])
            if d > AUTO_TRANSFER_RADIUS_M:
                continue
            # Если пересадка уже есть, не дублируем
            if any(data.get("edge_type") == "transfer" for _, _, data in g.edges([a], data=True) if _ == b):
                continue
            t = travel_time_min(d, "walk") + TRANSFER_PENALTY_MIN
            g.add_edge(a, b, key=f"auto_{a}_{b}", edge_type="transfer",
                       transfer_type="walking", weight=t)
            g.add_edge(b, a, key=f"auto_{b}_{a}", edge_type="transfer",
                       transfer_type="walking", weight=t)
            added += 1
    if added:
        logger.info("Добавлено %d автоматических пересадок", added)


# TODO: Здесь планируется функция rebuild_graph() для перестроения графа после
# обновления данных без перезапуска сервера. См. ТЗ п. 4.5.3.
