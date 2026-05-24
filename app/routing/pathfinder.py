"""
Алгоритмы поиска маршрута: Дейкстра и Йена.
Соответствует ТЗ п. 4.3 (подсистема маршрутизации) и Приложению Е, п. Е.2-Е.3.
"""

from functools import lru_cache
from typing import List, Optional, Tuple

import networkx as nx

from app.db.repository import find_nearby_stops
from app.utils.geo import haversine_distance, travel_time_min
from app.utils.logger import get_logger

logger = get_logger(__name__)

START_NODE = "__start__"
END_NODE = "__end__"


def find_route(
    graph: nx.MultiDiGraph,
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    max_walk_m: int = 800,
    alternatives: int = 1,
) -> List[dict]:
    """Поиск оптимального маршрута и до N альтернатив.

    Возвращает список маршрутов (каждый — словарь с полями total_time_min, segments и т.д.).
    См. ТЗ п. Е.2 (алгоритм поиска), п. Е.3 (альтернативы Йена).
    """
    # Шаг 1: найти ближайшие остановки
    from_stops = find_nearby_stops(from_lat, from_lon, max_walk_m)
    to_stops = find_nearby_stops(to_lat, to_lon, max_walk_m)

    if not from_stops:
        raise RouteNotFoundError(
            "Рядом с начальной точкой не найдено остановок",
            code="NO_NEARBY_FROM",
        )
    if not to_stops:
        raise RouteNotFoundError(
            "Рядом с конечной точкой не найдено остановок",
            code="NO_NEARBY_TO",
        )

    # Шаг 2: добавить временные вершины и подходные рёбра
    working_graph = graph.copy()  # не модифицируем основной граф
    working_graph.add_node(START_NODE, latitude=from_lat, longitude=from_lon, name="Начальная точка")
    working_graph.add_node(END_NODE, latitude=to_lat, longitude=to_lon, name="Конечная точка")

    for s in from_stops:
        t = travel_time_min(s["distance_m"], "walk")
        working_graph.add_edge(START_NODE, s["id"], key=f"start_{s['id']}",
                               edge_type="walk", weight=t, distance_m=s["distance_m"])
    for s in to_stops:
        t = travel_time_min(s["distance_m"], "walk")
        working_graph.add_edge(s["id"], END_NODE, key=f"end_{s['id']}",
                               edge_type="walk", weight=t, distance_m=s["distance_m"])

    # Шаг 3: свернуть в DiGraph — нужно для обоих алгоритмов.
    # _collapse_to_digraph сохраняет атрибуты ребра с минимальным весом,
    # поэтому route_id/route_number будут консистентными для всего пути.
    simple_g = _collapse_to_digraph(working_graph)

    # Шаг 4: поиск путей
    results = []
    try:
        if alternatives <= 1:
            path = nx.shortest_path(simple_g, START_NODE, END_NODE, weight="weight")
            paths = [path]
        else:
            # Алгоритм Йена (k кратчайших путей)
            gen = nx.shortest_simple_paths(simple_g, START_NODE, END_NODE, weight="weight")
            paths = []
            for i, p in enumerate(gen):
                if i >= alternatives:
                    break
                paths.append(p)
    except nx.NetworkXNoPath:
        raise RouteNotFoundError("Невозможно построить маршрут между указанными точками",
                                 code="NO_PATH")

    # Строим сегменты по DiGraph — у каждой пары вершин ровно одно ребро
    best_time: Optional[float] = None
    for p in paths:
        segments, total_time, total_dist = _build_segments(simple_g, p)
        if best_time is None:
            best_time = total_time
        results.append({
            "total_time_min": round(total_time, 1),
            "total_distance_m": round(total_dist, 1),
            "transfers_count": max(0, len([s for s in segments if s["type"] not in ("walk", "transfer")]) - 1),
            "segments": segments,
        })

    return results


def _build_segments(g: nx.DiGraph, node_path: List) -> Tuple[List[dict], float, float]:
    """Преобразовать последовательность вершин в список сегментов.

    Сегмент — непрерывный участок маршрута одним транспортным средством.
    Последовательные рёбра одного маршрута схлопываются в один сегмент.
    Соответствует ТЗ п. 4.3.3.
    """
    segments: List[dict] = []
    total_time = 0.0
    total_dist = 0.0

    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        # DiGraph: между u и v ровно одно ребро
        edge = g[u][v]

        edge_type = edge.get("edge_type", "walk")
        weight = float(edge.get("weight", 0))
        total_time += weight

        # Расстояние
        if edge.get("distance_m") is not None:
            seg_dist = float(edge["distance_m"])
        elif "latitude" in g.nodes[u] and "latitude" in g.nodes[v]:
            seg_dist = haversine_distance(
                g.nodes[u]["latitude"], g.nodes[u]["longitude"],
                g.nodes[v]["latitude"], g.nodes[v]["longitude"],
            )
        else:
            seg_dist = 0.0
        total_dist += seg_dist

        # Ключ схлопывания: для transit используем route_number (не route_id),
        # чтобы маршруты с одинаковым номером но разными id не дробились.
        group_key = _segment_key(edge)

        last = segments[-1] if segments else None
        if last is not None and last["_key"] == group_key:
            # Продолжаем тот же сегмент
            last["to_stop_id"] = v
            last["to_stop_name"] = _stop_name(g, v)
            last["duration_min"] += weight
            last["distance_m"] += seg_dist
            last["stops_count"] += 1
            last["geometry"].append([g.nodes[v].get("latitude"), g.nodes[v].get("longitude")])
        else:
            seg = {
                "_key": group_key,
                "type": edge_type if edge_type != "transit" else edge.get("transport_type", "bus"),
                "route_number": edge.get("route_number"),
                "line": edge.get("transport_type") if edge_type == "transit" else None,
                "color": edge.get("color"),
                "from_stop_id": u,
                "from_stop_name": _stop_name(g, u),
                "to_stop_id": v,
                "to_stop_name": _stop_name(g, v),
                "duration_min": weight,
                "distance_m": seg_dist,
                "stops_count": 1,
                "geometry": [
                    [g.nodes[u].get("latitude"), g.nodes[u].get("longitude")],
                    [g.nodes[v].get("latitude"), g.nodes[v].get("longitude")],
                ],
            }
            segments.append(seg)

    # Убираем служебное поле и округляем
    for s in segments:
        s.pop("_key", None)
        s["duration_min"] = round(s["duration_min"], 1)
        s["distance_m"] = round(s["distance_m"], 1)

    return segments, total_time, total_dist


def _segment_key(edge: dict) -> str:
    """Ключ для схлопывания соседних рёбер в один сегмент.

    Для транзитных рёбер используем route_number (видимый номер маршрута),
    чтобы автобус 270 на всём пути давал один сегмент независимо от route_id.
    """
    et = edge.get("edge_type", "walk")
    if et == "transit":
        # Используем route_number как ключ — он одинаков для всего маршрута
        return f"transit:{edge.get('route_number')}:{edge.get('transport_type')}"
    return et  # "walk" или "transfer"


def _stop_name(g: nx.DiGraph, node_id) -> Optional[str]:
    if node_id in (START_NODE, END_NODE):
        return None
    return g.nodes[node_id].get("name")


class RouteNotFoundError(Exception):
    """Маршрут не может быть построен."""

    def __init__(self, message: str, code: str = "NO_PATH") -> None:
        super().__init__(message)
        self.code = code


def _collapse_to_digraph(mg: nx.MultiDiGraph) -> nx.DiGraph:
    """Свернуть MultiDiGraph в DiGraph.

    Для каждой пары вершин (u, v) оставляем ребро с минимальным весом
    среди рёбер одного типа: сначала transit, потом transfer, потом walk.
    Это гарантирует что transit-ребро не вытеснится более дешёвым transfer,
    и атрибуты (route_id, route_number) будут консистентными вдоль пути.
    """
    dg = nx.DiGraph()
    for n, data in mg.nodes(data=True):
        dg.add_node(n, **data)

    # Приоритет типов: transit побеждает transfer побеждает walk
    TYPE_PRIORITY = {"transit": 0, "transfer": 1, "walk": 2}

    for u, v, data in mg.edges(data=True):
        if not dg.has_edge(u, v):
            dg.add_edge(u, v, **data)
        else:
            existing = dg[u][v]
            new_prio = TYPE_PRIORITY.get(data.get("edge_type", "walk"), 2)
            old_prio = TYPE_PRIORITY.get(existing.get("edge_type", "walk"), 2)
            # Заменяем если новый тип приоритетнее,
            # или тот же тип но с меньшим весом
            if new_prio < old_prio:
                dg[u][v].update(data)
            elif new_prio == old_prio and data.get("weight", float("inf")) < existing.get("weight", float("inf")):
                dg[u][v].update(data)

    return dg


# TODO: Здесь планируется LRU-кэш результатов маршрутизации по округлённым координатам
# (см. ТЗ п. 4.7, пункт 2). Ключ кэша — кортеж (lat1, lon1, lat2, lon2, max_walk_m),
# округлённые до 4 знаков (~11 м). Размер кэша — 1000 записей.

# TODO: Здесь планируется реализация временных интервалов с учётом расписания
# (разный вес рёбер в зависимости от времени суток).
