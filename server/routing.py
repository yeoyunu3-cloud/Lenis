"""보행 도로망 + 장애물 + 경사 → 사용자 유형별 경로 계산."""
import math
import os
from functools import lru_cache
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd
import requests

import slope
from profiles import GRADE_HARD, GRADE_SOFT, PROFILES

DATA = Path(__file__).resolve().parent.parent / "data"
# 가짜 데이터는 화면 테스트에서만 쓴다: USE_SAMPLE_DATA=1 uvicorn main:app
USE_SAMPLE_DATA = os.environ.get("USE_SAMPLE_DATA") == "1"
DETECTIONS = DATA / ("sample" if USE_SAMPLE_DATA else "processed") / "detections.csv"
OSM_STEPS = DATA / "processed" / "osm_steps.csv"

# TODO: 조사 생활권이 정해지면 바꾸기 (지금은 초량동 근처 예시)
CENTER = (35.117, 129.0375)
RADIUS_M = 1000
GRAPH_FILE = DATA / "processed" / f"walk_graph_{CENTER[0]}_{CENTER[1]}_{RADIUS_M}.graphml"
# 서버가 바쁘면(502·504) 다음 서버로 넘어간다
OVERPASS_SERVERS = [
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.kumi.systems/api",
]

MIN_CONF = 0.5          # 이 확신도 이상인 탐지만 경로에 반영
LEVEL_GRADE = 1.0       # 경사가 이 값(%) 이하면 오르막·내리막 길이에 넣지 않음
CLIMB_COST = 30.0       # 오르막 최소 경로: 1m 오르는 부담을 30m 더 걷는 것으로 계산


def in_service_area(df):
    """도로망을 받은 범위 안에 있는 행."""
    dlat = RADIUS_M / 111_000
    dlon = dlat / math.cos(math.radians(CENTER[0]))
    return ((df["lat"] - CENTER[0]).abs() <= dlat) & ((df["lon"] - CENTER[1]).abs() <= dlon)


def load_detections():
    """서비스 지역 안의 탐지만 읽는다. 다른 동네의 탐지가 가장 가까운 길에 잘못 붙지 않게 한다."""
    if DETECTIONS.exists():
        df = pd.read_csv(DETECTIONS, dtype={"image_id": str})
        if "source" not in df:
            df["source"] = "ai"
        return df[in_service_area(df)]
    return pd.DataFrame(columns=["image_id", "class", "conf", "lat", "lon", "source"])


def tag_values(value):
    """OSM 태그값. 구간이 합쳐지면 목록으로 들어오므로 항상 목록으로 돌려준다."""
    return value if isinstance(value, list) else [value]


def has_tag(d, key):
    return any(v not in (None, "no") for v in tag_values(d.get(key)))


def edge_coords(G, u, v, d):
    """u에서 v로 가는 순서의 (경도, 위도) 목록."""
    start, end = (G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])
    if "geometry" not in d:
        return [start, end]
    coords = list(d["geometry"].coords)
    gap = lambda p, q: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
    return coords if gap(coords[0], start) <= gap(coords[-1], start) else coords[::-1]


def add_slope(G):
    """DEM으로 방향별 경사를 계산해 d['segments'] = [(길이 m, 경사 %), ...]에 넣는다.
    DEM이 없거나 고도를 모르는 구간은 None으로 두고 평지로 간주하지 않는다."""
    xs = [n["x"] for n in G.nodes.values()]
    ys = [n["y"] for n in G.nodes.values()]
    dem = slope.load_dem((min(xs), min(ys), max(xs), max(ys)))
    for u, v, d in G.edges(data=True):
        follow_terrain = not (has_tag(d, "bridge") or has_tag(d, "tunnel"))
        d["segments"] = slope.edge_segments(dem, edge_coords(G, u, v, d), d["length"], follow_terrain)


def attach_obstacles(G, det):
    for *_, d in G.edges(keys=True, data=True):
        d["obstacles"] = []
        if "steps" in tag_values(d.get("highway")):
            d["obstacles"].append({"class": "stairs", "conf": 1.0, "source": "osm"})
    use = det[det["conf"] >= MIN_CONF]
    if use.empty:
        return
    nearest = ox.distance.nearest_edges(G, X=use["lon"].tolist(), Y=use["lat"].tolist())
    for (u, v, _), row in zip(nearest, use.to_dict("records")):
        info = {"class": row["class"], "conf": float(row["conf"]), "source": row["source"]}
        for a, b in ((u, v), (v, u)):   # 양방향 모두 표시
            if G.has_edge(a, b):
                for k in G[a][b]:
                    G[a][b][k]["obstacles"].append(info)


def download_graph():
    ox.settings.overpass_rate_limit = False
    for url in OVERPASS_SERVERS:
        ox.settings.overpass_url = url
        try:
            return ox.graph_from_point(CENTER, dist=RADIUS_M, network_type="walk")
        except (requests.RequestException, ValueError) as e:
            print(f"도로망 받기 실패 ({url}): {str(e)[:80]}")
    raise RuntimeError("모든 Overpass 서버가 응답하지 않습니다. 몇 분 뒤 다시 실행하세요.")


def load_graph():
    """저장한 도로망이 있으면 인터넷 없이 읽는다."""
    if GRAPH_FILE.exists():
        return ox.load_graphml(GRAPH_FILE)
    G = download_graph()
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, GRAPH_FILE)
    return G


@lru_cache(maxsize=1)
def get_graph():
    """처음 한 번만 만들어 메모리에 둔다."""
    G = load_graph()
    add_slope(G)
    attach_obstacles(G, load_detections())
    return G


def grade_multiplier(grade, profile):
    """경사 구간의 비용 배수. grade는 이동 방향 기준(+ 오르막, - 내리막). None이면 지나갈 수 없음."""
    steepness = abs(grade)
    if steepness <= GRADE_SOFT:
        return 1.0
    penalty = profile["grade_penalty"]["hard" if steepness > GRADE_HARD else "soft"]
    if penalty is None:
        return None
    if steepness > GRADE_HARD and penalty > 1.0:
        penalty *= steepness / GRADE_HARD      # 8.3%를 넘으면 가파를수록 더 피한다
    factor = 1.0 if grade > 0 else profile["downhill_factor"]
    return 1.0 + (penalty - 1.0) * factor


def obstacle_classes(d):
    """구간의 장애물 종류를 (확인된 것, AI 추정만 있는 것)으로 나눈다."""
    confirmed = {ob["class"] for ob in d["obstacles"] if ob["source"] != "ai"}
    estimated = {ob["class"] for ob in d["obstacles"] if ob["source"] == "ai"} - confirmed
    return confirmed, estimated


def edge_cost(d, profile):
    """구간 하나의 비용. None이면 지나갈 수 없음.
    같은 장애물을 사진 여러 장에서 찾아도 구간마다 한 번만 계산한다."""
    cost = d["length"]
    if d.get("segments"):
        cost = 0.0
        for length, grade in d["segments"]:
            multiplier = grade_multiplier(grade, profile)
            if multiplier is None:
                return None
            cost += length * multiplier
    confirmed, estimated = obstacle_classes(d)
    penalties = [profile["obstacle_penalty"].get(c, 1.0) for c in confirmed]
    penalties += [profile["ai_penalty"].get(c, 1.0) for c in estimated]
    for p in penalties:
        if p is None:
            return None
        cost *= p
    return cost


def climb_m(d):
    """구간에서 올라가는 높이(m)."""
    return sum(piece * max(grade, 0.0) / 100 for piece, grade in d.get("segments") or [])


def total_cost(d, profile, climb_cost=0.0):
    cost = edge_cost(d, profile)
    return None if cost is None else cost + climb_cost * climb_m(d)


def make_weight(profile, climb_cost=0.0):
    def weight(u, v, edges):        # MultiDiGraph: edges = {key: data}
        costs = [c for c in (total_cost(d, profile, climb_cost) for d in edges.values()) if c is not None]
        return min(costs) if costs else None
    return weight


def shortest_edge(edges):
    return min(edges.values(), key=lambda d: d["length"])


def cheapest_edge(profile, climb_cost=0.0):
    def pick(edges):
        costs = {k: total_cost(d, profile, climb_cost) for k, d in edges.items()}
        return edges[min((k for k, c in costs.items() if c is not None), key=costs.get)]
    return pick


def summarize(G, route, profile, name, pick=shortest_edge):
    length, max_grade, sources = 0.0, None, set()
    known = steep = steep_up = steep_down = uphill = downhill = distance = rise = 0.0
    elevation = [[0, 0.0, False]]   # [출발점부터 거리 m, 출발점 대비 높이 m, 가파른 구간 여부]
    path = [[G.nodes[route[0]]["y"], G.nodes[route[0]]["x"]]]
    steep_lines = []                # 지도에 표시할 가파른 구간 [[위도, 경도], [위도, 경도]]
    counts = {"stairs": 0, "curb": 0}
    estimated_count = blocked = 0
    for a, b in zip(route[:-1], route[1:]):
        d = pick(G[a][b])
        length += d["length"]
        sources |= {ob["source"] for ob in d["obstacles"]}
        confirmed, estimated = obstacle_classes(d)
        for c in counts:
            counts[c] += c in confirmed | estimated
        estimated_count += len(estimated & set(counts))
        blocked += edge_cost(d, profile) is None
        coords = edge_coords(G, a, b, d)
        path += [[lat, lon] for lon, lat in coords[1:]]
        segments = d.get("segments") or []
        for (piece, grade), (p, q) in zip(segments, slope.segment_lines(coords, len(segments)) if segments else []):
            if abs(grade) > GRADE_SOFT:
                steep_lines.append([[p[1], p[0]], [q[1], q[0]]])
            known += piece
            max_grade = max(max_grade or 0.0, abs(grade))
            steep += piece if abs(grade) > GRADE_SOFT else 0.0
            steep_up += piece if grade > GRADE_SOFT else 0.0
            steep_down += piece if grade < -GRADE_SOFT else 0.0
            uphill += piece if grade > LEVEL_GRADE else 0.0
            downhill += piece if grade < -LEVEL_GRADE else 0.0
            distance += piece
            rise += piece * grade / 100
            elevation.append([round(distance), round(rise, 1), abs(grade) > GRADE_SOFT])
    warnings = []
    if blocked:
        warnings.append(f"{profile['label']}로 지나가기 어려운 구간이 {blocked}곳 있습니다")
    if estimated_count:
        warnings.append(f"AI가 추정한 장애물 {estimated_count}곳은 현장 확인이 필요합니다")
    if length and not known:
        warnings.append("경사 데이터가 없어 경사를 반영하지 못했습니다")
    elif known < length * 0.95:
        warnings.append("일부 구간은 경사 정보가 없습니다")
    return {
        "name": name,
        "coords": path,
        "steep_lines": steep_lines,
        "length_m": round(length),
        "minutes": round(length / profile["speed_mps"] / 60, 1),
        "stairs": counts["stairs"],
        "curbs": counts["curb"],
        "max_grade": None if max_grade is None else round(max_grade, 1),
        "steep_m": round(steep) if known else None,
        "steep_up_m": round(steep_up) if known else None,
        "steep_down_m": round(steep_down) if known else None,
        "uphill_m": round(uphill) if known else None,
        "downhill_m": round(downhill) if known else None,
        "elevation": elevation if known else [],
        "sources": sorted(sources),
        "warnings": warnings,
    }


def find_routes(start, end, profile_key):
    """start, end = (위도, 경도). 최단 / 맞춤 / 오르막 최소 경로를 돌려준다.
    오르막 최소 경로는 앞의 두 경로보다 오르막이 실제로 짧을 때만 넣는다."""
    G = get_graph()
    profile = PROFILES[profile_key]
    o = ox.distance.nearest_nodes(G, X=start[1], Y=start[0])
    t = ox.distance.nearest_nodes(G, X=end[1], Y=end[0])

    shortest = nx.shortest_path(G, o, t, weight="length")
    routes = [summarize(G, shortest, profile, "최단 경로")]
    try:
        easy = nx.shortest_path(G, o, t, weight=make_weight(profile))
    except nx.NetworkXNoPath:
        routes[0]["warnings"].append("계단·급경사·장애물을 피해 갈 수 있는 길이 없습니다 (우회 불가 – 주의 구간)")
        return routes
    if easy == shortest:
        routes[0]["warnings"].append("이 구간은 더 편한 우회 경로를 찾지 못했습니다")
    else:
        routes.append(summarize(G, easy, profile, f"{profile['label']} 맞춤 경로", cheapest_edge(profile)))
    least_climb = nx.shortest_path(G, o, t, weight=make_weight(profile, CLIMB_COST))
    if least_climb not in (shortest, easy):
        third = summarize(G, least_climb, profile, "오르막 최소 경로", cheapest_edge(profile, CLIMB_COST))
        if third["uphill_m"] is not None and third["uphill_m"] < min(r["uphill_m"] for r in routes):
            routes.append(third)
    return routes


def osm_stairs_nearby():
    """조사 지역 안의 OSM 계단 위치 (지도 표시용)."""
    if not OSM_STEPS.exists():
        return []
    df = pd.read_csv(OSM_STEPS, usecols=["lat", "lon"])
    near = df[in_service_area(df)]
    return [{"class": "stairs", "conf": 1.0, "lat": r.lat, "lon": r.lon, "source": "osm"} for r in near.itertuples()]


def list_obstacles():
    det = load_detections()
    found = det[det["conf"] >= MIN_CONF][["class", "conf", "lat", "lon", "source"]].to_dict("records")
    return osm_stairs_nearby() + found
