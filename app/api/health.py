"""
Health check эндпоинт.
См. ТЗ п. 4.1.5.2 и Приложение Г, п. Г.6.
"""

import time
from datetime import datetime

from fastapi import APIRouter, Request

from app.api.models import ApiResponse, HealthStatus
from app.config.settings import get_settings
from app.db.connection import get_db

router = APIRouter()
_START_TIME = time.time()


@router.get("/health", response_model=ApiResponse)
async def health_check(request: Request):
    """Проверка состояния компонентов системы."""
    settings = get_settings()
    overall = "ok"

    # Состояние БД
    try:
        get_db().execute("SELECT 1").fetchone()
        db_status = "ok"
    except Exception:
        db_status = "error"
        overall = "error"

    graph = getattr(request.app.state, "graph", None)
    nodes = graph.number_of_nodes() if graph is not None else 0
    edges = graph.number_of_edges() if graph is not None else 0
    if nodes == 0:
        overall = "degraded" if overall == "ok" else overall

    # TODO: Здесь планируется получать дату последнего обновления из таблицы data_updates.
    last_update = None

    status = HealthStatus(
        status=overall,
        database_status=db_status,
        graph_nodes=nodes,
        graph_edges=edges,
        last_data_update=last_update,
        uptime_seconds=int(time.time() - _START_TIME),
        version=settings.app_version,
    )
    return ApiResponse(success=True, data=status.model_dump())
