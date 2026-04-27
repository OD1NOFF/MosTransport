"""Тесты утилит: формула гаверсинуса, bounding box, валидация координат."""

from app.utils.geo import (
    bounding_box,
    haversine_distance,
    is_within_moscow,
    travel_time_min,
)


def test_haversine_known_distance():
    # Расстояние между Красной площадью и ВДНХ ~9 км
    d = haversine_distance(55.7539, 37.6208, 55.8300, 37.6325)
    assert 8000 < d < 10000


def test_haversine_same_point():
    assert haversine_distance(55.0, 37.0, 55.0, 37.0) < 1.0


def test_travel_time_metro_faster_than_bus():
    d = 5000  # 5 км
    t_metro = travel_time_min(d, "metro")
    t_bus = travel_time_min(d, "bus")
    assert t_metro < t_bus


def test_is_within_moscow():
    assert is_within_moscow(55.7558, 37.6176)  # Кремль
    assert not is_within_moscow(60.0, 30.0)  # Петербург
    assert not is_within_moscow(0.0, 0.0)  # Экватор


def test_bounding_box_contains_point():
    lat, lon = 55.7558, 37.6176
    lat_min, lat_max, lon_min, lon_max = bounding_box(lat, lon, 500)
    assert lat_min < lat < lat_max
    assert lon_min < lon < lon_max
