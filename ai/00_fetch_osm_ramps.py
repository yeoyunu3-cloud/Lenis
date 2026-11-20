"""0단계: OpenStreetMap에서 부산 경사로 위치를 받는다.

받는 것 (kind 열)
  ramp_way        경사로 길          way ramp=yes / ramp:wheelchair=yes (계단 옆 경사로 포함)
  lowered_kerb    턱 낮춘 곳(연석 경사로)  node kerb=lowered|flush
  ramp_entrance   경사로·휠체어 출입구    node entrance=* + ramp=yes 또는 wheelchair=yes|limited

출력: data/processed/osm_ramps.csv            (한 줄에 하나: id, kind, 위도·경도, 태그)
      data/processed/osm_ramps.geojson        (지도 프로그램·folium에서 바로 열 수 있음)
      data/processed/osm_ramp_entrances.json  (data/sample/entrances.json 과 같은 형식)
출처 표기: "© OpenStreetMap contributors (ODbL)"
"""
import importlib
import json
import time
from datetime import date

import pandas as pd
import requests

# 계단 스크립트의 Overpass 서버 목록·출력 폴더를 그대로 쓴다 (파일 이름이 숫자로 시작해 importlib 사용)
steps = importlib.import_module("00_fetch_osm_steps")
OUT_DIR = steps.OUT_DIR
# 부산광역시 행정 경계 전체 (ISO3166-2 KR-26). 네모 범위(BBOX) 대신 경계 안만 받는다
AREA = 'area["ISO3166-2"="KR-26"]->.busan;'

TAGS = ["highway", "ramp", "ramp:wheelchair", "ramp:stroller", "kerb", "entrance",
        "wheelchair", "incline", "width", "surface", "handrail", "name"]

QUERY = f"""[out:json][timeout:180];
{AREA}
(
  way["ramp"="yes"](area.busan);
  way["ramp:wheelchair"="yes"](area.busan);
  node["kerb"~"^(lowered|flush)$"](area.busan);
  node["entrance"]["ramp"="yes"](area.busan);
  node["entrance"]["wheelchair"~"^(yes|limited)$"](area.busan);
);
out geom tags;"""


def fetch():
    # 계단 스크립트와 같은 재시도 방식. 쿼리만 다르다
    for url in steps.OVERPASS_SERVERS:
        for wait in (5, 15, 45):
            try:
                r = requests.post(url, data={"data": QUERY},
                                  headers={"User-Agent": "busan-easy-route/0.1"}, timeout=120)
                r.raise_for_status()
                return r.json()["elements"]
            except (requests.RequestException, ValueError) as e:
                print(f"실패 ({url}): {str(e)[:80]} → {wait}초 뒤 다시")
                time.sleep(wait)
    raise SystemExit("모든 Overpass 서버가 응답하지 않습니다. 몇 분 뒤 다시 실행하세요.")


def kind_of(el):
    t = el.get("tags", {})
    if el["type"] == "way":
        return "ramp_way"
    if "entrance" in t:
        return "ramp_entrance"
    return "lowered_kerb"


def points_of(el):
    if el["type"] == "node":
        return [{"lat": el["lat"], "lon": el["lon"]}]
    return el.get("geometry", [])


def to_rows(elements):
    rows = []
    for el in elements:
        pts = points_of(el)
        if not pts:
            continue
        tags = el.get("tags", {})
        rows.append({
            "osm_id": f'{el["type"]}/{el["id"]}',
            "kind": kind_of(el),
            "lat": sum(p["lat"] for p in pts) / len(pts),   # 길이면 가운데 위치
            "lon": sum(p["lon"] for p in pts) / len(pts),
            "start_lat": pts[0]["lat"], "start_lon": pts[0]["lon"],
            "end_lat": pts[-1]["lat"], "end_lon": pts[-1]["lon"],
            **{t: tags.get(t) for t in TAGS},
        })
    return pd.DataFrame(rows)


def to_geojson(elements):
    features = []
    for el in elements:
        pts = points_of(el)
        if not pts:
            continue
        coords = [[p["lon"], p["lat"]] for p in pts]
        geom = ({"type": "Point", "coordinates": coords[0]} if el["type"] == "node"
                else {"type": "LineString", "coordinates": coords})
        features.append({
            "type": "Feature",
            "properties": {"osm_id": f'{el["type"]}/{el["id"]}', "kind": kind_of(el), **el.get("tags", {})},
            "geometry": geom,
        })
    return {"type": "FeatureCollection", "features": features}


def to_entrances(df):
    """entrances.json 형식으로 바꾼다. 서버가 샘플 대신 이 파일을 읽게 할 수 있다."""
    today = date.today().isoformat()
    out = []
    for r in df[df["kind"] == "ramp_entrance"].itertuples():
        out.append({
            "name": r.name if isinstance(r.name, str) else "(이름 없음) 경사로 출입구",
            "type": "ramp_entrance",
            "lat": round(r.lat, 7),
            "lon": round(r.lon, 7),
            "note": f"OSM {r.osm_id} wheelchair={r.wheelchair} ramp={r.ramp}",
            "source": "osm",
            "checked_at": today,
        })
    return out


if __name__ == "__main__":
    elements = fetch()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = to_rows(elements)
    df.to_csv(OUT_DIR / "osm_ramps.csv", index=False)
    (OUT_DIR / "osm_ramps.geojson").write_text(
        json.dumps(to_geojson(elements), ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "osm_ramp_entrances.json").write_text(
        json.dumps(to_entrances(df), ensure_ascii=False, indent=2), encoding="utf-8")
    print("전체:", len(df))
    print("종류별:", df["kind"].value_counts().to_dict() if len(df) else {})
