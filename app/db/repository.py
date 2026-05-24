"""
Репозиторий для работы с данными в БД.
Паттерн Repository: абстрагирует SQL-запросы от бизнес-логики.
Соответствует ТЗ п. 4.3.2.1.
"""

from typing import List, Optional

from app.db.connection import get_db
from app.utils.geo import bounding_box, haversine_distance


def list_active_stops() -> List[dict]:
    """Получить все активные остановки. Используется при построении графа."""
    cur = get_db().execute(
        "SELECT id, external_id, name, latitude, longitude, stop_type, "
        "metro_line, metro_line_color FROM stops WHERE is_active = 1"
    )
    return [dict(r) for r in cur.fetchall()]


def list_active_routes() -> List[dict]:
    """Получить все активные маршруты."""
    cur = get_db().execute(
        "SELECT id, external_id, route_number, route_name, transport_type, "
        "direction, color FROM routes WHERE is_active = 1"
    )
    return [dict(r) for r in cur.fetchall()]


def list_route_stops(route_id: Optional[int] = None) -> List[dict]:
    """Получить связи маршрут-остановка (упорядочены по sequence)."""
    if route_id is None:
        cur = get_db().execute(
            "SELECT route_id, stop_id, stop_sequence, travel_time_min, distance_m "
            "FROM route_stops ORDER BY route_id, stop_sequence"
        )
    else:
        cur = get_db().execute(
            "SELECT route_id, stop_id, stop_sequence, travel_time_min, distance_m "
            "FROM route_stops WHERE route_id = ? ORDER BY stop_sequence",
            (route_id,),
        )
    return [dict(r) for r in cur.fetchall()]


def list_transfers() -> List[dict]:
    """Получить все пешеходные переходы/пересадки."""
    cur = get_db().execute(
        "SELECT from_stop_id, to_stop_id, distance_m, walk_time_min, transfer_type FROM transfers"
    )
    return [dict(r) for r in cur.fetchall()]


def get_stop_by_id(stop_id: int) -> Optional[dict]:
    cur = get_db().execute(
        "SELECT id, external_id, name, latitude, longitude, stop_type, "
        "metro_line, metro_line_color FROM stops WHERE id = ? AND is_active = 1",
        (stop_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_routes_through_stop(stop_id: int) -> List[dict]:
    """Маршруты, проходящие через данную остановку (для карточки остановки)."""
    cur = get_db().execute(
        "SELECT DISTINCT r.id, r.route_number, r.route_name, r.transport_type, r.color "
        "FROM routes r JOIN route_stops rs ON rs.route_id = r.id "
        "WHERE rs.stop_id = ? AND r.is_active = 1",
        (stop_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def find_nearby_stops(lat: float, lon: float, radius_m: float, limit: int = 50) -> List[dict]:
    """Поиск остановок в радиусе от точки.

    Двухэтапный алгоритм (см. ТЗ п. 4.3.1, шаг 1):
    1. Грубая фильтрация по bounding box через SQL (использует индекс idx_stops_coords).
    2. Точный расчёт расстояния по формуле гаверсинуса на отфильтрованных кандидатах.
    """
    lat_min, lat_max, lon_min, lon_max = bounding_box(lat, lon, radius_m)
    cur = get_db().execute(
        "SELECT id, name, latitude, longitude, stop_type, metro_line "
        "FROM stops WHERE is_active = 1 "
        "AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
        (lat_min, lat_max, lon_min, lon_max),
    )
    candidates = [dict(r) for r in cur.fetchall()]
    result = []
    for c in candidates:
        d = haversine_distance(lat, lon, c["latitude"], c["longitude"])
        if d <= radius_m:
            c["distance_m"] = round(d, 1)
            result.append(c)
    result.sort(key=lambda x: x["distance_m"])
    return result[:limit]


def upsert_stop(external_id: str, name: str, lat: float, lon: float,
                stop_type: str, metro_line: Optional[str] = None,
                metro_line_color: Optional[str] = None) -> int:
    """Вставить или обновить остановку. Возвращает id."""
    db = get_db()
    db.execute(
        "INSERT INTO stops (external_id, name, latitude, longitude, stop_type, metro_line, metro_line_color) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(external_id) DO UPDATE SET "
        "name=excluded.name, latitude=excluded.latitude, longitude=excluded.longitude, "
        "stop_type=excluded.stop_type, metro_line=excluded.metro_line, "
        "metro_line_color=excluded.metro_line_color, updated_at=CURRENT_TIMESTAMP",
        (external_id, name, lat, lon, stop_type, metro_line, metro_line_color),
    )
    db.commit()
    cur = db.execute("SELECT id FROM stops WHERE external_id = ?", (external_id,))
    return cur.fetchone()["id"]


# TODO: Здесь планируется добавить методы для работы с расписаниями (schedules)
# и словарём топонимов (toponyms). См. ТЗ п. 4.3.2.5, 4.3.2.6.

def upsert_route(external_id: str, route_number: str, transport_type: str,
                 route_name: Optional[str] = None, direction: Optional[str] = None,
                 color: Optional[str] = None) -> int:
    """Вставить или обновить маршрут. Возвращает id."""
    db = get_db()
    db.execute(
        "INSERT INTO routes (external_id, route_number, transport_type, route_name, direction, color) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(external_id) DO UPDATE SET "
        "route_number=excluded.route_number, transport_type=excluded.transport_type, "
        "route_name=excluded.route_name, direction=excluded.direction, "
        "color=excluded.color, updated_at=CURRENT_TIMESTAMP",
        (external_id, route_number, transport_type, route_name, direction, color),
    )
    db.commit()
    cur = db.execute("SELECT id FROM routes WHERE external_id = ?", (external_id,))
    return cur.fetchone()["id"]


def upsert_route_stop(route_external_id: str, stop_external_id: str,
                      sequence: int, travel_time_min: Optional[float] = None,
                      distance_m: Optional[float] = None) -> bool:
    """
    Вставить или обновить связь маршрут-остановка.
    Возвращает True если запись сохранена, False если маршрут или остановка не найдены.
    """
    db = get_db()
    route_row = db.execute(
        "SELECT id FROM routes WHERE external_id = ?", (route_external_id,)
    ).fetchone()
    stop_row = db.execute(
        "SELECT id FROM stops WHERE external_id = ?", (stop_external_id,)
    ).fetchone()

    if not route_row or not stop_row:
        return False

    db.execute(
        "INSERT INTO route_stops (route_id, stop_id, stop_sequence, travel_time_min, distance_m) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(route_id, stop_sequence) DO UPDATE SET "
        "stop_id=excluded.stop_id, "
        "travel_time_min=excluded.travel_time_min, distance_m=excluded.distance_m",
        (route_row["id"], stop_row["id"], sequence, travel_time_min, distance_m),
    )
    return True

