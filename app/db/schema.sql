-- Схема базы данных ИС «МосТранспорт» (SQLite).
-- Соответствует ТЗ Приложение В (структура БД) и п. 4.3.2.

-- Таблица маршрутов общественного транспорта
CREATE TABLE IF NOT EXISTS routes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT UNIQUE NOT NULL,
    route_number    TEXT NOT NULL,
    route_name      TEXT,
    transport_type  TEXT NOT NULL CHECK(transport_type IN ('bus','trolleybus','tram','metro')),
    direction       TEXT,
    color           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Таблица остановок и станций
CREATE TABLE IF NOT EXISTS stops (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id       TEXT UNIQUE NOT NULL,
    name              TEXT NOT NULL,
    latitude          REAL NOT NULL,
    longitude         REAL NOT NULL,
    stop_type         TEXT NOT NULL CHECK(stop_type IN ('bus_stop','tram_stop','trolleybus_stop','metro_station')),
    metro_line        TEXT,
    metro_line_color  TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Связь маршрут-остановка (последовательность)
CREATE TABLE IF NOT EXISTS route_stops (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id          INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    stop_id           INTEGER NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    stop_sequence     INTEGER NOT NULL,
    travel_time_min   REAL,
    distance_m        REAL,
    UNIQUE(route_id, stop_sequence)
);

-- Расписания
CREATE TABLE IF NOT EXISTS schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id       INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    stop_id        INTEGER NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    departure_time TEXT NOT NULL,
    day_type       TEXT NOT NULL CHECK(day_type IN ('weekday','saturday','sunday')),
    headway_min    REAL
);

-- Пешеходные переходы и пересадки
CREATE TABLE IF NOT EXISTS transfers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    from_stop_id   INTEGER NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    to_stop_id     INTEGER NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    distance_m     REAL NOT NULL,
    walk_time_min  REAL NOT NULL,
    transfer_type  TEXT NOT NULL CHECK(transfer_type IN ('walking','underground'))
);

-- Журнал обновлений данных
CREATE TABLE IF NOT EXISTS data_updates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       DATETIME NOT NULL,
    finished_at      DATETIME,
    status           TEXT NOT NULL CHECK(status IN ('success','failed','in_progress')),
    source           TEXT NOT NULL,
    routes_updated   INTEGER NOT NULL DEFAULT 0,
    stops_updated    INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT
);

-- Словарь топонимов (см. ТЗ п. 4.3.2.6)
CREATE TABLE IF NOT EXISTS toponyms (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical        TEXT NOT NULL,
    normalized       TEXT NOT NULL,
    variant          TEXT NOT NULL,
    latitude         REAL,
    longitude        REAL,
    source           TEXT
);

-- Индексы для оптимизации поиска (см. ТЗ п. 4.3.2.1)
CREATE INDEX IF NOT EXISTS idx_stops_coords ON stops(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_stops_active ON stops(is_active);
CREATE INDEX IF NOT EXISTS idx_route_stops_route ON route_stops(route_id);
CREATE INDEX IF NOT EXISTS idx_route_stops_stop ON route_stops(stop_id);
CREATE INDEX IF NOT EXISTS idx_schedules_lookup ON schedules(route_id, stop_id, day_type);
CREATE INDEX IF NOT EXISTS idx_transfers_from ON transfers(from_stop_id);
CREATE INDEX IF NOT EXISTS idx_transfers_to ON transfers(to_stop_id);
CREATE INDEX IF NOT EXISTS idx_toponyms_normalized ON toponyms(normalized);
