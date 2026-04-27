"""
Оркестрация процесса обновления данных из внешних источников.
Соответствует ТЗ п. 4.5.3 (процедура обновления).

Порядок работы:
1. Создать резервную копию БД.
2. Обратиться к каждому адаптеру (DataSource).
3. Валидировать данные (координаты в пределах Москвы, наличие обязательных полей).
4. Записать в БД в рамках транзакции (откат при ошибке).
5. Залогировать результат в таблицу data_updates.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from app.config.settings import get_settings
from app.data.base import DataSource, StopData
from app.data.datamos import DataMosDataSource
from app.data.mosgortrans import MosgortransDataSource
from app.data.osm import OsmDataSource
from app.db.connection import get_db
from app.db.repository import upsert_stop
from app.utils.geo import is_within_moscow
from app.utils.logger import get_logger

logger = get_logger(__name__)


def default_sources() -> List[DataSource]:
    """Список активных источников по умолчанию."""
    return [MosgortransDataSource(), DataMosDataSource(), OsmDataSource()]


async def update_all_data(sources: List[DataSource] | None = None) -> dict:
    """Обновить транспортные данные из всех источников. Возвращает отчёт."""
    settings = get_settings()
    sources = sources or default_sources()

    # 1) Резервная копия БД (см. ТЗ п. 4.3.2.7.1)
    _backup_database(settings.database_path)

    stops_total = 0
    routes_total = 0
    errors: List[str] = []

    # 2) Обход источников
    for src in sources:
        started = datetime.utcnow()
        _insert_update_log(src.name, "in_progress", started)
        try:
            stops = await src.fetch_stops()
            stops = _validate_stops(stops)
            _save_stops(stops)
            stops_total += len(stops)

            # Маршруты и связи реализуются аналогично по мере готовности адаптеров
            # TODO: Здесь планируется сохранение routes и route_stops после реализации
            # соответствующих методов в адаптерах.

            _finish_update_log(src.name, "success", started, len(stops), 0)
            logger.info("Источник %s: %d остановок загружено", src.name, len(stops))
        except Exception as e:
            errors.append(f"{src.name}: {e}")
            _finish_update_log(src.name, "failed", started, 0, 0, error=str(e))
            logger.error("Ошибка обновления из %s: %s", src.name, e)

    return {
        "sources": [s.name for s in sources],
        "stops_total": stops_total,
        "routes_total": routes_total,
        "errors": errors,
    }


def _validate_stops(stops: List[StopData]) -> List[StopData]:
    """Отфильтровать остановки с некорректными координатами или пустыми именами."""
    valid = []
    for s in stops:
        if not s.name or not s.external_id:
            continue
        if not is_within_moscow(s.latitude, s.longitude):
            continue
        valid.append(s)
    return valid


def _save_stops(stops: List[StopData]) -> None:
    """Сохранить остановки в БД в рамках одной транзакции."""
    db = get_db()
    try:
        db.execute("BEGIN")
        for s in stops:
            upsert_stop(s.external_id, s.name, s.latitude, s.longitude,
                        s.stop_type, s.metro_line, s.metro_line_color)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _backup_database(db_path: Path) -> None:
    """Создать резервную копию файла БД."""
    if not db_path.exists():
        return
    backup_dir = db_path.parent / "backups" / "daily"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{db_path.stem}_{ts}{db_path.suffix}"
    shutil.copy2(db_path, target)
    logger.info("Создана резервная копия БД: %s", target)
    # TODO: Здесь планируется удаление устаревших копий (старше 7 дней).


def _insert_update_log(source: str, status: str, started: datetime) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO data_updates (started_at, status, source) VALUES (?, ?, ?)",
        (started.isoformat(), status, source),
    )
    db.commit()
    return cur.lastrowid


def _finish_update_log(source: str, status: str, started: datetime,
                       stops_n: int, routes_n: int, error: str = "") -> None:
    db = get_db()
    db.execute(
        "UPDATE data_updates SET finished_at = ?, status = ?, "
        "routes_updated = ?, stops_updated = ?, error_message = ? "
        "WHERE source = ? AND started_at = ?",
        (datetime.utcnow().isoformat(), status, routes_n, stops_n, error,
         source, started.isoformat()),
    )
    db.commit()
