"""Проверка алгоритма маршрутизации на мок-датасете.
Не требует FastAPI и pydantic — использует только networkx и стандартную библиотеку.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import networkx as nx

from app.utils.geo import haversine_distance, travel_time_min

# Загрузка датасета
mock = json.loads((ROOT / "data/mock/moscow_center.json").read_text(encoding="utf-8"))

stops_by_ext = {s["external_id"]: s for s in mock["stops"]}

# Создаём in-memory БД и заполняем её
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
schema = (ROOT / "app/db/schema.sql").read_text(encoding="utf-8")
conn.executescript(schema)

# Вставка данных
for r in mock["routes"]:
    conn.execute(
        "INSERT INTO routes (external_id, route_number, route_name, transport_type, color) "
        "VALUES (?, ?, ?, ?, ?)",
        (r["external_id"], r["route_number"], r.get("route_name"), r["transport_type"], r.get("color")),
    )
for s in mock["stops"]:
    conn.execute(
        "INSERT INTO stops (external_id, name, latitude, longitude, stop_type, metro_line, metro_line_color) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (s["external_id"], s["name"], s["latitude"], s["longitude"], s["stop_type"],
         s.get("metro_line"), s.get("metro_line_color")),
    )
for rs in mock["route_stops"]:
    r = conn.execute("SELECT id FROM routes WHERE external_id=?", (rs["route_external_id"],)).fetchone()
    s = conn.execute("SELECT id FROM stops WHERE external_id=?", (rs["stop_external_id"],)).fetchone()
    conn.execute(
        "INSERT INTO route_stops (route_id, stop_id, stop_sequence, travel_time_min) VALUES (?, ?, ?, ?)",
        (r["id"], s["id"], rs["sequence"], rs.get("travel_time_min")),
    )
for tr in mock.get("transfers", []):
    f = conn.execute("SELECT id FROM stops WHERE external_id=?", (tr["from_external_id"],)).fetchone()
    t = conn.execute("SELECT id FROM stops WHERE external_id=?", (tr["to_external_id"],)).fetchone()
    conn.execute(
        "INSERT INTO transfers (from_stop_id, to_stop_id, distance_m, walk_time_min, transfer_type) "
        "VALUES (?, ?, ?, ?, ?)",
        (f["id"], t["id"], tr["distance_m"], tr["walk_time_min"], tr["transfer_type"]),
    )
conn.commit()

# Построение графа
g = nx.MultiDiGraph()

stops = [dict(r) for r in conn.execute(
    "SELECT id, external_id, name, latitude, longitude, stop_type, metro_line, metro_line_color "
    "FROM stops WHERE is_active = 1"
).fetchall()]
for s in stops:
    g.add_node(s["id"], **s)

routes = {r["id"]: dict(r) for r in conn.execute(
    "SELECT id, external_id, route_number, transport_type, color FROM routes WHERE is_active = 1"
).fetchall()}

by_route = {}
for x in conn.execute("SELECT route_id, stop_id, stop_sequence, travel_time_min FROM route_stops ORDER BY route_id, stop_sequence"):
    by_route.setdefault(x["route_id"], []).append(dict(x))

TRANSFER_PENALTY = 3.0
for route_id, entries in by_route.items():
    route = routes.get(route_id)
    if not route:
        continue
    entries.sort(key=lambda x: x["stop_sequence"])
    for i in range(len(entries) - 1):
        a, b = entries[i], entries[i + 1]
        t = float(b["travel_time_min"]) if b.get("travel_time_min") is not None else 2.0
        g.add_edge(a["stop_id"], b["stop_id"],
                   edge_type="transit",
                   route_id=route_id,
                   route_number=route["route_number"],
                   transport_type=route["transport_type"],
                   color=route.get("color"),
                   weight=t)
        # Обратное ребро
        g.add_edge(b["stop_id"], a["stop_id"],
                   edge_type="transit",
                   route_id=route_id,
                   route_number=route["route_number"],
                   transport_type=route["transport_type"],
                   color=route.get("color"),
                   weight=t)

for tr in conn.execute("SELECT from_stop_id, to_stop_id, walk_time_min FROM transfers"):
    g.add_edge(tr["from_stop_id"], tr["to_stop_id"], edge_type="transfer",
               weight=float(tr["walk_time_min"]) + TRANSFER_PENALTY)
    g.add_edge(tr["to_stop_id"], tr["from_stop_id"], edge_type="transfer",
               weight=float(tr["walk_time_min"]) + TRANSFER_PENALTY)

print(f"Граф: {g.number_of_nodes()} вершин, {g.number_of_edges()} рёбер")

# Тест 1: Парк культуры → Комсомольская (одна линия)
src = next(s["id"] for s in stops if s["external_id"] == "sok_parkkult")
dst = next(s["id"] for s in stops if s["external_id"] == "sok_komsomol")
path = nx.shortest_path(g, src, dst, weight="weight")
time = sum(min(g.get_edge_data(path[i], path[i+1]).values(), key=lambda e: e["weight"])["weight"]
           for i in range(len(path) - 1))
print(f"\nТест 1: Парк культуры → Комсомольская")
print(f"  Путь: {' → '.join(g.nodes[n]['name'] for n in path)}")
print(f"  Время: {time:.1f} мин")

# Тест 2: Парк культуры → Белорусская (требует пересадку)
src = next(s["id"] for s in stops if s["external_id"] == "sok_parkkult")
dst = next(s["id"] for s in stops if s["external_id"] == "zam_belorus")
path = nx.shortest_path(g, src, dst, weight="weight")
time = sum(min(g.get_edge_data(path[i], path[i+1]).values(), key=lambda e: e["weight"])["weight"]
           for i in range(len(path) - 1))
print(f"\nТест 2: Парк культуры → Белорусская (с пересадкой)")
print(f"  Путь: {' → '.join(g.nodes[n]['name'] for n in path)}")
print(f"  Время: {time:.1f} мин")

# Тест 3: Три альтернативных маршрута Киевская → Курская
src = next(s["id"] for s in stops if s["external_id"] == "arb_kievskaya")
dst = next(s["id"] for s in stops if s["external_id"] == "arb_kurskaya")
print(f"\nТест 3: Киевская → Курская ({3} альтернативы — запрошено)")
# MultiDiGraph не поддерживается Йеном — конвертируем в DiGraph
simple_g = nx.DiGraph()
for n, data in g.nodes(data=True):
    simple_g.add_node(n, **data)
for u, v, data in g.edges(data=True):
    if simple_g.has_edge(u, v):
        if data.get("weight", 999) < simple_g[u][v].get("weight", 999):
            simple_g[u][v].update(data)
    else:
        simple_g.add_edge(u, v, **data)

paths = []
for i, p in enumerate(nx.shortest_simple_paths(simple_g, src, dst, weight="weight")):
    if i >= 3:
        break
    paths.append(p)
for i, p in enumerate(paths, 1):
    time = sum(simple_g.get_edge_data(p[j], p[j+1])["weight"] for j in range(len(p) - 1))
    names = " → ".join(simple_g.nodes[n]["name"] for n in p)
    print(f"  Вариант {i}: {len(p)-1} перегонов, {time:.1f} мин")
    print(f"    {names}")

conn.close()
print("\n✓ Все тесты пройдены")
