function qs(name) {
  return new URLSearchParams(location.search).get(name);
}

const DATA_BASE = window.TRIP_DATA_BASE || "";

function formatDate(d) {
  if (!d) return "";
  return new Date(d).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

function formatDateRange(start, end) {
  if (!start) return "";
  const s = formatDate(start);
  const e = end ? formatDate(end) : null;
  return e && e !== s ? `${s} — ${e}` : s;
}

const WEATHER_ICONS = {
  "clear-day": "☀️", "clear-night": "🌙", "partly-cloudy-day": "⛅",
  "partly-cloudy-night": "☁️", "cloudy": "☁️", "rain": "🌧️",
  "snow": "❄️", "sleet": "🌨️", "wind": "🌬️", "fog": "🌫️",
};

let LIGHTBOX_PHOTOS = [];
let LIGHTBOX_INDEX = 0;

function openLightbox(photos, index) {
  LIGHTBOX_PHOTOS = photos;
  LIGHTBOX_INDEX = index;
  updateLightbox();
  document.getElementById("lightbox").classList.add("is-open");
}

function updateLightbox() {
  document.getElementById("lightbox-img").src = LIGHTBOX_PHOTOS[LIGHTBOX_INDEX];
  document.getElementById("lightbox-count").textContent =
    `${LIGHTBOX_INDEX + 1} / ${LIGHTBOX_PHOTOS.length}`;
}

function closeLightbox() {
  document.getElementById("lightbox").classList.remove("is-open");
}

function initLightbox() {
  document.querySelector(".lightbox-close").onclick = closeLightbox;
  document.querySelector(".lightbox-prev").onclick = () => {
    LIGHTBOX_INDEX = (LIGHTBOX_INDEX - 1 + LIGHTBOX_PHOTOS.length) % LIGHTBOX_PHOTOS.length;
    updateLightbox();
  };
  document.querySelector(".lightbox-next").onclick = () => {
    LIGHTBOX_INDEX = (LIGHTBOX_INDEX + 1) % LIGHTBOX_PHOTOS.length;
    updateLightbox();
  };
  document.getElementById("lightbox").addEventListener("click", (e) => {
    if (e.target.id === "lightbox") closeLightbox();
  });
  document.addEventListener("keydown", (e) => {
    if (!document.getElementById("lightbox").classList.contains("is-open")) return;
    if (e.key === "Escape") closeLightbox();
    if (e.key === "ArrowLeft") document.querySelector(".lightbox-prev").click();
    if (e.key === "ArrowRight") document.querySelector(".lightbox-next").click();
  });

  // navigation tactile (swipe) pour mobile
  let touchStartX = null;
  const lb = document.getElementById("lightbox");
  lb.addEventListener("touchstart", (e) => { touchStartX = e.changedTouches[0].clientX; }, { passive: true });
  lb.addEventListener("touchend", (e) => {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 40) {
      document.querySelector(dx > 0 ? ".lightbox-prev" : ".lightbox-next").click();
    }
    touchStartX = null;
  }, { passive: true });
}

function renderHeader(trip) {
  document.getElementById("page-title").textContent = `${trip.name} — Wayfarer Log`;
  document.getElementById("trip-dates").textContent = formatDateRange(trip.start_date, trip.end_date);
  document.getElementById("trip-name").textContent = trip.name;
  document.getElementById("trip-summary").textContent = trip.summary || "";
  document.getElementById("trip-stats").innerHTML = `
    <div><span class="num">${trip.total_km.toLocaleString("fr-FR")} km</span> <span class="label">parcourus</span></div>
    <div><span class="num">${trip.step_count}</span> <span class="label">étapes</span></div>
    <div><span class="num">${trip.photo_count}</span> <span class="label">photos</span></div>
  `;
}

function renderTimeline(trip) {
  const el = document.getElementById("timeline");
  el.innerHTML = trip.steps.map((s, i) => {
    const weatherIcon = WEATHER_ICONS[s.weather_condition] || "";
    const weather = s.weather_temperature != null
      ? `${weatherIcon} ${Math.round(s.weather_temperature)}°`
      : "";
    const photosHtml = s.photos.map((p, pi) => `
      <button data-step="${i}" data-photo="${pi}">
        <img src="${p.thumb}" alt="${s.name}" loading="lazy">
      </button>
    `).join("");
    const videoHtml = (s.videos || []).map(v => `
      <div class="step-video"><video controls src="${v}"></video></div>
    `).join("");
    return `
      <article class="step" id="step-${s.id}" data-step-index="${i}">
        <div class="step-meta">
          <span>${formatDate(s.date)}</span>
          ${weather ? `<span>${weather}</span>` : ""}
        </div>
        <h3 class="step-name">${s.name} ${s.place ? `<span class="step-place">— ${s.place}</span>` : ""}</h3>
        ${s.description ? `<p class="step-desc">${s.description}</p>` : ""}
        ${s.photos.length ? `<div class="step-photos">${photosHtml}</div>` : ""}
        ${videoHtml}
      </article>
    `;
  }).join("");

  el.querySelectorAll(".step-photos button").forEach(btn => {
    btn.addEventListener("click", () => {
      const stepIndex = Number(btn.dataset.step);
      const photoIndex = Number(btn.dataset.photo);
      const fullPhotos = trip.steps[stepIndex].photos.map(p => p.full);
      openLightbox(fullPhotos, photoIndex);
    });
  });
}

function renderMap(trip) {
  const map = L.map("trip-map").setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    subdomains: "abc",
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const withCoords = trip.steps.filter(s => s.lat && s.lon);
  const latlngs = withCoords.map(s => [s.lat, s.lon]);
  if (latlngs.length > 1) {
    L.polyline(latlngs, { color: "#d9a441", weight: 2, opacity: 0.8 }).addTo(map);
  }

  const markers = {};
  withCoords.forEach(s => {
    const marker = L.circleMarker([s.lat, s.lon], {
      radius: 6,
      color: "#12211f",
      weight: 2,
      fillColor: "#d9a441",
      fillOpacity: 0.95,
    }).addTo(map);
    marker.bindTooltip(s.name, { direction: "top" });
    marker.on("click", () => {
      document.getElementById(`step-${s.id}`).scrollIntoView({ behavior: "smooth" });
    });
    markers[s.id] = marker;
  });

  if (latlngs.length) {
    map.fitBounds(L.latLngBounds(latlngs).pad(0.15));
  }

  // met en avant le marqueur de l'etape visible au scroll
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const stepEl = entry.target;
      const stepId = stepEl.id.replace("step-", "");
      const marker = markers[stepId];
      if (!marker) return;
      if (entry.isIntersecting) {
        marker.setStyle({ fillColor: "#8fbfb2", radius: 8 });
      } else {
        marker.setStyle({ fillColor: "#d9a441", radius: 6 });
      }
    });
  }, { rootMargin: "-40% 0px -40% 0px" });

  document.querySelectorAll(".step").forEach(el => observer.observe(el));
}

async function init() {
  const slug = window.TRIP_SLUG || qs("slug");
  initLightbox();
  if (!slug) {
    document.getElementById("timeline").innerHTML = "<p>Voyage introuvable.</p>";
    return;
  }
  try {
    const res = await fetch(`${DATA_BASE}data/trips/${slug}.json`);
    if (!res.ok) throw new Error("not found");
    const trip = await res.json();
    renderHeader(trip);
    renderTimeline(trip);
    renderMap(trip);
  } catch (e) {
    document.getElementById("timeline").innerHTML = "<p>Ce voyage est introuvable.</p>";
  }
}

init();
