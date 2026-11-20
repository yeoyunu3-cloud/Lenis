"""0단계: OpenStreetMap에서 부산 계단(highway=steps) 위치를 받는다.

출력: data/processed/osm_steps.csv      (계단마다 한 줄: id, 위도·경도, 태그)
      data/processed/osm_steps.geojson  (지도 프로그램·folium에서 바로 열 수 있음)
출처 표기: "© OpenStreetMap contributors (ODbL)"
"""
import json
import time

import pandas as pd
import requests

from config import BASE

# 서버가 바쁘면(502·504) 다음 서버로 넘어간다
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# (남쪽 위도, 서쪽 경도, 북쪽 위도, 동쪽 경도) — 부산 도심. 시범 지역만 받으려면 좁히기
BBOX = (35.05, 128.95, 35.25, 129.15)
TAGS = ["step_count", "incline", "handrail", "ramp", "ramp:wheelchair", "ramp:stroller", "width", "name"]

OUT_DIR = BASE / "processed"


def fetch():
    query = f'[out:json][timeout:90];way["highway"="steps"]{BBOX};out geom tags;'
    for url in OVERPASS_SERVERS:
        for wait in (5, 15, 45):    # 바쁠 때는 기다렸다가 같은 서버에 다시
            try:
                r = requests.post(url, data={"data": query},
                                  headers={"User-Agent": "busan-easy-route/0.1"}, timeout=120)
                r.raise_for_status()
                return r.json()["elements"]
            except (requests.RequestException, ValueError) as e:
                print(f"실패 ({url}): {str(e)[:80]} → {wait}초 뒤 다시")
                time.sleep(wait)
    raise SystemExit("모든 Overpass 서버가 응답하지 않습니다. 몇 분 뒤 다시 실행하세요.")


def to_rows(ways):
    rows = []
    for w in ways:
        pts = w.get("geometry", [])
        if not pts:
            continue
        tags = w.get("tags", {})
        rows.append({
            "osm_id": w["id"],
            "lat": sum(p["lat"] for p in pts) / len(pts),   # 계단 가운데 위치
            "lon": sum(p["lon"] for p in pts) / len(pts),
            "start_lat": pts[0]["lat"], "start_lon": pts[0]["lon"],
            "end_lat": pts[-1]["lat"], "end_lon": pts[-1]["lon"],
            **{t: tags.get(t) for t in TAGS},
        })
    return pd.DataFrame(rows)


def to_geojson(ways):
    features = [{
        "type": "Feature",
        "properties": {"osm_id": w["id"], **w.get("tags", {})},
        "geometry": {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in w["geometry"]]},
    } for w in ways if w.get("geometry")]
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    ways = fetch()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = to_rows(ways)
    df.to_csv(OUT_DIR / "osm_steps.csv", index=False)
    (OUT_DIR / "osm_steps.geojson").write_text(json.dumps(to_geojson(ways), ensure_ascii=False), encoding="utf-8")
    print("계단 수:", len(df))
    print("태그가 있는 계단 수:", {t: int(df[t].notna().sum()) for t in TAGS})
