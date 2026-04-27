"""
Модуль конфигурации. Загрузка параметров из .env-файла и переменных окружения.

Соответствует ТЗ п. 4.1.1, подсистема 5 (конфигурация) и Приложению И (развёртывание).
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Все параметры можно переопределить через .env или env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Приложение
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # База данных (SQLite, см. ТЗ п. 4.3.2.4)
    database_path: Path = Field(default=Path("data/mostransport.db"))

    # API data.mos.ru (см. ТЗ Приложение К, п. К.2)
    # ВАЖНО: ключ не коммитится в git. Задавать через .env или переменную окружения.
    datamos_api_key: str = Field(default="", description="API-ключ портала data.mos.ru")
    datamos_base_url: str = "https://apidata.mos.ru/v1"

    # API Мосгортранса (см. ТЗ Приложение К, п. К.1)
    # TODO: Здесь планируется интеграция с API Мосгортранса после получения ключа.
    mosgortrans_api_key: str = Field(default="")
    mosgortrans_base_url: str = "https://transport.mos.ru/api"

    # Nominatim (см. ТЗ Приложение К, п. К.4)
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "MosTransport/0.1 (educational project, MAI)"

    # Параметры маршрутизации (см. ТЗ п. 4.2.2)
    max_walk_distance_m: int = 800
    max_alternative_routes: int = 3
    route_cache_size: int = 1000
    geocode_cache_size: int = 1000

    # Ограничение частоты запросов (см. ТЗ п. 4.4.10.3)
    rate_limit_per_minute: int = 60

    # CORS
    cors_origins: List[str] = ["*"]

    # Логирование
    log_level: str = "INFO"
    log_file: Path = Field(default=Path("logs/app.log"))


@lru_cache
def get_settings() -> Settings:
    """Получить настройки приложения (кэшируется)."""
    return Settings()
