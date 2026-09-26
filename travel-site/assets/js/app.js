async function loadTrips() {
  const res = await fetch("data/trips.json");
  const data = await res.json();
  return data.trips || [];
}

function countryFlags(codes) {
  return (codes || []).map(cc => {
    if (!cc || cc.length !== 2) return "";
    const points = [...cc.toUpperCase()].map(c => 127397 + c.charCodeAt(0));
    return String.fromCodePoint(...points);
  }).join(" ");
}

function formatDateRange(start, end) {
  if (!start) return "";
  const opts = { day: "numeric", month: "short", year: "numeric" };
  const s = new Date(start).toLocaleDateString("fr-FR", opts);
  const e = end ? new Date(end).toLocaleDateString("fr-FR", opts) : null;
  return e && e !== s ? `${s} — ${e}` : s;
}

function renderStats(trips) {
  const totalKm = trips.reduce((sum, t) => sum + (t.total_km || 0), 0);
  const totalPhotos = trips.reduce((sum, t) => sum + (t.photo_count || 0), 0);
  const countries = new Set(trips.flatMap(t => t.countries || []));
  const el = document.getElementById("hero-stats");
  el.innerHTML = `
    <div class="hero-stat"><span class="num">${trips.length}</span><span class="label">voyages</span></div>
    <div class="hero-stat"><span class="num">${totalKm.toLocaleString("fr-FR")} km</span><span class="label">parcourus</span></div>
    <div class="hero-stat"><span class="num">${countries.size}</span><span class="label">pays</span></div>
    <div class="hero-stat"><span class="num">${totalPhotos}</span><span class="label">photos</span></div>
  `;
}

function renderGrid(trips) {
  const grid = document.getElementById("trip-grid");
  if (!trips.length) {
    grid.innerHTML = `<p style="color:var(--ink-faint)">Aucun voyage pour l'instant.</p>`;
    return;
  }
  grid.innerHTML = trips.map(t => `
    <a class="trip-card" href="voyages/${encodeURIComponent(t.slug)}.html">
      <div class="cover">
        ${t.cover ? `<img src="${t.cover.thumb}" alt="${t.name}" loading="lazy">` : ""}
      </div>
      <div class="body">
        <div class="dates">${formatDateRange(t.start_date, t.end_date)}</div>
        <h2>${t.name}</h2>
        <p class="summary">${t.summary || ""}</p>
        <div class="meta">
          <span>${countryFlags(t.countries)}</span>
          <span>${t.total_km ? t.total_km.toLocaleString("fr-FR") + " km" : ""}</span>
          <span>${t.step_count} étapes</span>
        </div>
      </div>
    </a>
  `).join("");
}

async function renderHeroMap(trips) {
  const map = L.map("hero-map", {
    zoomControl: false,
    dragging: true,
    scrollWheelZoom: false,
  }).setView([25, 10], 2);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    subdomains: "abc",
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const markers = [];
  for (const t of trips) {
    try {
      const res = await fetch(`data/trips/${t.slug}.json`);
      const full = await res.json();
      const withCoords = full.steps.filter(s => s.lat && s.lon);
      withCoords.forEach(s => {
        const m = L.circleMarker([s.lat, s.lon], {
          radius: 4,
          className: "trip-pin",
          color: "#12211f",
          weight: 1,
          fillColor: "#d9a441",
          fillOpacity: 0.9,
        }).addTo(map);
        markers.push(m);
      });
    } catch (e) { /* voyage sans détail, on ignore */ }
  }
  if (markers.length) {
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.3));
  }
}

(async function init() {
  const trips = await loadTrips();
  renderStats(trips);
  renderGrid(trips);
  renderHeroMap(trips);
})();
