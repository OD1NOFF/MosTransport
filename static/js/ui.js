// ИС «МосТранспорт» — модуль пользовательского интерфейса. См. ТЗ п. 4.6.

const UI = (function () {
  const TRANSPORT_LABELS = {
    bus: "Автобус",
    trolleybus: "Троллейбус",
    tram: "Трамвай",
    metro: "Метро",
    transfer: "Пересадка",
    walk: "Пешком",
  };

  function showLoading(visible) {
    document.getElementById("loading").classList.toggle("hidden", !visible);
  }

  function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3500);
  }

  function renderResult(route) {
    const panel = document.getElementById("result-panel");
    if (!route) {
      panel.classList.add("hidden");
      return;
    }

    const time = Math.round(route.total_time_min);
    const dist = (route.total_distance_m / 1000).toFixed(1);
    const transfers = route.transfers_count;

    let stepsHtml = "";
    route.steps.forEach((step, idx) => {
      const seg = route.segments[Math.min(idx, route.segments.length - 1)];
      const type = seg ? seg.type : "walk";
      const badgeText = _badgeText(seg);
      const badgeClass = ["metro", "bus", "tram", "trolleybus"].includes(type) ? type : "";
      const badgeStyle = type === "metro" && seg.color ? `background:${seg.color}` : "";
      stepsHtml += `
        <li>
          <span class="step-badge ${badgeClass}" style="${badgeStyle}">${badgeText}</span>
          <span class="step-text">${step}</span>
        </li>`;
    });

    panel.innerHTML = `
      <div class="route-summary">
        <div class="summary-item"><div class="label">Время</div><div class="value">${time} мин</div></div>
        <div class="summary-item"><div class="label">Расстояние</div><div class="value">${dist} км</div></div>
        <div class="summary-item"><div class="label">Пересадки</div><div class="value">${transfers}</div></div>
      </div>
      <ul class="route-steps">${stepsHtml}</ul>`;
    panel.classList.remove("hidden");
  }

  function _badgeText(seg) {
    if (!seg) return "·";
    if (seg.type === "metro") return "М";
    if (seg.type === "transfer") return "↔";
    if (seg.type === "walk") return "·";
    return seg.route_number || TRANSPORT_LABELS[seg.type]?.[0] || "·";
  }

  function setInputValue(which, text) {
    document.getElementById(`${which}-input`).value = text;
  }

  function showSuggestions(which, items, onPick) {
    const list = document.getElementById(`${which}-suggestions`);
    if (!items || items.length === 0) {
      list.classList.remove("visible");
      list.innerHTML = "";
      return;
    }
    list.innerHTML = "";
    items.forEach((it) => {
      const li = document.createElement("li");
      li.textContent = it.name || it.display_name;
      li.addEventListener("click", () => {
        onPick(it);
        list.classList.remove("visible");
      });
      list.appendChild(li);
    });
    list.classList.add("visible");
  }

  function clearResult() {
    document.getElementById("result-panel").classList.add("hidden");
  }

  function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  return {
    showLoading, showToast, renderResult, setInputValue,
    showSuggestions, clearResult, debounce,
  };
})();
