// ИС «МосТранспорт» — основная оркестрация клиентской подсистемы. См. ТЗ п. 4.1.3.

(function () {
  const state = {
    from: null,  // { lat, lon, label }
    to: null,
  };

  function init() {
    MapController.init();

    // Ввод с автодополнением
    const debounced = UI.debounce(onGeocodeInput, 300);
    document.getElementById("from-input").addEventListener("input", (e) => debounced("from", e.target.value));
    document.getElementById("to-input").addEventListener("input", (e) => debounced("to", e.target.value));

    // Скрывать подсказки при клике вне
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".input-wrap")) {
        document.querySelectorAll(".suggestions").forEach((s) => s.classList.remove("visible"));
      }
    });

    // Кнопки
    document.getElementById("build-btn").addEventListener("click", buildRoute);
    document.getElementById("clear-btn").addEventListener("click", clearAll);
    document.getElementById("swap-btn").addEventListener("click", swap);

    // Контекстное меню карты
    window._mtHandleMapContext = (latlng) => {
      const choice = confirm("ОК = маршрут ОТСЮДА, Отмена = маршрут СЮДА");
      if (choice) setEndpoint("from", latlng.lat, latlng.lng, "Точка на карте");
      else setEndpoint("to", latlng.lat, latlng.lng, "Точка на карте");
    };

    // Проверка доступности API
    API.health().then((h) => {
      if (h && h.graph_nodes === 0) {
        UI.showToast("База данных пуста. Загрузите мок-датасет: python manage.py load_mock", "error");
      }
    }).catch(() => {});
  }

  async function onGeocodeInput(which, query) {
    if (!query || query.length < 3) return;
    try {
      const data = await API.geocode(query, 5);
      const items = (data?.results || []).map((r) => ({
        name: _shortName(r.name),
        display_name: r.display_name,
        lat: r.lat,
        lon: r.lon,
      }));
      UI.showSuggestions(which, items, (picked) => {
        setEndpoint(which, picked.lat, picked.lon, picked.name);
      });
    } catch (e) {
      // Геокодер недоступен — молча игнорируем
    }
  }

  function setEndpoint(which, lat, lon, label) {
    state[which] = { lat, lon, label };
    UI.setInputValue(which, label);
    MapController.setEndpoint(which, [lat, lon]);
    MapController.centerOn(lat, lon, 14);
  }

  async function buildRoute() {
    if (!state.from || !state.to) {
      UI.showToast("Укажите начальную и конечную точки", "error");
      return;
    }
    UI.showLoading(true);
    try {
      const data = await API.buildRoute(state.from.lat, state.from.lon, state.to.lat, state.to.lon);
      if (!data || !data.routes || data.routes.length === 0) {
        UI.showToast("Маршрут не найден", "error");
        return;
      }
      const best = data.routes[0];
      MapController.drawRoute(best);
      UI.renderResult(best);
    } catch (e) {
      UI.showToast(e.message || "Ошибка построения маршрута", "error");
    } finally {
      UI.showLoading(false);
    }
  }

  function clearAll() {
    state.from = state.to = null;
    UI.setInputValue("from", "");
    UI.setInputValue("to", "");
    MapController.setEndpoint("from", null);
    MapController.setEndpoint("to", null);
    MapController.clearRoute();
    UI.clearResult();
  }

  function swap() {
    const a = state.from, b = state.to;
    state.from = b;
    state.to = a;
    UI.setInputValue("from", b?.label || "");
    UI.setInputValue("to", a?.label || "");
    MapController.setEndpoint("from", b ? [b.lat, b.lon] : null);
    MapController.setEndpoint("to", a ? [a.lat, a.lon] : null);
    if (state.from && state.to) buildRoute();
  }

  function _shortName(full) {
    if (!full) return "";
    const parts = full.split(",").map((s) => s.trim());
    return parts.slice(0, 2).join(", ");
  }

  // TODO: Здесь планируется отображение альтернативных маршрутов в виде вкладок
  // (см. ТЗ п. Ж.2). Сейчас показывается только первый вариант из списка routes.

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
