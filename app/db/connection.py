"""
Управление подключением к SQLite.
Соответствует ТЗ п. 4.3.2.4.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

_connection: Optional[sqlite3.Connection] = None


def init_db(db_path: Path) -> sqlite3.Connection:
    """Инициализировать БД: создать файл (если отсутствует) и применить схему."""
    global _connection
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _connection = sqlite3.connect(str(db_path), check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA foreign_keys = ON")
    _connection.execute("PRAGMA journal_mode = WAL")  # лучше для одновременного чтения

    schema_path = Path(__file__).parent / "schema.sql"
    with schema_path.open("r", encoding="utf-8") as f:
        _connection.executescript(f.read())
    _connection.commit()

    return _connection


def get_db() -> sqlite3.Connection:
    """Получить текущее соединение с БД."""
    if _connection is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db() при старте приложения.")
    return _connection


def close_db() -> None:
    """Закрыть соединение с БД. Вызывается при остановке приложения."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.info("Соединение с БД закрыто")


# TODO: Здесь планируется миграция на PostgreSQL + PostGIS (см. ТЗ п. 4.3.2.4).
# Для этого следует перейти на SQLAlchemy с асинхронным драйвером asyncpg
# и реализовать alembic-миграции.
