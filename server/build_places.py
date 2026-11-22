"""장소 검색 목록(web/places.json)을 부산 전체로 만든다. OpenStreetMap의 이름 있는 장소를 모은다.

실행: cd server && .venv/bin/python build_places.py
고를 장소: 유아차·캐리어 이용자가 목적지로 찾을 만한 곳 (역, 병원, 주민센터, 학교, 공원, 관광지, 큰 상점 등).
식당·카페처럼 너무 많은 곳은 넣지 않는다 (검색 목록이 휴대폰에서 무거워진다).
"""
import json
import math
from pathlib import Path

import requests

from area import BUSAN_BOUNDS
from routing import OVERPASS_SERVERS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "places.json"
SEED = ROOT / "data" / "processed" / "places_seed.json"   # OSM 분류로 안 잡히지만 꼭 있어야 하는 장소 (시연 구간 등)
AMENITY = ("hospital|clinic|doctors|pharmacy|townhall|community_centre|social_facility|library|school|university|"
           "college|kindergarten|childcare|post_office|police|fire_station|bus_station|ferry_terminal|marketplace|"
           "arts_centre|theatre|cinema|place_of_worship|toilets|parking")
SHOP = "mall|department_store|supermarket"
QUERY = f"""
[out:json][timeout:300];
area["name"="부산광역시"]["admin_level"="4"]->.busan;
(
  nwr["name"]["amenity"~"^({AMENITY})$"](area.busan);
  nwr["name"]["tourism"](area.busan);
  nwr["name"]["leisure"~"^(park|stadium|sports_centre|playground)$"](area.busan);
  nwr["name"]["shop"~"^({SHOP})$"](area.busan);
  nwr["name"]["railway"~"^(station|halt)$"](area.busan);
  nwr["name"]["public_transport"="station"](area.busan);
  nwr["name"]["office"="government"](area.busan);
  nwr["name"]["historic"](area.busan);
  nwr["name"]["natural"~"^(beach|peak)$"](area.busan);
  nwr["name"]["place"~"^(suburb|quarter|neighbourhood|village|island|islet)$"](area.busan);
  nwr["name"]["building"~"^(hospital|school|university|train_station|public|civic|government)$"](area.busan);
);
out center tags;
"""
SKIP_AMENITY_WITHOUT_KO = {"toilets", "parking"}   # 이름 없는 화장실·주차장 이름이 '화장실'만인 경우가 많다


def fetch():
    for url in OVERPASS_SERVERS:
        try:
            res = requests.post(f"{url}/interpreter", data={"data": QUERY}, timeout=360,
                                headers={"User-Agent": "lenis-places/1.0"})   # 기본 이름이면 406으로 막힌다
            res.raise_for_status()
            return res.json()["elements"]
        except (requests.RequestException, ValueError) as e:
            print(f"Overpass 실패 ({url}): {str(e)[:80]}")
    raise RuntimeError("모든 Overpass 서버가 응답하지 않습니다.")


def close(a, b, meters=150):
    dy = (a["lat"] - b["lat"]) * 111_000
    dx = (a["lon"] - b["lon"]) * 111_000 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy) <= meters


def main():
    west, south, east, north = BUSAN_BOUNDS
    by_name = {}
    for place in json.loads(SEED.read_text(encoding="utf-8")) if SEED.exists() else []:
        by_name.setdefault(place["name"], []).append(place)
    for e in fetch():
        tags = e.get("tags", {})
        name = (tags.get("name:ko") or tags.get("name") or "").strip()
        lat, lon = e.get("lat", e.get("center", {}).get("lat")), e.get("lon", e.get("center", {}).get("lon"))
        if not name or lat is None or not (south <= lat <= north and west <= lon <= east):
            continue
        if tags.get("amenity") in SKIP_AMENITY_WITHOUT_KO and len(name) <= 4:
            continue
        place = {"name": name, "lat": round(lat, 7), "lon": round(lon, 7)}
        same = by_name.setdefault(name, [])
        if not any(close(place, p) for p in same):   # 같은 이름이 가까이 여러 개면 하나만
            same.append(place)
    places = []
    for name, items in by_name.items():
        places.extend(items)
    places.sort(key=lambda p: p["name"])
    OUT.write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(places)}곳 → {OUT} ({OUT.stat().st_size // 1000}KB)")


if __name__ == "__main__":
    main()
