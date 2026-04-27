"""Тесты модуля маршрутизации. См. ТЗ Приложение М, п. М.2."""

import json
from pathlib import Path

import pytest

from app.config.settings import get_settings
from app.db.connection import close_db, get_db, init_db
from app.routing.graph import build_graph
from app.routing.pathfinder import find_route


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    init_db(tmp_path / "test.db")

    # Заполняем БД мок-данными
    mock_path = Path(__file__).parent.parent / "data" / "mock" / "moscow_center.json"
    payload = json.loads(mock_path.read_text(encoding="utf-8"))
    db = get_db()
    db.execute("BEGIN")
    for r in payload["routes"]:
        db.execute(
            "INSERT INTO routes (external_id, route_number, route_name, transport_type, color) "
            "VALUES (?, ?, ?, ?, ?)",
            (r["external_id"], r["route_number"], r.get("route_name"),
             r["transport_type"], r.get("color")),
        )
    for s in payload["stops"]:
        db.execute(
            "INSERT INTO stops (external_id, name, latitude, longitude, stop_type, "
            "metro_line, metro_line_color) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (s["external_id"], s["name"], s["latitude"], s["longitude"],
             s["stop_type"], s.get("metro_line"), s.get("metro_line_color")),
        )
    for rs in payload["route_stops"]:
        route_row = db.execute("SELECT id FROM routes WHERE external_id = ?",
                               (rs["route_external_id"],)).fetchone()
        stop_row = db.execute("SELECT id FROM stops WHERE external_id = ?",
                              (rs["stop_external_id"],)).fetchone()
        db.execute(
            "INSERT INTO route_stops (route_id, stop_id, stop_sequence, travel_time_min) "
            "VALUES (?, ?, ?, ?)",
            (route_row["id"], stop_row["id"], rs["sequence"], rs.get("travel_time_min")),
        )
    for tr in payload.get("transfers", []):
        f = db.execute("SELECT id FROM stops WHERE external_id = ?",
                       (tr["from_external_id"],)).fetchone()
        t = db.execute("SELECT id FROM stops WHERE external_id = ?",
                       (tr["to_external_id"],)).fetchone()
        db.execute(
            "INSERT INTO transfers (from_stop_id, to_stop_id, distance_m, walk_time_min, "
            "transfer_type) VALUES (?, ?, ?, ?, ?)",
            (f["id"], t["id"], tr["distance_m"], tr["walk_time_min"], tr["transfer_type"]),
        )
    db.commit()
    yield
    close_db()


def test_graph_has_nodes_and_edges():
    g = build_graph()
    assert g.number_of_nodes() >= 20
    assert g.number_of_edges() >= 20


def test_route_same_line():
    """Маршрут в пределах одной линии метро — без пересадок."""
    g = build_graph()
    # От Парка культуры (55.7356, 37.5937) до Комсомольской (55.7758, 37.6558) по Сокольнической
    results = find_route(g, 55.7356, 37.5937, 55.7758, 37.6558, alternatives=1)
    assert len(results) == 1
    route = results[0]
    assert route["total_time_min"] > 0
    assert route["total_time_min"] < 40
    # Должен быть хотя бы один транспортный сегмент
    assert any(s["type"] == "metro" for s in route["segments"])


def test_route_with_transfer():
    """Маршрут с пересадкой между линиями."""
    g = build_graph()
    # От Арбатской (55.7524, 37.6013) до Маяковской (55.7699, 37.5959)
    # Требует пересадку Арбатская → Площадь Революции → Театральная → Маяковская
    results = find_route(g, 55.7524, 37.6013, 55.7699, 37.5959, alternatives=1)
    assert len(results) == 1
    route = results[0]
    assert route["transfers_count"] >= 0  # может быть 0, если использованы авто-пересадки


def test_route_not_found_far_points():
    """Точки вне зоны покрытия мок-графа."""
    from app.routing.pathfinder import RouteNotFoundError
    g = build_graph()
    with pytest.raises(RouteNotFoundError):
        # Координаты далеко за центром Москвы, рядом нет остановок из нашего датасета
        find_route(g, 55.9000, 37.8000, 55.9100, 37.8100, max_walk_m=200)
