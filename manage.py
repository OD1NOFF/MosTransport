"""
CLI-утилита администратора ИС «МосТранспорт».
Соответствует ТЗ п. 4.2.5 (подсистема администрирования).

Использование:
    python manage.py init_db           — инициализация БД
    python manage.py load_mock         — загрузка учебного датасета
    python manage.py update_data       — обновление из внешних источников
    python manage.py health            — проверка состояния
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.config.settings import get_settings
from app.data.updater import update_all_data
from app.db.connection import init_db
from app.utils.logger import get_logger

logger = get_logger(__name__)


def cmd_init_db(_: argparse.Namespace) -> int:
    settings = get_settings()
    init_db(settings.database_path)
    print(f"База данных инициализирована: {settings.database_path}")
    return 0


def cmd_load_mock(_: argparse.Namespace) -> int:
    """Загрузить учебный мок-датасет (центр Москвы)."""
    settings = get_settings()
    init_db(settings.database_path)

    mock_file = Path(__file__).parent / "data" / "mock" / "moscow_center.json"
    if not mock_file.exists():
        print(f"ОШИБКА: файл {mock_file} не найден", file=sys.stderr)
        return 1

    from app.db.connection import get_db
    payload = json.loads(mock_file.read_text(encoding="utf-8"))

    db = get_db()
    db.execute("BEGIN")
    try:
        # Маршруты
        for r in payload["routes"]:
            db.execute(
                "INSERT INTO routes (external_id, route_number, route_name, transport_type, color) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(external_id) DO NOTHING",
                (r["external_id"], r["route_number"], r.get("route_name"),
                 r["transport_type"], r.get("color")),
            )

        # Остановки
        for s in payload["stops"]:
            db.execute(
                "INSERT INTO stops (external_id, name, latitude, longitude, stop_type, "
                "metro_line, metro_line_color) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(external_id) DO NOTHING",
                (s["external_id"], s["name"], s["latitude"], s["longitude"],
                 s["stop_type"], s.get("metro_line"), s.get("metro_line_color")),
            )

        # Связи маршрут-остановка
        for rs in payload["route_stops"]:
            route_row = db.execute(
                "SELECT id FROM routes WHERE external_id = ?", (rs["route_external_id"],)
            ).fetchone()
            stop_row = db.execute(
                "SELECT id FROM stops WHERE external_id = ?", (rs["stop_external_id"],)
            ).fetchone()
            if not route_row or not stop_row:
                continue
            db.execute(
                "INSERT INTO route_stops (route_id, stop_id, stop_sequence, travel_time_min) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(route_id, stop_sequence) DO NOTHING",
                (route_row["id"], stop_row["id"], rs["sequence"], rs.get("travel_time_min")),
            )

        # Пересадки
        for tr in payload.get("transfers", []):
            f = db.execute("SELECT id FROM stops WHERE external_id = ?",
                           (tr["from_external_id"],)).fetchone()
            t = db.execute("SELECT id FROM stops WHERE external_id = ?",
                           (tr["to_external_id"],)).fetchone()
            if not f or not t:
                continue
            db.execute(
                "INSERT INTO transfers (from_stop_id, to_stop_id, distance_m, walk_time_min, "
                "transfer_type) VALUES (?, ?, ?, ?, ?)",
                (f["id"], t["id"], tr["distance_m"], tr["walk_time_min"], tr["transfer_type"]),
            )

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"ОШИБКА загрузки: {e}", file=sys.stderr)
        return 1

    print(f"Загружено: маршрутов={len(payload['routes'])}, "
          f"остановок={len(payload['stops'])}, "
          f"связей={len(payload['route_stops'])}, "
          f"пересадок={len(payload.get('transfers', []))}")
    return 0


def cmd_update_data(_: argparse.Namespace) -> int:
    settings = get_settings()
    init_db(settings.database_path)
    result = asyncio.run(update_all_data())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


def cmd_health(_: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        init_db(settings.database_path)
    except Exception as e:
        print(f"БД недоступна: {e}")
        return 1
    print(f"OK. БД: {settings.database_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ИС «МосТранспорт» — утилита администратора")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init_db", help="инициализировать БД")
    p_init.set_defaults(func=cmd_init_db)

    p_mock = sub.add_parser("load_mock", help="загрузить учебный датасет")
    p_mock.set_defaults(func=cmd_load_mock)

    p_upd = sub.add_parser("update_data", help="обновить данные из внешних источников")
    p_upd.set_defaults(func=cmd_update_data)

    p_h = sub.add_parser("health", help="проверить состояние системы")
    p_h.set_defaults(func=cmd_health)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
