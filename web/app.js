// Lenis 화면 동작. 화면 모양은 style.css, 화면 구성은 index.html에 있다.
// 화면 이동: go("home") 처럼 부르면 .app[data-screen]이 바뀐다.

const CENTER = [35.117, 129.0375];   // TODO: 조사 생활권 정해지면 server/routing.py와 같이 바꾸기
const CLASS_LABEL = { stairs: "계단", curb: "턱", blocked: "지나갈 수 없음", ramp: "경사로", elevator: "엘리베이터" };
const SOURCE_LABEL = { osm: "OpenStreetMap", ai: "AI 추정", survey: "현장 확인", report: "이용자 제보" };
const GRADE_LIMIT = 30;     // 서버가 이 값에서 잘라낸다 (DEM 오차)
const SAME_ROUTE_M = 15;    // 갈 때·올 때 길이 차이가 이보다 작으면 같은 길로 본다

// 자주 가는 곳. 좌표는 OpenStreetMap의 장소 위치
const TRIPS = [
  { from: "초량6동 주민센터", start: [35.120039, 129.0345155], to: "새부산병원", end: [35.118028, 129.039297], icon: "hill" },
  { from: "부산역", start: [35.1157262, 129.0399028], to: "초량6동 주민센터", end: [35.120039, 129.0345155], icon: "stroller" },
  { from: "부산역", start: [35.1157262, 129.0399028], to: "이바구캠프", end: [35.1191555, 129.028386], icon: "suitcase" },
];

const state = {
  profile: "stroller",
  profiles: [],
  start: null, end: null,             // [위도, 경도]
  startName: "", endName: "",
  routes: [],
  selected: 0,
  places: [],
  reportAt: null,
  request: 0,                          // 늦게 온 옛 응답을 버리기 위한 번호
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const esc = (text) => String(text).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* 저장 못 해도 동작은 한다 */ } },
};

// ---------- 3D 아이콘 (Figma 시안과 같은 그림) ----------
const ICON_DEFS = `<defs>
  <linearGradient id="b" x1="30" y1="10" x2="70" y2="80" gradientUnits="userSpaceOnUse"><stop stop-color="#7AB6FF"/><stop offset="1" stop-color="#1B64DA"/></linearGradient>
  <linearGradient id="w" x1="40" y1="30" x2="56" y2="76" gradientUnits="userSpaceOnUse"><stop stop-color="#FFFFFF"/><stop offset="1" stop-color="#CFE0FF"/></linearGradient>
  <linearGradient id="h" x1="48" y1="40" x2="48" y2="82" gradientUnits="userSpaceOnUse"><stop stop-color="#D5E6FF"/><stop offset="1" stop-color="#4C93FF"/></linearGradient></defs>`;
const shadow = (cx, cy, rx) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="5" fill="#1B64DA" fill-opacity="0.16"/>`;
const ICONS = {
  hill: shadow(48, 85, 38) + `<path d="M6 80C16 56 30 44 46 44C62 44 78 56 90 80Z" fill="url(#h)"/><path d="M14 72C22 58 32 51 44 50" stroke="#FFFFFF" stroke-opacity="0.7" stroke-width="3" stroke-linecap="round"/><path d="M30 80C36 72 44 70 52 66C58 63 60 58 58 54" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/><path d="M58 10C47 10 40 18 40 27C40 39 58 52 58 52C58 52 76 39 76 27C76 18 69 10 58 10Z" fill="url(#b)"/><circle cx="58" cy="27" r="7" fill="#FFFFFF"/><path d="M47 18C49 15 52 13.5 55 13" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="3" stroke-linecap="round"/><circle cx="24" cy="32" r="5" fill="#FFC342"/>`,
  stroller: shadow(48, 87, 32) + `<path d="M22 50C22 32 34 20 50 20V50Z" fill="url(#b)"/><path d="M18 50H74C74 62 64 70 50 70H38C27 70 18 62 18 50Z" fill="url(#w)"/><path d="M30 36C33 29 38 25 44 24" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="3" stroke-linecap="round"/><path d="M24 57H68" stroke="#3182F6" stroke-opacity="0.35" stroke-width="3" stroke-linecap="round"/><path d="M74 50L80 30H86" stroke="#1B64DA" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="32" cy="78" r="8" fill="#22324D"/><circle cx="32" cy="78" r="3" fill="#B9CEFF"/><circle cx="64" cy="78" r="8" fill="#22324D"/><circle cx="64" cy="78" r="3" fill="#B9CEFF"/>`,
  suitcase: shadow(48, 89, 26) + `<path d="M38 22V14C38 11 40 10 42 10H54C56 10 58 11 58 14V22" stroke="#22324D" stroke-width="5" stroke-linecap="round"/><rect x="24" y="20" width="48" height="60" rx="12" fill="url(#b)"/><path d="M38 30V70M58 30V70" stroke="#FFFFFF" stroke-opacity="0.45" stroke-width="4" stroke-linecap="round"/><path d="M30 31C30 27 32 26 34 26" stroke="#FFFFFF" stroke-opacity="0.75" stroke-width="3" stroke-linecap="round"/><rect x="61" y="40" width="10" height="14" rx="3" fill="#FFC342"/><circle cx="34" cy="84" r="4.5" fill="#22324D"/><circle cx="62" cy="84" r="4.5" fill="#22324D"/>`,
  report: shadow(46, 85, 30) + `<path d="M24 40L62 22V70L24 54Z" fill="url(#b)"/><rect x="14" y="38" width="14" height="18" rx="5" fill="url(#w)"/><ellipse cx="62" cy="46" rx="8" ry="24" fill="url(#w)"/><path d="M30 56L34 74" stroke="#22324D" stroke-width="6" stroke-linecap="round"/><path d="M30 42L52 32" stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="3" stroke-linecap="round"/><path d="M76 34C80 38 82 42 82 46C82 50 80 54 76 58" stroke="#FFC342" stroke-width="4" stroke-linecap="round"/><path d="M84 28C90 34 92 40 92 46C92 52 90 58 84 64" stroke="#FFC342" stroke-opacity="0.6" stroke-width="4" stroke-linecap="round"/>`,
};
const LOGO = `<svg viewBox="0 0 72 72" aria-hidden="true">
  <defs>
    <linearGradient id="lg" x1="8" y1="0" x2="64" y2="72" gradientUnits="userSpaceOnUse"><stop stop-color="#5AA5FF"/><stop offset="1" stop-color="#1B64DA"/></linearGradient>
    <linearGradient id="lr" x1="24" y1="18" x2="56" y2="52" gradientUnits="userSpaceOnUse"><stop stop-color="#FFFFFF"/><stop offset="1" stop-color="#D3E5FF"/></linearGradient>
  </defs>
  <rect width="72" height="72" rx="18" fill="url(#lg)"/>
  <path d="M24 17V38C24 47 29.5 52 38 52H53" stroke="#1B64DA" stroke-opacity="0.35" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(0 2.5)"/>
  <path d="M24 17V38C24 47 29.5 52 38 52H53" stroke="url(#lr)" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <circle cx="51" cy="22" r="6.5" fill="#FFC342"/>
</svg>`;

// 같은 그림이 여러 번 나와도 그라데이션이 섞이지 않게 id를 아이콘마다 다르게 붙인다
let iconCount = 0;
function iconSVG(name) {
  if (name === "logo") return LOGO.replace(/id="l([gr])"/g, `id="l$1${++iconCount}"`).replace(/url\(#l([gr])\)/g, `url(#l$1${iconCount})`);
  const n = ++iconCount;
  return `<svg viewBox="0 0 96 96" aria-hidden="true">${ICON_DEFS}${ICONS[name]}</svg>`
    .replace(/id="([bwh])"/g, `id="$1${n}"`).replace(/url\(#([bwh])\)/g, `url(#$1${n})`);
}
function paintIcons(root = document) {
  root.querySelectorAll("[data-icon]:empty").forEach((el) => { el.innerHTML = iconSVG(el.dataset.icon); });
}

// ---------- 화면 이동 ----------
const app = $(".app");
const trail = [];

function go(screen, { reset = false } = {}) {
  const now = app.dataset.screen;
  if (now === screen) return;
  if (reset) trail.length = 0;
  else if (now && now !== "start") trail.push(now);
  show(screen);
}
function back() { show(trail.pop() ?? "home"); }

function show(screen) {
  app.dataset.screen = screen;
  $$(".tabbar button").forEach((b) => b.toggleAttribute("aria-current", b.dataset.go === screen));
  $$(".tabbar button[aria-current]").forEach((b) => b.setAttribute("aria-current", "page"));
  const scroller = document.getElementById(screen === "map" ? "mapview" : screen);
  if (scroller) scroller.scrollTop = 0;
  if (screen === "map" || screen === "route") {
    map.invalidateSize();
    if (screen === "map") startMapPick();
  }
  if (screen === "report") openReport();
}

document.addEventListener("click", (e) => {
  const target = e.target.closest("[data-go], [data-back]");
  if (!target) return;
  if (target.hasAttribute("data-back")) return back();
  const screen = target.dataset.go;
  go(screen, { reset: !!target.closest(".tabbar") });
  if (screen === "search") setTimeout(() => $(state.start ? "#end-input" : "#start-input").focus(), 50);
});

// ---------- 시작 화면: 이동 유형 고르기 ----------
function selectProfile(key) {
  state.profile = key;
  store.set("lenis-profile", key);
  $$(".pick-card").forEach((b) => b.setAttribute("aria-checked", b.dataset.profile === key));
  const info = state.profiles.find((p) => p.key === key);
  $("#profile-chip").textContent = info ? info.label.replace("여행용 ", "") : "";
}

$(".start-pick").addEventListener("click", (e) => {
  const card = e.target.closest(".pick-card");
  if (card) selectProfile(card.dataset.profile);
});
$("#start-btn").addEventListener("click", () => go("home", { reset: true }));

async function loadProfiles() {
  state.profiles = await api("/api/profiles");
  const saved = store.get("lenis-profile");
  const known = state.profiles.some((p) => p.key === saved);
  selectProfile(known ? saved : state.profile);
}

// 길 비교 화면의 칩을 누르면 다른 유형으로 같은 구간을 다시 계산한다
$("#profile-chip").addEventListener("click", () => {
  const keys = state.profiles.map((p) => p.key);
  selectProfile(keys[(keys.indexOf(state.profile) + 1) % keys.length]);
  searchRoutes();
});

// ---------- 큰 지도 ----------
// 무드보드처럼 글자가 적고 밝은 지도: OpenFreeMap(키 없이 쓰는 OSM 벡터 지도)의 Positron을 바탕으로
// 공원은 초록, 물은 파랑, 길은 흰색으로 칠한다. 어두운 모드는 같은 지도를 어두운 색으로 칠한다.
const DARK = matchMedia("(prefers-color-scheme: dark)").matches;
const MAP_COLORS = DARK
  ? { background: "#1E2026", park: "#23352A", wood: "#22302A", water: "#1D2C42", building: "#2A2D35", road: "#3A3E48", minor: "#30333C", text: "#C9CDD4", halo: "#1E2026" }
  : { background: "#EEF1F4", park: "#CFEBB9", wood: "#DCEFCD", water: "#AFD3F7", building: "#E2E6EB", road: "#FFFFFF", minor: "#FFFFFF", text: "#6B7684", halo: "#FFFFFF" };
let mapStyle = null;
async function loadMapStyle() {
  const style = await (await fetch("https://tiles.openfreemap.org/styles/positron")).json();
  const c = MAP_COLORS;
  const paint = { background: { "background-color": c.background }, park: { "fill-color": c.park, "fill-opacity": 1 },
    landcover_wood: { "fill-color": c.wood, "fill-opacity": 1 }, water: { "fill-color": c.water },
    waterway: { "line-color": c.water }, building: { "fill-color": c.building },
    landuse_residential: { "fill-color": c.background } };
  for (const layer of style.layers) {
    Object.assign(layer.paint ??= {}, paint[layer.id] ?? {});
    if (layer.type === "line" && layer.id.startsWith("highway")) {
      if (layer.id.includes("casing")) layer.paint["line-color"] = c.background;
      else layer.paint["line-color"] = layer.id.includes("minor") || layer.id.includes("path") ? c.minor : c.road;
    }
    if (layer.type === "symbol") {
      // 한국 이름을 먼저 쓴다 (기본은 로마자)
      layer.layout["text-field"] = ["coalesce", ["get", "name:ko"], ["get", "name"]];
      Object.assign(layer.paint, { "text-color": c.text, "text-halo-color": c.halo });
    }
  }
  return style;
}
async function addBaseMap(target) {
  try {
    mapStyle ??= loadMapStyle();
    L.maplibreGL({ style: await mapStyle, attribution: "© OpenStreetMap · OpenFreeMap" }).addTo(target);
  } catch (err) {
    console.error(err);   // 벡터 지도를 못 읽으면 기본 OSM 지도로 보여 준다
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap", maxZoom: 19 }).addTo(target);
  }
}
const map = L.map("map", { zoomControl: false, attributionControl: true }).setView(CENTER, 15);
addBaseMap(map);
const routeLayer = L.layerGroup().addTo(map);
const pinLayer = L.layerGroup().addTo(map);
const entranceLayer = L.layerGroup().addTo(map);
window.addEventListener("resize", () => { map.invalidateSize(); reportMap?.invalidateSize(); });

// 출발: 파란 테두리 동그라미 / 도착: 끝이 뾰족한 핀 / 그 밖: 작은 점
const END_PIN = `<svg viewBox="0 0 32 40" aria-hidden="true"><path d="M16 39C16 39 30 25.5 30 15A14 14 0 0 0 2 15C2 25.5 16 39 16 39Z" fill="currentColor" stroke="#fff" stroke-width="2.5"/><circle cx="16" cy="15" r="5.5" fill="#fff"/></svg>`;
function pinIcon(kind) {
  if (kind === "end") return L.divIcon({ className: "pin pin-end", html: END_PIN, iconSize: [32, 40], iconAnchor: [16, 39] });
  return L.divIcon({ className: `pin pin-${kind}`, html: "<span></span>", iconSize: [22, 22], iconAnchor: [11, 11] });
}

function drawPins() {
  pinLayer.clearLayers();
  if (state.start) L.marker(state.start, { icon: pinIcon("start") }).bindTooltip("출발").addTo(pinLayer);
  if (state.end) L.marker(state.end, { icon: pinIcon("end") }).bindTooltip("도착").addTo(pinLayer);
}

// 지도 탭: 지도를 눌러 출발 → 도착을 고른다
let picking = [];
function startMapPick() {
  picking = [];
  routeLayer.clearLayers();
  entranceLayer.clearLayers();
  pinLayer.clearLayers();
  $("#map-hint").textContent = "지도를 눌러 출발지를 고르세요";
  $("#map-pick").hidden = true;
}

map.on("click", (e) => {
  if (app.dataset.screen !== "map") return;
  const p = [e.latlng.lat, e.latlng.lng];
  if (picking.length >= 2) picking = [];
  picking.push(p);
  pinLayer.clearLayers();
  picking.forEach((q, i) => L.marker(q, { icon: pinIcon(i ? "end" : "start") }).addTo(pinLayer));
  const done = picking.length === 2;
  $("#map-hint").textContent = done ? "다시 누르면 처음부터 고를 수 있어요" : "이제 도착지를 눌러 주세요";
  $("#map-pick").hidden = !done;
  if (done) $("#map-pick-text").textContent = `${placeLabel(picking[0])} → ${placeLabel(picking[1])}`;
});

$("#map-pick-btn").addEventListener("click", () => {
  setTrip(picking[0], placeLabel(picking[0]), picking[1], placeLabel(picking[1]));
  searchRoutes();
});

// ---------- 장소 ----------
function fmt([lat, lon]) { return `${lat.toFixed(5)}, ${lon.toFixed(5)}`; }
function parse(text) {
  const [lat, lon] = text.split(",").map(Number);
  return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}
function meters(a, b) {
  const rad = Math.PI / 180;
  const x = (b[1] - a[1]) * rad * Math.cos(((a[0] + b[0]) / 2) * rad);
  return Math.hypot(x, (b[0] - a[0]) * rad) * 6371000;
}

// 고른 지점과 가장 가까운 장소 이름. 멀면 "고른 위치"
function placeLabel(p) {
  let best = null;
  for (const place of state.places) {
    const d = meters(p, [place.lat, place.lon]);
    if (d < 250 && (!best || d < best.d)) best = { d, name: place.name };
  }
  return best ? `${best.name} 근처` : "고른 위치";
}

// 장소 이름이나 "위도, 경도"를 좌표로 바꾼다. 못 찾으면 비슷한 장소 목록을 돌려준다
function lookupPlace(text) {
  const coords = parse(text.trim());
  if (coords) return { coords, name: placeLabel(coords), suggestions: [] };
  const { match, suggestions } = PlaceSearch.search(text, state.places);
  return { coords: match ? [match.lat, match.lon] : null, name: match?.name, suggestions };
}

function showSuggestions(field, text, suggestions) {
  $("#search-status").textContent = suggestions.length
    ? `"${text}"을(를) 못 찾았어요. 혹시 이곳인가요?`
    : `"${text}"을(를) 못 찾았어요. 다른 이름으로 찾거나 지도에서 골라 주세요.`;
  $("#place-suggest").innerHTML = suggestions.map((p) =>
    `<button type="button" class="suggest-btn" data-field="${field}" data-name="${esc(p.name)}">${esc(p.name)}</button>`).join("");
  $("#place-suggest").hidden = !suggestions.length;
}

function clearSuggestions() {
  $("#search-status").textContent = "";
  $("#place-suggest").hidden = true;
  $("#place-suggest").innerHTML = "";
}

$("#place-suggest").addEventListener("click", (e) => {
  const btn = e.target.closest(".suggest-btn");
  if (!btn) return;
  $(`#${btn.dataset.field}-input`).value = btn.dataset.name;
  clearSuggestions();
  $("#route-form").requestSubmit();
});
["#start-input", "#end-input"].forEach((sel) => $(sel).addEventListener("input", clearSuggestions));

async function loadPlaces() {
  state.places = await api("places.json");
  $("#place-list").innerHTML = state.places.map((p) => `<option value="${esc(p.name)}"></option>`).join("");
}

// ---------- API ----------
async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(`${res.status} ${text}`);
    try { err.detail = res.status === 400 ? JSON.parse(text).detail : null; } catch { /* 서버 안내문이 없으면 기본 문구 */ }
    throw err;
  }
  return res.json();
}
const postJSON = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function loadStats() {
  const s = await api("/api/stats");
  $("#stat-stairs").textContent = `${s.stairs.toLocaleString("ko-KR")}곳`;
  $("#stat-roads").textContent = `${s.sloped_roads.toLocaleString("ko-KR")}개`;
}

// ---------- 자주 가는 곳 ----------
const tripHTML = TRIPS.map((t, i) => `
  <li><button type="button" class="trip-btn" data-index="${i}">
    <span class="trip-tile"><i data-icon="${t.icon}"></i></span>
    <span class="trip-text"><strong>${esc(t.to)}</strong><span>${esc(t.from)}에서 출발</span></span>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>
  </button></li>`).join("");
$("#trip-list").innerHTML = tripHTML;
$("#search-trips").innerHTML = tripHTML;

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".trip-btn");
  if (!btn) return;
  const t = TRIPS[Number(btn.dataset.index)];
  setTrip(t.start, t.from, t.end, t.to);
  searchRoutes();
});

function setTrip(start, startName, end, endName) {
  Object.assign(state, { start, startName, end, endName });
  $("#start-input").value = startName;
  $("#end-input").value = endName;
  store.set("lenis-trip", JSON.stringify({ start, startName, end, endName }));
}

// 출발지와 도착지를 바꾼다
function swapPlaces() {
  setTrip(state.end, state.endName, state.start, state.startName);
}
$("#swap-btn").addEventListener("click", () => {
  const [a, b] = [$("#start-input").value, $("#end-input").value];
  $("#start-input").value = b;
  $("#end-input").value = a;
  clearSuggestions();
});

// 홈의 "돌아오는 길": 마지막으로 본 길을 거꾸로 찾는다
$("#return-card").addEventListener("click", () => {
  let last = null;
  try { last = JSON.parse(store.get("lenis-trip")); } catch { /* 없으면 아래에서 첫 구간 */ }
  if (!state.start && last?.start) Object.assign(state, last);
  if (!state.start) { const t = TRIPS[0]; setTrip(t.start, t.from, t.end, t.to); }
  swapPlaces();
  searchRoutes();
});

$("#route-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const [startText, endText] = [$("#start-input").value, $("#end-input").value];
  const [start, end] = [lookupPlace(startText), lookupPlace(endText)];
  if (!start.coords) return showSuggestions("start", startText, start.suggestions);
  if (!end.coords) return showSuggestions("end", endText, end.suggestions);
  setTrip(start.coords, start.name, end.coords, end.name);
  searchRoutes();
});

// ---------- 장애물 표시 ----------
async function loadObstacles() {
  const obstacles = await api("/api/obstacles");
  for (const o of obstacles) {
    const estimated = o.source === "ai";
    const detail = estimated ? `확신도 ${Math.round(o.conf * 100)}%, 현장 확인 필요` : "확인된 정보";
    L.circleMarker([o.lat, o.lon], {
      radius: 3.5,
      color: estimated ? css("--accent") : css("--muted"),
      weight: 1.5,
      dashArray: estimated ? "3 3" : null,
      fillColor: css("--surface"),
      fillOpacity: estimated ? 0.4 : 0.9,
    })
      .bindPopup(`<strong>${esc(CLASS_LABEL[o.class] ?? o.class)}</strong><br>${esc(SOURCE_LABEL[o.source] ?? o.source)}<br>${detail}`)
      .addTo(map);
  }
}

// ---------- 길 찾기 ----------
const sheet = $("#sheet");

function setExpanded(on) {
  sheet.classList.toggle("is-expanded", on);
  $("#sheet-handle").setAttribute("aria-expanded", on);
  $("#sheet-handle").setAttribute("aria-label", on ? "작게 보기" : "자세히 보기");
  if (!on) $("#sheet-body").scrollTop = 0;
}
$("#sheet-handle").addEventListener("click", () => setExpanded(!sheet.classList.contains("is-expanded")));

// 손잡이를 위아래로 밀어 시트 크기를 바꾼다
let dragStart = null;
$("#sheet-handle").addEventListener("pointerdown", (e) => { dragStart = e.clientY; });
window.addEventListener("pointerup", (e) => {
  if (dragStart === null) return;
  const moved = e.clientY - dragStart;
  dragStart = null;
  if (Math.abs(moved) > 30) setExpanded(moved < 0);
});

async function searchRoutes() {
  const id = ++state.request;
  clearSuggestions();
  if (app.dataset.screen !== "route") go("route");
  $("#route-title").textContent = `${state.startName} → ${state.endName}`;
  setExpanded(false);
  state.routes = [];
  routeLayer.clearLayers();
  entranceLayer.clearLayers();
  $("#headline").hidden = true;
  $("#route-tabs").innerHTML = "";
  $("#round-trip").hidden = true;
  $("#route-status").textContent = "편한 길을 찾고 있어요.";
  drawPins();
  map.fitBounds(L.latLngBounds([state.start, state.end]), fitPadding());
  $("#search-btn").disabled = true;
  try {
    const data = await postJSON("/api/route", { start: state.start, end: state.end, profile: state.profile });
    if (id !== state.request) return;
    state.routes = data.routes;
    state.selected = data.routes.length > 1 ? 1 : 0;
    $("#route-status").textContent = "";
    renderRoutes();
    loadEntrances(state.end).catch(console.error);
    loadRoundTrip(id).catch(console.error);
  } catch (err) {
    console.error(err);
    if (id === state.request) {
      $("#route-status").textContent = typeof err.detail === "string" ? err.detail : "길을 찾지 못했어요. 출발지와 도착지를 다시 골라 주세요.";
    }
  } finally {
    $("#search-btn").disabled = false;
  }
}

// 경사 데이터가 없으면 0으로 보이지 않게 한다
const withUnit = (value, unit) => (value === null || value === undefined ? "–" : `${value}${unit}`);
const gradeText = (value) => (value === null ? "–" : value >= GRADE_LIMIT ? `${GRADE_LIMIT}%+` : `${value}%`);
const mins = (r) => Math.max(1, Math.round(r.minutes));
const recommended = (routes) => routes[routes.length > 1 ? 1 : 0];
function shortName(route) {
  if (route.name === "최단 경로") return "최단 경로";
  if (route.name === "오르막 최소 경로") return "오르막 최소";
  return "편한 길";
}

// 더 많은 쪽의 가파른 구간을 화살표와 함께 쓴다
function steepText(r) {
  if (r.steep_up_m === null) return { cls: "", text: "경사 정보 없음" };
  if (!r.steep_up_m && !r.steep_down_m) return { cls: "", text: "가파른 곳 없음" };
  return r.steep_down_m >= r.steep_up_m
    ? { cls: "is-down", text: `↓가파른 ${r.steep_down_m}m` }
    : { cls: "is-up", text: `↑가파른 ${r.steep_up_m}m` };
}

// 큰 숫자: 최단 경로보다 무엇이 얼마나 줄었는지 하나만 크게 보여 준다
function headline(routes) {
  const [base, easy] = [routes[0], recommended(routes)];
  const extra = easy.length_m - base.length_m;
  const extraMin = mins(easy) - mins(base);
  const sub = extra > 0 ? `${extra}m${extraMin > 0 ? `, ${extraMin}분` : ""}만 더 걸으면 돼요` : "거리도 더 짧아요";
  if (routes.length === 1) {
    return { label: "이 구간은", value: "최단 경로", unit: "가 가장 편해요", sub: base.warnings[0] ?? `${base.length_m}m, ${mins(base)}분 걸려요` };
  }
  const stairs = base.stairs - easy.stairs;
  if (stairs > 0) return { label: "계단을", value: `${stairs}곳`, unit: "피해요", sub };
  const up = (base.steep_up_m ?? 0) - (easy.steep_up_m ?? 0);
  const down = (base.steep_down_m ?? 0) - (easy.steep_down_m ?? 0);
  if (up <= 0 && down <= 0) {
    // 가파른 길이는 줄지 않았지만 가장 가파른 곳이 덜 가파르면 그걸 보여 준다
    const eased = (base.max_grade ?? 0) - (easy.max_grade ?? 0);
    if (eased >= 0.5) return { label: "가장 가파른 곳이", value: gradeText(easy.max_grade), unit: "로 낮아져요", sub: `최단 경로는 ${gradeText(base.max_grade)} · ${sub}` };
    return { label: "두 길의 경사는", value: "비슷", unit: "해요", sub: `편한 길은 ${extra > 0 ? `${extra}m 더 걸어요` : "거리도 짧아요"}` };
  }
  return up >= down
    ? { label: "가파른 오르막이", value: `${up}m`, unit: "줄어요", sub }
    : { label: "갈 때는 가파른 내리막이", value: `${down}m`, unit: "줄어요", sub };
}

function renderRoutes() {
  const h = headline(state.routes);
  $("#headline-label").textContent = h.label;
  $("#headline-value").textContent = h.value;
  $("#headline-unit").textContent = h.unit;
  $("#headline-sub").textContent = h.sub;
  $("#headline").hidden = false;
  $("#route-tabs").dataset.count = state.routes.length;
  $("#route-tabs").innerHTML = state.routes.map((r, i) => {
    const s = steepText(r);
    return `
    <button type="button" class="route-tab" role="tab" data-index="${i}" aria-selected="${i === state.selected}">
      <span class="tab-name">${esc(shortName(r))}</span>
      <span class="tab-time">${mins(r)}분</span>
      <span class="tab-detail">${r.length_m}m · <span class="${s.cls}">${s.text}</span></span>
    </button>`;
  }).join("");
  renderSelected();
  fitRoutes();
}

function renderSelected() {
  const r = state.routes[state.selected];
  $$(".route-tab").forEach((t) => t.setAttribute("aria-selected", Number(t.dataset.index) === state.selected));
  $("#direction-pills").innerHTML = r.downhill_m === null ? "" :
    `<span class="pill is-down">↓ 내리막 ${r.downhill_m}m</span><span class="pill is-up">↑ 오르막 ${r.uphill_m}m</span>`;
  $("#elevation").hidden = !r.elevation.length;
  $("#slope-note").hidden = !r.elevation.length;
  $("#elevation-chart").innerHTML = elevationChart(r);
  $("#stat-row").innerHTML = [
    ["가파른<br>오르막", withUnit(r.steep_up_m, "m"), r.steep_up_m ? "is-up" : ""],
    ["가파른<br>내리막", withUnit(r.steep_down_m, "m"), r.steep_down_m ? "is-down" : ""],
    ["계단", `${r.stairs}곳`, r.stairs ? "is-up" : ""],
    ["최대 경사", gradeText(r.max_grade), ""],
  ].map(([label, value, cls]) => `<div class="stat"><span>${label}</span><strong class="${cls}">${value}</strong></div>`).join("");
  const notes = [...r.warnings];
  if (r.sources.length) notes.push(`장애물 정보: ${r.sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ")}`);
  $("#warnings").innerHTML = notes.map((w) => `<li>${esc(w)}</li>`).join("");
  $("#warnings").hidden = !notes.length;
  drawRouteLines();
}

$("#route-tabs").addEventListener("click", (e) => {
  const tab = e.target.closest(".route-tab");
  if (!tab) return;
  state.selected = Number(tab.dataset.index);
  renderSelected();
});

function drawRouteLines() {
  routeLayer.clearLayers();
  const order = state.routes.map((_, i) => i).filter((i) => i !== state.selected).concat(state.selected);
  const line = { lineCap: "round", lineJoin: "round" };
  for (const i of order) {
    const r = state.routes[i];
    const on = i === state.selected;
    // 흰 테두리를 깔아 지도 위에서 선이 또렷하게 보이게 한다. 고르지 않은 길은 회색으로 뒤에 둔다
    L.polyline(r.coords, { ...line, color: "#FFFFFF", weight: on ? 12 : 9, opacity: on ? 1 : 0.9, interactive: false }).addTo(routeLayer);
    L.polyline(r.coords, { ...line, color: on ? css("--brand") : css("--route-short"), weight: on ? 7 : 5 })
      .bindTooltip(shortName(r), { sticky: true })
      .on("click", () => { state.selected = i; renderSelected(); }).addTo(routeLayer);
  }
  const chosen = state.routes[state.selected];
  for (const s of chosen.steep_lines) {
    L.polyline(s.line, { ...line, color: css(s.up ? "--steep-up" : "--steep-down"), weight: 7 })
      .bindTooltip(s.up ? "가파른 오르막" : "가파른 내리막", { sticky: true }).addTo(routeLayer);
  }
  // 고른 장소와 길 사이(건물 안·광장 등)는 점선으로 잇는다
  const dash = { color: css("--muted"), weight: 3, dashArray: "2 7", lineCap: "round", interactive: false };
  if (chosen.coords.length) {
    L.polyline([state.start, chosen.coords[0]], dash).addTo(routeLayer);
    L.polyline([chosen.coords.at(-1), state.end], dash).addTo(routeLayer);
  }
}

// 고른 길의 높낮이. 가파른 오르막은 빨강, 내리막은 주황, 최단 경로는 회색 점선
function elevationChart(r) {
  const pts = r.elevation;
  if (!pts.length) return "";
  const base = state.selected !== 0 ? state.routes[0].elevation : [];
  const all = pts.concat(base);
  const [w, h, top, bottom] = [320, 110, 8, 20];
  const maxD = Math.max(...all.map((p) => p[0]), 1);
  const low = Math.min(...all.map((p) => p[1]));
  const high = Math.max(...all.map((p) => p[1]), low + 5);
  const x = (d) => ((d / maxD) * w).toFixed(1);
  const y = (z) => (top + (1 - (z - low) / (high - low)) * (h - top - bottom)).toFixed(1);
  const line = (list) => list.map((p) => `${x(p[0])},${y(p[1])}`).join(" ");
  const steep = pts.slice(1).map((p, k) => p[2]
    ? `<line x1="${x(pts[k][0])}" y1="${y(pts[k][1])}" x2="${x(p[0])}" y2="${y(p[1])}" stroke="var(${p[1] > pts[k][1] ? "--steep-up" : "--steep-down"})" stroke-width="4" stroke-linecap="round"/>`
    : "").join("");
  const peak = Math.round(Math.max(...pts.map((p) => p[1])));
  return `
    <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="가장 높은 곳은 출발점보다 ${peak}미터 높아요">
      <line x1="0" y1="${h - bottom}" x2="${w}" y2="${h - bottom}" stroke="var(--line)"/>
      ${base.length ? `<polyline points="${line(base)}" fill="none" stroke="var(--route-short)" stroke-width="2" stroke-dasharray="2 4" stroke-linecap="round"/>` : ""}
      <polygon points="${x(pts[0][0])},${h - bottom} ${line(pts)} ${x(pts.at(-1)[0])},${h - bottom}" fill="var(--brand)" opacity="0.12"/>
      <polyline points="${line(pts)}" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round"/>
      ${steep}
      <text class="chart-axis" x="0" y="${h - 4}">출발</text>
      <text class="chart-axis" x="${w}" y="${h - 4}" text-anchor="end">${Math.round(maxD)}m</text>
    </svg>`;
}

// 갈 때와 올 때를 같이 보여 준다. 내리막이었던 길은 돌아올 때 오르막이 된다
async function loadRoundTrip(id) {
  const data = await postJSON("/api/route", { start: state.end, end: state.start, profile: state.profile });
  if (id !== state.request) return;
  const [there, back] = [recommended(state.routes), recommended(data.routes)];
  const differs = Math.abs(there.length_m - back.length_m) > SAME_ROUTE_M;
  const title = !differs ? "돌아올 때도 같은 길이 편해요"
    : there.steep_down_m > 0 ? "돌아올 땐 오르막이라 다른 길로 안내해요" : "돌아올 땐 다른 길이 더 편해요";
  const leg = (label, r) => {
    const s = steepText(r);
    return `<div class="leg"><span>${label}</span><strong>${mins(r)}분 · ${r.length_m}m</strong><em class="${s.cls}">${s.text}</em></div>`;
  };
  $("#round-trip").innerHTML = `<strong class="round-title">${title}</strong>
    <div class="legs">${leg("갈 때", there)}${leg("올 때", back)}</div>
    <button type="button" class="text-btn" id="round-go">돌아오는 길 보기</button>`;
  $("#round-trip").hidden = false;
}
$("#round-trip").addEventListener("click", (e) => {
  if (!e.target.closest("#round-go")) return;
  swapPlaces();
  searchRoutes();
});

// 위 막대와 아래 시트에 가리지 않게 경로를 보여 준다
function fitPadding() {
  const box = app.getBoundingClientRect();
  const topBar = $(".top-bar").getBoundingClientRect();
  const sheetTop = sheet.getBoundingClientRect().top;
  return {
    paddingTopLeft: [28, Math.max(topBar.bottom - box.top + 20, 90)],
    paddingBottomRight: [28, Math.max(box.bottom - sheetTop + 20, 260)],
  };
}
function fitRoutes() {
  if (!state.routes.length) return;
  map.fitBounds(L.polyline(state.routes.flatMap((r) => r.coords)).getBounds(), fitPadding());
}

// ---------- 출입구 ----------
async function loadEntrances([lat, lon]) {
  const items = await api(`/api/entrances?lat=${lat}&lon=${lon}`);
  entranceLayer.clearLayers();
  $("#entrances").hidden = !items.length;
  $("#entrances").innerHTML = `<strong>도착지 출입구</strong><ul>${items.map((e) =>
    `<li>${esc(e.name)}<span>${e.distance_m}m · ${esc(e.checked_at)} 확인</span></li>`).join("")}</ul>`;
  items.forEach((e) => L.marker([e.lat, e.lon], { icon: pinIcon("entrance") }).bindTooltip(e.name).addTo(entranceLayer));
}

// ---------- 제보 ----------
let reportMap = null;
let reportPin = null;

function openReport() {
  $("#report-status").textContent = "";
  if (!reportMap) {
    reportMap = L.map("report-map", { zoomControl: false, attributionControl: false }).setView(state.end ?? CENTER, 17);
    addBaseMap(reportMap);
    reportMap.on("click", (e) => setReportPlace([e.latlng.lat, e.latlng.lng]));
  }
  setTimeout(() => reportMap.invalidateSize(), 0);
}

function setReportPlace(p) {
  state.reportAt = p;
  $("#report-place").textContent = placeLabel(p) === "고른 위치" ? fmt(p) : placeLabel(p);
  if (reportPin) reportPin.setLatLng(p);
  else reportPin = L.marker(p, { icon: pinIcon("report") }).addTo(reportMap);
}

// 큰 지도를 길게 누르면 그 자리로 제보 화면을 연다
map.on("contextmenu", (e) => {
  go("report");
  const p = [e.latlng.lat, e.latlng.lng];
  reportMap.setView(p, 17);
  setReportPlace(p);
});

$("#report-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const at = state.reportAt;
  if (!at) { $("#report-status").textContent = "위 지도를 눌러 위치를 먼저 골라 주세요."; return; }
  const f = new FormData(e.target);
  const btn = e.target.querySelector("[type=submit]");
  btn.disabled = true;
  try {
    await postJSON("/api/reports", {
      lat: at[0], lon: at[1],
      profile: state.profile,
      kind: f.get("kind"),
      obstacle: f.get("obstacle") || null,
      memo: f.get("memo"),
    });
    e.target.reset();
    $("#report-status").textContent = "고마워요! 제보를 받았어요.";
  } catch (err) {
    console.error(err);
    $("#report-status").textContent = "제보를 보내지 못했어요. 인터넷 연결을 확인하고 다시 보내 주세요.";
  } finally {
    btn.disabled = false;
  }
});

// ---------- 처음 ----------
paintIcons();
new MutationObserver(() => paintIcons()).observe(app, { childList: true, subtree: true });
show(store.get("lenis-profile") ? "home" : "start");
loadProfiles().catch((err) => { console.error(err); $("#search-status").textContent = "서버에 연결하지 못했어요."; });
loadStats().catch(console.error);
loadObstacles().catch(console.error);
loadPlaces().catch(console.error);
