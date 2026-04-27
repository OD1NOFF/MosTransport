// ИС «МосТранспорт» — модуль взаимодействия с API. См. ТЗ п. 4.1.3.
// Инкапсулирует все HTTP-запросы, обработку ошибок и форматирование URL.

const API = (function () {
  const BASE = "/api/v1";

  async function request(path, params = {}) {
    const url = new URL(BASE + path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });

    const resp = await fetch(url.toString());
    const payload = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      const msg = payload?.error?.message || payload?.detail || `HTTP ${resp.status}`;
      const err = new Error(msg);
      err.status = resp.status;
      err.code = payload?.error?.code || payload?.detail?.code;
      throw err;
    }

    if (payload && payload.success === false) {
      const err = new Error(payload.error?.message || "Неизвестная ошибка API");
      err.code = payload.error?.code;
      throw err;
    }

    return payload.data;
  }

  return {
    buildRoute(fromLat, fromLon, toLat, toLon, opts = {}) {
      return request("/route", {
        from_lat: fromLat, from_lon: fromLon,
        to_lat: toLat, to_lon: toLon,
        alternatives: opts.alternatives || 1,
        max_walk_m: opts.maxWalkM || 800,
      });
    },
    geocode(q, limit = 5) {
      return request("/geocode", { q, limit });
    },
    stopDetails(id) {
      return request(`/stops/${id}`);
    },
    nearbyStops(lat, lon, radiusM = 500) {
      return request("/stops/nearby", { lat, lon, radius_m: radiusM });
    },
    health() {
      return request("/health");
    },
  };
})();
