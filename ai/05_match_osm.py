"""5단계: AI 탐지 결과를 OSM 계단과 비교한다.

입력: data/processed/detections.csv, mapillary/images.csv, osm_steps.csv
출력: data/processed/new_obstacle_candidates.csv  지도에 없는 장애물 후보 (사진을 보고 verified 칸에 yes/no 입력)
      data/processed/osm_match_summary.json       발표용 숫자
"새로 찾은 계단"은 verified가 yes인 것만 센다. 확인하지 않은 후보는 성과로 쓰지 않는다.
"""
import csv
import json
import math

from config import BASE, CONF, DETECTIONS_CSV, MAPILLARY_DIR

PROCESSED = BASE / "processed"
OSM_STEPS = PROCESSED / "osm_steps.csv"
CANDIDATES = PROCESSED / "new_obstacle_candidates.csv"
SUMMARY = PROCESSED / "osm_match_summary.json"

MERGE_M = 15        # 이 거리 안의 같은 종류 탐지는 하나로 합친다
MATCH_M = 20        # 탐지에서 이 거리 안에 OSM 계단이 있으면 일치
PHOTO_M = 30        # OSM 계단에서 이 거리 안에 사진이 있으면 AI가 볼 수 있었던 계단
COLUMNS = ["class", "lat", "lon", "photos", "best_conf", "image_id", "view", "photo_file", "photo_url", "verified"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def distance_m(a, b):
    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


class Nearby:
    """가까운 점만 빠르게 찾기 위한 격자."""

    def __init__(self, points, cell_m):
        self.cell = cell_m / 111_320
        self.grid = {}
        for index, point in enumerate(points):
            self.grid.setdefault(self._key(point), []).append((index, point))

    def _key(self, point):
        return math.floor(point[0] / self.cell), math.floor(point[1] / self.cell)

    def within(self, point, radius_m):
        row, col = self._key(point)
        reach = math.ceil(radius_m / 111_320 / self.cell / math.cos(math.radians(point[0])))
        for r in range(row - reach, row + reach + 1):
            for c in range(col - reach, col + reach + 1):
                for index, other in self.grid.get((r, c), []):
                    if distance_m(point, other) <= radius_m:
                        yield index


def merge(detections):
    """같은 장애물이 사진 여러 장에 찍힌 것을 하나로 합친다."""
    points = [(float(d["lat"]), float(d["lon"])) for d in detections]
    parent = list(range(len(points)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    nearby = Nearby(points, MERGE_M)
    for i, point in enumerate(points):
        for j in nearby.within(point, MERGE_M):
            parent[root(i)] = root(j)
    groups = {}
    for i, detection in enumerate(detections):
        groups.setdefault(root(i), []).append((points[i], detection))

    clusters = []
    for members in groups.values():
        best = max(members, key=lambda m: float(m[1]["conf"]))[1]
        clusters.append({
            "class": best["class"],
            "lat": round(sum(p[0] for p, _ in members) / len(members), 7),
            "lon": round(sum(p[1] for p, _ in members) / len(members), 7),
            "photos": len({m[1]["image_id"] for m in members}),
            "best_conf": float(best["conf"]),
            "image_id": best["image_id"],
            "view": best["view"],
        })
    return clusters


def osm_stair_points(rows):
    """OSM 계단마다 가운데·양 끝 위치."""
    return [[(float(r[a]), float(r[b])) for a, b in (("lat", "lon"), ("start_lat", "start_lon"), ("end_lat", "end_lon"))]
            for r in rows]


def previous_reviews():
    if not CANDIDATES.exists():
        return {}
    return {r["image_id"] + r["class"]: r["verified"] for r in read_csv(CANDIDATES) if r["verified"]}


if __name__ == "__main__":
    detections = [d for d in read_csv(DETECTIONS_CSV) if float(d["conf"]) >= CONF]
    photos = [(float(r["lat"]), float(r["lon"])) for r in read_csv(MAPILLARY_DIR / "images.csv")]
    stairs = osm_stair_points(read_csv(OSM_STEPS))

    clusters = {c: merge([d for d in detections if d["class"] == c]) for c in ("stairs", "curb", "ramp")}
    ai_stairs = Nearby([(c["lat"], c["lon"]) for c in clusters["stairs"]], MATCH_M)
    photo_points = Nearby(photos, PHOTO_M)

    visible = [s for s in stairs if any(next(photo_points.within(p, PHOTO_M), None) is not None for p in s)]
    found = [s for s in visible if any(next(ai_stairs.within(p, MATCH_M), None) is not None for p in s)]

    osm_points = Nearby([p for s in stairs for p in s], MATCH_M)
    new_stairs = [c for c in clusters["stairs"]
                  if next(osm_points.within((c["lat"], c["lon"]), MATCH_M), None) is None]

    reviews = previous_reviews()
    candidates = new_stairs + clusters["curb"]
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for c in sorted(candidates, key=lambda c: (c["class"], -c["best_conf"])):
            writer.writerow({**c, "photo_file": f"mapillary/views/{c['image_id']}_{c['view']}.jpg",
                             "photo_url": f"https://www.mapillary.com/app/?pKey={c['image_id']}",
                             "verified": reviews.get(c["image_id"] + c["class"], "")})

    verified = lambda cls: sum(reviews.get(c["image_id"] + cls) == "yes" for c in candidates if c["class"] == cls)
    summary = {
        "분석한 사진 수": len(photos),
        "사진이 있는 OSM 계단": len(visible),
        "AI가 다시 찾은 OSM 계단": len(found),
        "OSM 재발견율(%)": round(len(found) / len(visible) * 100, 1) if visible else None,
        "지도에 없는 계단 후보": len(new_stairs),
        "사진으로 확인한 새 계단": verified("stairs"),
        "턱 후보": len(clusters["curb"]),
        "사진으로 확인한 턱": verified("curb"),
        "경사로 탐지 위치": len(clusters["ramp"]),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n후보 사진 확인: {CANDIDATES} 의 verified 칸에 yes 또는 no를 적고 다시 실행하세요.")
