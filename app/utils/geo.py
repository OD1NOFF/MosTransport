"""
Географические утилиты: формула гаверсинуса, работа с координатами.
Соответствует ТЗ Приложение А (формула гаверсинуса).
"""

import math
from typing import Tuple

EARTH_RADIUS_M = 6_371_000  # средний радиус Земли в метрах

# Средние скорости транспорта (км/ч), см. ТЗ Приложение Е, п. Е.1
TRANSPORT_SPEEDS = {
    "bus": 18,
    "trolleybus": 16,
    "tram": 15,
    "metro": 40,
    "walk": 4.5,
}

# Границы Москвы для фильтрации по bounding box
MOSCOW_BOUNDS = {
    "lat_min": 55.0, "lat_max": 56.5,
    "lon_min": 36.0, "lon_max": 38.5,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расчёт расстояния между двумя точками на сфере по формуле гаверсинуса.

    Аргументы в градусах (WGS84). Возвращает расстояние в метрах.
    Точность — не хуже 0.5% на расстояниях в пределах города.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def travel_time_min(distance_m: float, transport: str) -> float:
    """Расчёт времени в пути в минутах по расстоянию и типу транспорта."""
    speed_kmh = TRANSPORT_SPEEDS.get(transport, TRANSPORT_SPEEDS["walk"])
    return (distance_m / 1000.0) / speed_kmh * 60.0


def is_within_moscow(lat: float, lon: float) -> bool:
    """Проверка, что координата находится в пределах Москвы и ближайших пригородов."""
    return (MOSCOW_BOUNDS["lat_min"] <= lat <= MOSCOW_BOUNDS["lat_max"] and
            MOSCOW_BOUNDS["lon_min"] <= lon <= MOSCOW_BOUNDS["lon_max"])


def bounding_box(lat: float, lon: float, radius_m: float) -> Tuple[float, float, float, float]:
    """Ограничивающий прямоугольник для быстрой фильтрации по SQL.
    Возвращает (lat_min, lat_max, lon_min, lon_max).
    Используется в связке с haversine_distance для двухэтапного поиска (см. ТЗ п. 4.3.1, шаг 1).
    """
    lat_delta = radius_m / 111_000  # ~111 км на градус широты
    lon_delta = radius_m / (111_000 * max(math.cos(math.radians(lat)), 0.01))
    return (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta)
