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

    Каждый сегмент — уже схлопнутый участок (один транспорт от A до B).
    Шаблоны инструкций — см. ТЗ п. Е.4.
    """
    steps: List[str] = []
    for i, seg in enumerate(segments):
        steps.extend(_segment_steps(seg, is_first=(i == 0), is_last=(i == len(segments) - 1)))
    return steps


def _segment_steps(seg: dict, is_first: bool = False, is_last: bool = False) -> List[str]:
    t = seg["type"]
    duration = int(round(seg["duration_min"]))
    distance = int(round(seg["distance_m"]))

    # ── Пешком ───────────────────────────────────────────────────────────────
    if t == "walk":
        to_name = seg.get("to_stop_name") or "остановке"
        if is_first:
            return [f"Пройдите {distance} м до остановки «{to_name}» ({duration} мин)."]
        if is_last:
            return [f"Пройдите {distance} м до точки назначения ({duration} мин)."]
        return [f"Пройдите {distance} м до остановки «{to_name}» ({duration} мин)."]

    # ── Пересадка ─────────────────────────────────────────────────────────────
    if t == "transfer":
        to_name = seg.get("to_stop_name") or "следующей остановке"
        return [f"Перейдите на остановку «{to_name}» ({distance} м, {duration} мин пешком)."]

    # ── Транспортный сегмент (bus / trolleybus / tram / metro) ───────────────
    # stops_count = количество перегонов (рёбер), т.е. остановок минус одна
    transport_name = TRANSPORT_NAMES.get(t, t)
    route = _clean_route_number(seg.get("route_number") or "")
    stops_n = seg.get("stops_count", 1)
    from_name = seg.get("from_stop_name") or "остановке"
    to_name = seg.get("to_stop_name") or "остановке"

    if t == "metro":
        return [
            f"Сядьте в метро на станции «{from_name}».",
            f"Ехать до станции «{to_name}» ({duration} мин).",
            # f"Выйдите на станции «{to_name}».",
        ]

    # Наземный транспорт
    head = f"Сядьте на {transport_name}"
    if route:
        head += f" № {route}"

    # stops_count ненадёжен из-за данных API — показываем время
    return [
        f"{head} на остановке «{from_name}».",
        f"Ехать до остановки «{to_name}» ({duration} мин).",
        # f"Выйдите на остановке «{to_name}».",
    ]


def _clean_route_number(route: str) -> str:
    """Убрать лишние префиксы из номера маршрута.

    data.mos.ru возвращает номера вида 'А270', 'Ас591', 'Тб10'.
    Для отображения пассажиру достаточно числовой части или короткого кода.
    Примеры: 'А270' → '270', 'Ас532' → '532', 'Тб10' → 'Тб10', 'м1' → 'м1'.
    """
    if not route:
        return route
    # Если номер начинается с кириллических букв и затем идут цифры — убираем буквы-префикс.
    # Исключение: номера типа 'м1', 'С1', 'МЦД' — короткие значимые коды.
    import re
    m = re.match(r'^[А-ЯЁа-яёA-Za-z]{1,2}(\d+.*)$', route)
    if m:
        return m.group(1)
    return route


def _perstops(n: int) -> str:
    """Склонение слова «остановка» по числительному."""
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