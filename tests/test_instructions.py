"""Тесты формирования текстовых инструкций. См. ТЗ Приложение М, п. М.2."""

from app.routing.instructions import _perstops, build_instructions


def test_perstops_declension():
    assert _perstops(1) == "остановку"
    assert _perstops(2) == "остановки"
    assert _perstops(5) == "остановок"
    assert _perstops(11) == "остановок"
    assert _perstops(21) == "остановку"


def test_instructions_for_metro_segment():
    seg = {
        "type": "metro",
        "route_number": "1",
        "from_stop_name": "Парк культуры",
        "to_stop_name": "Комсомольская",
        "duration_min": 14,
        "distance_m": 6000,
        "stops_count": 7,
    }
    steps = build_instructions([seg])
    assert any("метро" in s.lower() for s in steps)
    assert any("Парк культуры" in s for s in steps)
    assert any("Комсомольская" in s for s in steps)


def test_instructions_for_walk_segment():
    seg = {
        "type": "walk",
        "from_stop_name": None,
        "to_stop_name": "Метро Охотный Ряд",
        "duration_min": 5,
        "distance_m": 400,
        "stops_count": 1,
    }
    steps = build_instructions([seg])
    assert len(steps) == 1
    assert "Пройдите" in steps[0]
