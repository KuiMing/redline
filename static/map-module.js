// Leaflet Map Module

let leafletMap = null;
let markerLayer = null;
let currentMarkers = new Map();

// Minimal color palette (expand later if needed)
const palette = {
  "紅軍": "#f04f56",
  "臺灣": "#3fb6ff",
  "香港": "#f472b6",
  "東洋": "#a78bfa",
  "北國": "#67e8f9",
  "南洋": "#22c55e",
  "印度": "#f59e0b",
  "天方": "#fb7185"
};

function factionColor(f) {
  return palette[f] || "#cbd5e1";
}

window.initLeaflet = function () {
  if (leafletMap) return;

  leafletMap = L.map('leafletMap', { preferCanvas: true });

  L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    { maxZoom: 19 }
  ).addTo(leafletMap);

  markerLayer = L.layerGroup().addTo(leafletMap);

  // Default view (East Asia focus)
  leafletMap.setView([35, 110], 4);

  window.leafletMap = leafletMap;
};

window.updateMap = function (state) {
  if (!leafletMap || !state || !state.players) return;

  markerLayer.clearLayers();
  currentMarkers.clear();

  // We expect backend to include town geo coords in state later.
  // For now, skip if not provided.
  if (!state.town_geo) return;

  Object.entries(state.town_geo).forEach(([name, geo]) => {
    const marker = L.circleMarker([geo.lat, geo.lon], {
      radius: 6,
      fillColor: factionColor(geo.controller),
      fillOpacity: 1,
      color: '#07111f',
      weight: 1
    }).addTo(markerLayer);

    marker.bindTooltip(`${name} (${geo.units || 0})`, {
      permanent: leafletMap.getZoom() >= 5,
      direction: 'top'
    });

    currentMarkers.set(name, marker);
  });
};
