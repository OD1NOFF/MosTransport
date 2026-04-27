"""
Клиент Nominatim для геокодирования адресов.
Соответствует ТЗ п. 4.4 и Приложению К, п. К.4.
"""

from functools import lru_cache
from typing import List

import httpx

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Bounding box Москвы (см. ТЗ п. 4.4)
MOSCOW_VIEWBOX = "36.803,55.489,37.968,56.009"


async def geocode_query(query: str, limit: int = 5) -> List[dict]:
    """Преобразовать адрес в координаты. Ограничено территорией Москвы."""
    cached = _cache_get(query.strip().lower(), limit)
    if cached is not None:
        return cached

    settings = get_settings()
    url = f"{settings.nominatim_base_url}/search"
    params = {
        "q": query,
        "countrycodes": "ru",
        "viewbox": MOSCOW_VIEWBOX,
        "bounded": 1,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1,
    }
    headers = {"User-Agent": settings.nominatim_user_agent}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    results = []
    for item in payload[:limit]:
        try:
            results.append({
                "name": item.get("display_name", ""),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "display_name": item.get("display_name"),
            })
        except (KeyError, ValueError):
            continue

    _cache_set(query.strip().lower(), limit, results)
    return results


# Простой in-memory LRU-кэш. В продакшене можно заменить на Redis.
_GEOCODE_CACHE: dict = {}
_GEOCODE_CACHE_ORDER: list = []


def _cache_get(query: str, limit: int):
    key = (query, limit)
    return _GEOCODE_CACHE.get(key)


def _cache_set(query: str, limit: int, value) -> None:
    key = (query, limit)
    max_size = get_settings().geocode_cache_size
    if key in _GEOCODE_CACHE:
        _GEOCODE_CACHE_ORDER.remove(key)
    elif len(_GEOCODE_CACHE) >= max_size:
        oldest = _GEOCODE_CACHE_ORDER.pop(0)
        _GEOCODE_CACHE.pop(oldest, None)
    _GEOCODE_CACHE[key] = value
    _GEOCODE_CACHE_ORDER.append(key)


# TODO: Здесь планируется предварительная нормализация запроса через словарь топонимов
# и pymorphy3 (см. ТЗ п. 4.3.2.5, 4.3.2.6).
