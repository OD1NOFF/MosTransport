"""
Настройка структурированного логирования.
Соответствует ТЗ п. 4.1.5.1 (логирование).
"""

import logging
import sys
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с настроенным форматом.

    Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    В рабочем режиме — INFO, при диагностике — DEBUG.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный вывод
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # TODO: Здесь планируется добавить файловый обработчик с ротацией (TimedRotatingFileHandler)
    # и отдельный поток для отправки CRITICAL в внешнюю систему мониторинга.
    # См. ТЗ п. 4.1.5.2 (программный мониторинг ИС).

    return logger
