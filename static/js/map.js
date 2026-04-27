// ИС «МосТранспорт» — модуль работы с картой (Leaflet). См. ТЗ п. 4.6.2.

const MapController = (function () {
  const TRANSPORT_COLORS = {
    bus: "#1565C0",
    trolleybus: "#2E7D32",
    tram: "#C62828",
    metro: "#EF161E",
  };

  let map, routeLayers = [], markers = { from: null, to: null };

  function init() {
    map = L.map("map").setView([55.7558, 37.6176], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    map.on("contextmenu", (e) => {
      if (window._mtHandleMapContext) window._mtHandleMapContext(e.latlng);
    });

    return map;
  }

  function clearRoute() {
    routeLayers.forEach((l) => map.removeLayer(l));
    routeLayers = [];
  }

  function setEndpoint(which, latlng) {
    if (markers[which]) map.removeLayer(markers[which]);
    if (!latlng) return;
    const color = which === "from" ? "#1b7e3c" : "#c62828";
    markers[which] = L.marker(latlng, {
      icon: L.divIcon({
        className: "",
        iconSize: [22, 22],
        html: `<div style="background:${color};border:3px solid white;border-radius:50%;width:22px;height:22px;box-shadow:0 2px 6px rgba(0,0,0,0.3)"></div>`,
      }),
    }).addTo(map);
  }

  function drawRoute(route) {
    clearRoute();
    const allPoints = [];

    route.segments.forEach((seg) => {
      if (!seg.geometry || seg.geometry.length < 2) return;
      let color = "#666";
      let dashArray = null;
      let weight = 5;

      if (seg.type === "metro") {
        color = seg.color || "#555";
        weight = 6;
      } else if (TRANSPORT_COLORS[seg.type]) {
        color = TRANSPORT_COLORS[seg.type];
      } else if (seg.type === "transfer") {
        color = "#888";
        dashArray = "6,6";
      } else if (seg.type === "walk") {
        color = "#555";
        dashArray = "4,8";
        weight = 3;
      }

      const poly = L.polyline(seg.geometry, { color, weight, opacity: 0.9, dashArray }).addTo(map);
      routeLayers.push(poly);
      seg.geometry.forEach((p) => allPoints.push(p));
    });

    if (allPoints.length > 0) {
      map.fitBounds(allPoints, { padding: [60, 60] });
    }
  }

  function centerOn(lat, lon, zoom = 15) {
    map.setView([lat, lon], zoom);
  }

  return { init, clearRoute, setEndpoint, drawRoute, centerOn };
})();
