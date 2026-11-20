// 화면 동작. 디자인과 무관하게 id/class만 맞으면 동작한다.

const CENTER = [35.117, 129.0375];   // TODO: 조사 생활권 정해지면 server/routing.py와 같이 바꾸기
const CLASS_LABEL = { stairs: "계단", curb: "턱", ramp: "경사로", elevator: "엘리베이터" };
const SOURCE_LABEL = { osm: "OpenStreetMap", ai: "AI 추정", survey: "현장 확인", report: "이용자 제보" };
const SOURCE_COLOR = { osm: "#10263D", ai: "#C77700", survey: "#0B7F6B", report: "#6741D9" };
const ROUTE_COLOR = ["#66788A", "#0F5FA8", "#0B7F6B"];
const GRADE_LIMIT = 30;     // 서버가 이 값에서 잘라낸다 (DEM 오차)

// 시연용 구간. 좌표는 OpenStreetMap의 장소 위치
const TRIPS = [
  { from: "초량6동 주민센터", start: [35.120039, 129.0345155], to: "새부산병원", end: [35.118028, 129.039297] },
  { from: "부산역", start: [35.1157262, 129.0399028], to: "초량6동 주민센터", end: [35.120039, 129.0345155] },
  { from: "부산역", start: [35.1157262, 129.0399028], to: "이바구캠프", end: [35.1191555, 129.028386] },
];

const state = {
  profile: "stroller",
  start: null,        // [위도, 경도]
  end: null,
  reportAt: null,
  routes: [],
  selected: 0,
  places: [],
};

const $ = (sel) => document.querySelector(sel);
const esc = (text) => String(text).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ---------- 화면 이동 ----------
function showStep(step) {
  document.body.dataset.step = step;
  document.querySelectorAll("#step-nav button").forEach((b) => {
    if (b.dataset.step === step) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $("#sheet").scrollTop = 0;
  if (step === "report") reportLayer.addTo(map);
  else reportLayer.remove();
  map.invalidateSize();
}

$("#step-nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) showStep(btn.dataset.step);
});

// ---------- 지도 ----------
const map = L.map("map", { zoomControl: false }).setView(CENTER, 15);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap",
  maxZoom: 19,
}).addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const STEEP_COLOR = "#C2255C";
const pinLayer = L.layerGroup().addTo(map);
const entranceLayer = L.layerGroup().addTo(map);
const reportLayer = L.layerGroup();
window.addEventListener("resize", () => map.invalidateSize());

// 지도 클릭: 길 찾기 화면에서는 출발 → 도착, 제보 화면에서는 제보 위치를 고른다
map.on("click", (e) => {
  const p = [e.latlng.lat, e.latlng.lng];
  if (document.body.dataset.step === "report") return setReportPlace(p);
  if (document.body.dataset.step !== "search") return;
  $("#search-status").textContent = "";
  if (!state.start || state.end) {
    state.start = p; state.end = null;
    $("#start-input").value = fmt(p); $("#end-input").value = "";
  } else {
    state.end = p;
    $("#end-input").value = fmt(p);
  }
  drawPins();
});

// 우클릭(모바일은 길게 누르기): 바로 제보 화면으로
map.on("contextmenu", (e) => {
  setReportPlace([e.latlng.lat, e.latlng.lng]);
  showStep("report");
});

function setReportPlace(p) {
  state.reportAt = p;
  $("#report-location").textContent = `제보 위치: ${fmt(p)}`;
  reportLayer.clearLayers();
  L.marker(p).bindTooltip("제보 위치").addTo(reportLayer);
}

function fmt([lat, lon]) { return `${lat.toFixed(5)}, ${lon.toFixed(5)}`; }
function parse(text) {
  const [lat, lon] = text.split(",").map(Number);
  return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}

// 장소 이름이나 "위도, 경도"를 좌표로 바꾼다
function resolvePlace(text) {
  const query = text.trim();
  const coords = parse(query);
  if (coords) return coords;
  const exact = state.places.find((p) => p.name === query);
  const matches = exact ? [exact] : state.places.filter((p) => query && p.name.includes(query));
  return matches.length === 1 ? [matches[0].lat, matches[0].lon] : null;
}

async function loadPlaces() {
  state.places = await api("places.json");
  $("#place-list").innerHTML = state.places.map((p) => `<option value="${esc(p.name)}"></option>`).join("");
}

function drawPins() {
  pinLayer.clearLayers();
  if (state.start) L.marker(state.start).bindTooltip("출발").addTo(pinLayer);
  if (state.end) L.marker(state.end).bindTooltip("도착").addTo(pinLayer);
}

// ---------- API ----------
async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}
const postJSON = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// ---------- 이동 유형 ----------
async function loadProfiles() {
  const profiles = await api("/api/profiles");
  const buttons = profiles
    .map((p) => `<button type="button" class="profile-btn" data-key="${esc(p.key)}">${esc(p.label)}</button>`)
    .join("");
  $("#profile-list").innerHTML = buttons;
  $("#result-profile-list").innerHTML = buttons;
  selectProfile(state.profile);
}

function selectProfile(key) {
  state.profile = key;
  document.querySelectorAll(".profile-btn").forEach((b) => {
    b.classList.toggle("is-selected", b.dataset.key === key);
    b.setAttribute("aria-pressed", b.dataset.key === key);
  });
}

$("#profile-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".profile-btn");
  if (btn) selectProfile(btn.dataset.key);
});

// 길 비교 화면에서 유형을 바꾸면 같은 구간을 다시 계산한다
$("#result-profile-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".profile-btn");
  if (!btn) return;
  selectProfile(btn.dataset.key);
  if (state.start && state.end) searchRoutes();
});

// ---------- 추천 구간 ----------
$("#trip-list").innerHTML = TRIPS.map((t, i) =>
  `<button type="button" class="trip-btn" data-index="${i}">${esc(t.from)}에서 ${esc(t.to)}까지</button>`).join("");

$("#trip-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".trip-btn");
  if (!btn) return;
  const trip = TRIPS[Number(btn.dataset.index)];
  state.start = trip.start;
  state.end = trip.end;
  $("#start-input").value = trip.from;
  $("#end-input").value = trip.to;
  searchRoutes();
});

// ---------- 장애물 표시 ----------
async function loadObstacles() {
  const obstacles = await api("/api/obstacles");
  for (const o of obstacles) {
    const estimated = o.source === "ai";
    const detail = estimated ? `확신도 ${Math.round(o.conf * 100)}%, 현장 확인 필요` : "확인된 정보";
    L.circleMarker([o.lat, o.lon], {
      radius: 6,
      color: SOURCE_COLOR[o.source] ?? SOURCE_COLOR.osm,
      weight: 2,
      dashArray: estimated ? "3 3" : null,
      fillColor: "#FFFFFF",
      fillOpacity: estimated ? 0.4 : 0.9,
    })
      .bindPopup(`<strong>${esc(CLASS_LABEL[o.class] ?? o.class)}</strong><br>${esc(SOURCE_LABEL[o.source] ?? o.source)}<br>${detail}`)
      .addTo(map);
  }
}

// ---------- 경로 ----------
$("#route-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const [startText, endText] = [$("#start-input").value, $("#end-input").value];
  const [start, end] = [resolvePlace(startText), resolvePlace(endText)];
  if (!start || !end) {
    $("#search-status").textContent = `"${!start ? startText : endText}"을(를) 찾지 못했어요. 목록에서 고르거나 지도를 눌러 주세요.`;
    return;
  }
  state.start = start;
  state.end = end;
  searchRoutes();
});

async function searchRoutes() {
  $("#search-status").textContent = "";
  $("#recommendation").hidden = true;
  drawPins();
  showStep("result");
  $("#route-list").innerHTML = "";
  $("#slope-note").hidden = true;
  $("#reverse-btn").hidden = true;
  $("#search-btn").disabled = true;
  setStatus("길을 계산하고 있어요. 처음 한 번은 1분쯤 걸려요.");
  try {
    const data = await postJSON("/api/route", { start: state.start, end: state.end, profile: state.profile });
    state.routes = data.routes;
    state.selected = data.routes.length > 1 ? 1 : 0;
    renderRoutes();
    setStatus("");
    await loadEntrances(state.end);
  } catch (err) {
    console.error(err);
    setStatus("길을 찾지 못했어요. 출발지와 도착지를 다시 골라 주세요.");
  } finally {
    $("#search-btn").disabled = false;
  }
}

function setStatus(text) { $("#status").textContent = text; }

// 같은 길도 방향에 따라 부담이 달라지므로 돌아오는 길을 바로 비교한다
$("#reverse-btn").addEventListener("click", () => {
  [state.start, state.end] = [state.end, state.start];
  const [from, to] = [$("#start-input").value, $("#end-input").value];
  $("#start-input").value = to;
  $("#end-input").value = from;
  searchRoutes();
});

// 경사 데이터가 없으면 0으로 보이지 않게 한다
function withUnit(value, unit) { return value === null ? "정보 없음" : `${value}${unit}`; }
function gradeText(value) {
  if (value === null) return "정보 없음";
  return value >= GRADE_LIMIT ? `${GRADE_LIMIT}% 이상` : `${value}%`;
}

function drawRouteLines() {
  routeLayer.clearLayers();
  const order = state.routes.map((_, i) => i).filter((i) => i !== state.selected).concat(state.selected);
  order.forEach((i) => {
    const on = i === state.selected;
    L.polyline(state.routes[i].coords, { color: ROUTE_COLOR[i], weight: on ? 7 : 4, opacity: on ? 1 : 0.55 })
      .bindTooltip(state.routes[i].name)
      .addTo(routeLayer);
  });
  state.routes[state.selected]?.steep_lines.forEach((line) =>
    L.polyline(line, { color: STEEP_COLOR, weight: 5, opacity: 1, lineCap: "butt" }).bindTooltip("가파른 구간").addTo(routeLayer));
}

// 경로끼리 높낮이를 비교할 수 있게 모든 카드에 같은 축척을 쓴다
function elevationScale(routes) {
  const points = routes.flatMap((r) => r.elevation);
  if (!points.length) return null;
  const rises = points.map((p) => p[1]);
  return { distance: Math.max(...points.map((p) => p[0]), 1), low: Math.min(...rises), high: Math.max(...rises, Math.min(...rises) + 1) };
}

function elevationChart(route, color, scale) {
  if (!scale || !route.elevation.length) return `<p class="route-elevation-empty">높낮이 정보 없음</p>`;
  const [w, h, pad] = [320, 76, 5];
  const x = (d) => (d / scale.distance) * w;
  const y = (z) => h - pad - ((z - scale.low) / (scale.high - scale.low)) * (h - pad * 2);
  const pts = route.elevation;
  const line = pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const area = `0,${h} ${line} ${x(pts[pts.length - 1][0]).toFixed(1)},${h}`;
  const steep = pts.slice(1).map((p, i) => p[2]
    ? `<line x1="${x(pts[i][0]).toFixed(1)}" y1="${y(pts[i][1]).toFixed(1)}" x2="${x(p[0]).toFixed(1)}" y2="${y(p[1]).toFixed(1)}"/>`
    : "").join("");
  const top = Math.max(...pts.map((p) => p[1]));
  return `
    <figure class="route-elevation">
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img"
           aria-label="출발점보다 가장 높은 곳이 ${Math.round(top)}미터 높아요">
        <polygon points="${area}" fill="${color}" opacity="0.16"/>
        <polyline points="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
        <g class="steep-lines">${steep}</g>
      </svg>
      <figcaption><span>출발</span><span class="steep-key">가파른 구간</span><span>도착</span></figcaption>
    </figure>`;
}

function compareText(route, base) {
  const extra = route.length_m - base.length_m;
  const parts = [extra > 0 ? `${extra}m 더 걷고` : extra < 0 ? `${-extra}m 덜 걷고` : "거리는 같고"];
  const stairs = base.stairs - route.stairs;
  if (stairs > 0) parts.push(`계단 ${stairs}곳을 피해요`);
  if (route.steep_m !== null && base.steep_m !== null) {
    const steep = base.steep_m - route.steep_m;
    if (steep > 0) parts.push(`가파른 구간이 ${steep}m 줄어요`);
    else if (steep < 0) parts.push(`가파른 구간이 ${-steep}m 늘어요`);
  }
  return `최단 경로보다 ${parts.join(", ")}`;
}

function recommendationText(routes) {
  if (routes[0].warnings.some((w) => w.includes("우회 불가"))) return "";
  if (routes.length === 1) return "이 구간은 최단 경로가 가장 편한 길이에요.";
  return `${routes[1].name}를 추천해요. ${compareText(routes[1], routes[0])}`;
}

function renderRoutes() {
  const advice = recommendationText(state.routes);
  $("#recommendation").textContent = advice;
  $("#recommendation").hidden = !advice;
  drawRouteLines();
  if (state.routes.length) {
    map.fitBounds(L.polyline(state.routes.flatMap((r) => r.coords)).getBounds(), { padding: [24, 24] });
  }
  const scale = elevationScale(state.routes);
  $("#slope-note").hidden = !scale;
  $("#reverse-btn").hidden = false;
  $("#route-list").innerHTML = state.routes.map((r, i) => `
    <li class="route-card ${i === state.selected ? "is-selected" : ""}" data-index="${i}" style="--route:${ROUTE_COLOR[i]}">
      <button type="button" class="route-select" aria-pressed="${i === state.selected}">
        <h3 class="route-name">${esc(r.name)}</h3>
        <p class="route-headline">${r.length_m}m, ${r.minutes}분</p>
      </button>
      ${i > 0 ? `<p class="route-compare">${esc(compareText(r, state.routes[0]))}</p>` : ""}
      ${elevationChart(r, ROUTE_COLOR[i], scale)}
      <dl class="route-stats">
        <div><dt>계단</dt><dd class="stat-stairs ${r.stairs ? "is-alert" : ""}">${r.stairs}곳</dd></div>
        <div><dt>턱</dt><dd class="stat-curbs">${r.curbs}곳</dd></div>
        <div><dt>최대 경사</dt><dd class="stat-grade">${gradeText(r.max_grade)}</dd></div>
        <div><dt>가파른 구간</dt><dd class="stat-steep">${withUnit(r.steep_m, "m")}</dd></div>
        <div><dt>가파른 오르막</dt><dd class="stat-steep-up">${withUnit(r.steep_up_m, "m")}</dd></div>
        <div><dt>가파른 내리막</dt><dd class="stat-steep-down">${withUnit(r.steep_down_m, "m")}</dd></div>
      </dl>
      ${r.sources.length ? `<p class="route-source">장애물 정보: ${r.sources.map((s) => esc(SOURCE_LABEL[s] ?? s)).join(", ")}</p>` : ""}
      ${r.warnings.length ? `<ul class="route-warnings">${r.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    </li>`).join("");
}

$("#route-list").addEventListener("click", (e) => {
  const card = e.target.closest(".route-card");
  if (!card) return;
  state.selected = Number(card.dataset.index);
  document.querySelectorAll(".route-card").forEach((c) => {
    const on = c === card;
    c.classList.toggle("is-selected", on);
    c.querySelector(".route-select").setAttribute("aria-pressed", on);
  });
  drawRouteLines();
});

// ---------- 출입구 ----------
async function loadEntrances([lat, lon]) {
  const items = await api(`/api/entrances?lat=${lat}&lon=${lon}`);
  entranceLayer.clearLayers();
  $("#entrance-empty").hidden = items.length > 0;
  $("#entrance-list").innerHTML = items.map((e) => `
    <li class="entrance-item" data-type="${esc(e.type)}">
      <strong class="entrance-name">${esc(e.name)}</strong>
      <span class="entrance-distance">도착지에서 ${e.distance_m}m</span>
      <span class="entrance-checked">마지막 확인 ${esc(e.checked_at)}</span>
    </li>`).join("");
  items.forEach((e) => L.marker([e.lat, e.lon]).bindTooltip(e.name).addTo(entranceLayer));
}

// ---------- 제보 ----------
$("#report-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const at = state.reportAt;
  if (!at) { $("#report-status").textContent = "지도를 눌러 제보 위치를 먼저 고르세요."; return; }
  const f = new FormData(e.target);
  try {
    await postJSON("/api/reports", {
      lat: at[0], lon: at[1],
      profile: state.profile,
      kind: f.get("kind"),
      obstacle: f.get("obstacle") || null,
      needed_help: f.has("needed_help"),
      memo: f.get("memo"),
    });
    e.target.reset();
    $("#report-status").textContent = "제보를 보냈어요.";
  } catch (err) {
    console.error(err);
    $("#report-status").textContent = "제보를 보내지 못했어요. 인터넷 연결을 확인하고 다시 보내 주세요.";
  }
});

showStep("search");
loadProfiles().catch((err) => { console.error(err); setStatus("서버에 연결하지 못했어요."); });
loadObstacles().catch(console.error);
loadPlaces().catch(console.error);
