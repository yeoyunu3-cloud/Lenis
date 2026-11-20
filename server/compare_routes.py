"""네이버지도 경로와 편한길로 경로를 같은 기준으로 비교한다.

1. docs/네이버_경로_입력.json 의 naver_walk(일반), naver_no_stairs(계단회피)에
   네이버지도에서 본 거리(m), 계단 수, 경로가 꺾이는 지점의 좌표 [위도, 경도]를 적는다.
2. server 폴더에서 python compare_routes.py 를 실행한다.
3. 결과: docs/경로_비교_검증표.md

경사는 30m 고도 자료로 추정한 값이다. 네이버 칸이 비어 있으면 '입력 필요'로 표시하고 비교 결론을 쓰지 않는다.
"""
import json
import sys
from pathlib import Path

import networkx as nx
import osmnx as ox

import routing
from profiles import PROFILES

DOCS = Path(__file__).resolve().parent.parent / "docs"
INPUT = DOCS / "네이버_경로_입력.json"
OUTPUT = DOCS / "경로_비교_검증표.md"
LENGTH_GAP = 0.15       # 입력한 거리와 경유점으로 계산한 거리가 이 비율 이상 다르면 경고


def nodes_through(G, points):
    """경유점을 차례로 잇는 도로망 노드 목록."""
    stops = [ox.distance.nearest_nodes(G, X=lon, Y=lat) for lat, lon in points]
    route = [stops[0]]
    for a, b in zip(stops[:-1], stops[1:]):
        route += nx.shortest_path(G, a, b, weight="length")[1:]
    return route


def show(value, unit):
    return "입력 필요" if value is None else f"{value}{unit}"


def row(name, length, stairs, summary):
    summary = summary or {}
    return (f"| {name} | {show(length, 'm')} | {show(stairs, '곳')} | {show(summary.get('max_grade'), '%')} "
            f"| {show(summary.get('steep_m'), 'm')} | {show(summary.get('uphill_m'), 'm')} |")


def naver_summary(G, profile, entry):
    if len(entry.get("waypoints", [])) < 2:
        return None
    return routing.summarize(G, nodes_through(G, entry["waypoints"]), profile, "네이버")


def compare(trip, G):
    profile = PROFILES[trip["profile"]]
    routes = routing.find_routes(trip["start"], trip["end"], trip["profile"])
    shortest, easy = routes[0], routes[-1] if len(routes) == 1 else routes[1]
    lines = [f"## {trip['name']} ({profile['label']})", "",
             "| 경로 | 거리 | 계단 | 최대 경사 | 가파른 구간 | 오르막 |", "|---|---|---|---|---|---|",
             row("편한길로 최단", shortest["length_m"], shortest["stairs"], shortest)]
    naver = {}
    for key, label in (("naver_walk", "네이버 일반"), ("naver_no_stairs", "네이버 계단회피")):
        entry = trip.get(key, {})
        naver[key] = naver_summary(G, profile, entry)
        lines.append(row(label, entry.get("length_m"), entry.get("stairs"), naver[key]))
    lines.append(row("**편한길로 맞춤**", easy["length_m"], easy["stairs"], easy))
    lines.append("")

    for key, label in (("naver_walk", "네이버 일반"), ("naver_no_stairs", "네이버 계단회피")):
        length, summary = trip.get(key, {}).get("length_m"), naver[key]
        if length and summary and abs(summary["length_m"] - length) / length > LENGTH_GAP:
            lines += [f"- {label}: 경유점으로 계산한 거리({summary['length_m']}m)가 입력값과 달라 좌표 확인이 필요합니다.", ""]
    target = naver["naver_no_stairs"]
    entry = trip.get("naver_no_stairs", {})
    if target and entry.get("length_m") is not None:
        steep = target["steep_m"] - easy["steep_m"]
        extra = easy["length_m"] - entry["length_m"]
        lines += [f"- 네이버 계단회피 대비: 가파른 구간 {abs(steep)}m {'감소' if steep >= 0 else '증가'}, "
                  f"거리 {abs(extra)}m {'증가' if extra >= 0 else '감소'}", ""]
    return lines


def main(source=INPUT, target=OUTPUT):
    trips = json.loads(Path(source).read_text(encoding="utf-8"))
    G = routing.get_graph()
    lines = ["# 네이버지도 경로 비교 검증표", "",
             "같은 출발지·도착지로 비교합니다. 경사는 30m 고도 자료(FABDEM)로 추정한 값이며, 현장 측정값이 아닙니다.", ""]
    for trip in trips:
        lines += compare(trip, G)
    Path(target).write_text("\n".join(lines), encoding="utf-8")
    print("저장:", target)


if __name__ == "__main__":
    main(*sys.argv[1:3])
