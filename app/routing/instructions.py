"""
Формирование пошаговых текстовых инструкций на русском языке.
Соответствует ТЗ п. 4.3.3 и Приложению Е, п. Е.4.
"""

from typing import List

TRANSPORT_NAMES = {
    "bus": "автобус",
    "trolleybus": "троллейбус",
    "tram": "трамвай",
    "metro": "метро",
}


def build_instructions(segments: List[dict]) -> List[str]:
    """Преобразовать сегменты маршрута в список пошаговых инструкций.

    Шаблоны инструкций — см. ТЗ п. Е.4.
    """
    steps: List[str] = []
    for i, seg in enumerate(segments):
        steps.extend(_segment_steps(seg, is_first=i == 0, is_last=i == len(segments) - 1))
    return steps


def _segment_steps(seg: dict, is_first: bool = False, is_last: bool = False) -> List[str]:
    t = seg["type"]
    duration = int(round(seg["duration_min"]))
    distance = int(round(seg["distance_m"]))

    if t == "walk":
        if is_first:
            return [f"Пройдите {distance} м до остановки «{seg['to_stop_name']}» ({duration} мин)."]
        if is_last:
            return [f"Пройдите {distance} м до точки назначения ({duration} мин)."]
        return [f"Пройдите {distance} м до «{seg['to_stop_name']}» ({duration} мин)."]

    if t == "transfer":
        return [f"Перейдите на остановку «{seg['to_stop_name']}» ({distance} м, {duration} мин пешком)."]

    # Транспортный сегмент (bus / trolleybus / tram / metro)
    transport_name = TRANSPORT_NAMES.get(t, t)
    route = seg.get("route_number") or ""
    stops_n = seg["stops_count"]

    if t == "metro":
        # Для метро: «Сядьте в метро на станции X, проезжайте N перегонов до Y»
        return [
            f"Сядьте в метро на станции «{seg['from_stop_name']}».",
            f"Проезжайте {stops_n} {_perstops(stops_n)} до станции «{seg['to_stop_name']}» ({duration} мин).",
        ]

    # Наземный транспорт
    head = f"Сядьте на {transport_name}"
    if route:
        head += f" № {route}"
    return [
        f"{head} на остановке «{seg['from_stop_name']}».",
        f"Проезжайте {stops_n} {_perstops(stops_n)} до «{seg['to_stop_name']}» ({duration} мин).",
        f"Выйдите на остановке «{seg['to_stop_name']}».",
    ]


def _perstops(n: int) -> str:
    """Склонение «остановка» по числительному."""
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20:
        return "остановок"
    if 1 < n1 < 5:
        return "остановки"
    if n1 == 1:
        return "остановку"
    return "остановок"


# TODO: Здесь планируется поддержка английского языка с выносом шаблонов в файлы локализации.
# См. ТЗ п. 4.3.3.3.
