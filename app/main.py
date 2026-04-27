"""
ИС «МосТранспорт» — навигация по маршрутам общественного транспорта Москвы.
Точка входа FastAPI-приложения.

Документ-источник: Техническое задание ИС «МосТранспорт», п. 4.1.1 (подсистема 3).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import geocode, health, routes, stops
from app.config.settings import get_settings
from app.db.connection import close_db, init_db
from app.routing.graph import build_graph
from app.utils.logger import get_logger
from app.api import debug


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения. При старте — инициализация БД и построение графа.
    При остановке — корректное закрытие соединений."""
    settings = get_settings()
    logger.info("Запуск ИС «МосТранспорт» v%s", settings.app_version)

    init_db(settings.database_path)
    logger.info("База данных инициализирована: %s", settings.database_path)

    # Построение транспортного графа (подсистема 2, см. ТЗ п. 4.1.1)
    graph = build_graph()
    app.state.graph = graph
    logger.info("Транспортный граф построен: %d вершин, %d рёбер",
                graph.number_of_nodes(), graph.number_of_edges())

    # TODO: Здесь планируется запуск фоновой задачи ежедневного обновления данных
    # (cron 03:00 МСК, см. ТЗ п. 4.5.3). Использовать apscheduler или celery.

    yield

    logger.info("Остановка приложения")
    close_db()


settings = get_settings()

app = FastAPI(
    title="ИС «МосТранспорт»",
    description="Навигация по маршрутам общественного транспорта Москвы",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Подключение роутеров (подсистема 3: серверное API)
app.include_router(routes.router, prefix="/api/v1", tags=["routes"])
app.include_router(stops.router, prefix="/api/v1", tags=["stops"])
app.include_router(geocode.router, prefix="/api/v1", tags=["geocode"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(debug.router, prefix="/api/v1", tags=["debug"])

# Подключение клиентской подсистемы (веб-интерфейс, см. ТЗ п. 4.1.1, подсистема 4)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
