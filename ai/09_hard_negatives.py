"""9단계: AI가 부산 사진에서 잘못 찾은 부분을 모아 v3 학습에 '장애물 없음' 사진으로 넣는다.

python 09_hard_negatives.py prepare   오탐 후보를 잘라 둔다
python 09_hard_negatives.py review    브라우저에서 사람이 확인한다 (http://localhost:8770)
python 09_hard_negatives.py build     확인한 사진으로 v3 학습 데이터를 만든다

부산 시험 사진(08_busan_test.py)과 그 주변 사진은 학습에 넣지 않는다. 넣으면 점수가 부풀려진다.
후보의 20%는 학습에서 빼 두었다가 v2와 v3의 오탐을 비교하는 데 쓴다 (11_compare_models.py).
"""
import csv
import json
import math
import os
import random
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import yaml

from config import BASE, CLASSES, CONF, DATASET_DIR, DETECTIONS_CSV, DEVICE, MAPILLARY_DIR, RUN_NAME, RUNS_DIR
from panorama import view_file

HARD = BASE / "processed" / "hard_negatives"
CROPS = HARD / "crops"
CANDIDATES = HARD / "candidates.csv"
DECISIONS = HARD / "decisions.json"
V3_DATASET = BASE / "processed" / "busan_obstacles_v3"
TEST_IMAGES = BASE / "raw" / "busan_labeled" / "images"
PAGE = Path(__file__).with_name("review_page.html")

TARGET = 300            # 사람이 확인할 후보 수
MIN_NEGATIVES = 100     # 학습에 넣을 최소 사진 수
PER_PLACE = 2           # 같은 장소(약 50m 칸)에서 고를 최대 후보 수
PLACE_DEGREE = 0.0005
TEST_GAP_M = 30         # 부산 시험 사진에서 이 거리 안의 사진은 쓰지 않는다
HOLDOUT = 0.2
MIN_CROP = 160
COLUMNS = ["file", "image_id", "view", "class", "conf", "lat", "lon", "split"]
PORT = 8770


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def distance_m(a, b):
    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def usable_views():
    """장애물을 찾은 화면 중 부산 시험 사진과 겹치지 않는 것."""
    places = {r["image_id"]: (float(r["lat"]), float(r["lon"])) for r in read_csv(MAPILLARY_DIR / "images.csv")}
    test_ids = {p.stem.rsplit("_", 1)[0] for p in TEST_IMAGES.glob("*.jpg")}
    if not test_ids:
        raise SystemExit("부산 시험 사진이 없습니다. 먼저 python 08_busan_test.py prepare 를 실행하세요.")
    test_places = [places[i] for i in test_ids if i in places]
    views = {(r["image_id"], r["view"]) for r in read_csv(DETECTIONS_CSV)}
    return [(i, v, places[i]) for i, v in sorted(views)
            if i not in test_ids and view_file(i, v).exists()
            and all(distance_m(places[i], t) > TEST_GAP_M for t in test_places)]


def find_boxes(views):
    from ultralytics import YOLO

    model = YOLO(str(RUNS_DIR / RUN_NAME / "weights" / "best.pt"))
    boxes = []
    for start in range(0, len(views), 16):
        batch = views[start:start + 16]
        results = model.predict([str(view_file(i, v)) for i, v, _ in batch], conf=CONF, device=DEVICE, verbose=False)
        for (image_id, view, place), result in zip(batch, results):
            for xyxy, cls, conf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
                boxes.append({"image_id": image_id, "view": view, "place": place, "xyxy": xyxy,
                              "class": result.names[int(cls)], "conf": round(conf, 3)})
    return boxes


def pick(boxes):
    """확신도가 높은 오탐부터, 같은 장소에 몰리지 않게 고른다."""
    picked, used = [], {}
    for box in sorted(boxes, key=lambda b: -b["conf"]):
        cell = tuple(int(v / PLACE_DEGREE) for v in box["place"])
        if used.get(cell, 0) < PER_PLACE:
            used[cell] = used.get(cell, 0) + 1
            picked.append(box)
        if len(picked) == TARGET:
            break
    return picked


def save_crop(box, path):
    image = cv2.imread(str(view_file(box["image_id"], box["view"])))
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box["xyxy"]
    side_x, side_y = max((x2 - x1) * 1.15, MIN_CROP), max((y2 - y1) * 1.15, MIN_CROP)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    left, right = max(int(cx - side_x / 2), 0), min(int(cx + side_x / 2), width)
    top, bottom = max(int(cy - side_y / 2), 0), min(int(cy + side_y / 2), height)
    cv2.imwrite(str(path), image[top:bottom, left:right], [cv2.IMWRITE_JPEG_QUALITY, 92])


def prepare():
    from training_guard import stop_if_training

    stop_if_training()
    if DECISIONS.exists():
        raise SystemExit(f"이미 확인한 결과가 있습니다: {DECISIONS}. 확인 내용을 지키기 위해 후보를 다시 만들지 않습니다.")
    picked = pick(find_boxes(usable_views()))
    shutil.rmtree(HARD, ignore_errors=True)
    CROPS.mkdir(parents=True)
    rng = random.Random(42)
    holdout_cells = {}
    rows = []
    for number, box in enumerate(picked):
        name = f"{number:03d}_{box['image_id']}_{box['view']}.jpg"
        save_crop(box, CROPS / name)
        cell = tuple(int(v / 0.002) for v in box["place"])    # 평가용 사진이 학습 사진 옆에 있지 않게 칸 단위로 나눈다
        holdout = holdout_cells.setdefault(cell, rng.random() < HOLDOUT)
        rows.append({"file": name, "image_id": box["image_id"], "view": box["view"], "class": box["class"],
                     "conf": box["conf"], "lat": box["place"][0], "lon": box["place"][1],
                     "split": "holdout" if holdout else "train"})
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"확인할 후보 {len(rows)}개 (학습용 {sum(r['split'] == 'train' for r in rows)}, 평가용 {sum(r['split'] == 'holdout' for r in rows)})")


def load_decisions():
    return json.loads(DECISIONS.read_text(encoding="utf-8")) if DECISIONS.exists() else {}


class ReviewHandler(BaseHTTPRequestHandler):
    files = set()

    def reply(self, body, content_type="application/json; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.reply(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/items":
            items = [{"file": r["file"], "class": r["class"], "conf": float(r["conf"])} for r in read_csv(CANDIDATES)]
            self.reply(json.dumps({"items": items, "decisions": load_decisions()}, ensure_ascii=False).encode())
        elif self.path.startswith("/crops/") and self.path[7:] in self.files:
            self.reply((CROPS / self.path[7:]).read_bytes(), "image/jpeg")
        else:
            self.reply(b"{}", status=404)

    def do_POST(self):
        if self.path != "/save":
            self.reply(b"{}", status=404)
            return
        changes = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        decisions = load_decisions()
        decisions.update({f: d for f, d in changes.items() if f in self.files and d in ("negative", "obstacle")})
        temp = DECISIONS.with_suffix(".tmp")
        temp.write_text(json.dumps(decisions, ensure_ascii=False, indent=1), encoding="utf-8")
        temp.replace(DECISIONS)
        self.reply(json.dumps({"saved": len(decisions)}).encode())

    def log_message(self, *args):
        pass


def review():
    if not CANDIDATES.exists():
        raise SystemExit("후보가 없습니다. 먼저 python 09_hard_negatives.py prepare 를 실행하세요.")
    ReviewHandler.files = {r["file"] for r in read_csv(CANDIDATES)}
    print(f"브라우저에서 여세요: http://localhost:{PORT}  (끝나면 Ctrl + C)")
    ThreadingHTTPServer(("127.0.0.1", PORT), ReviewHandler).serve_forever()


def link_all(source, target):
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if not path.name.endswith(".cache"):
            os.symlink(path, target / path.name)


def build():
    rows = read_csv(CANDIDATES)
    decisions = load_decisions()
    negatives = [r for r in rows if r["split"] == "train" and decisions.get(r["file"]) == "negative"]
    waiting = sum(r["file"] not in decisions for r in rows)
    if len(negatives) < MIN_NEGATIVES:
        raise SystemExit(f"확인된 오탐이 {len(negatives)}개라 부족합니다 (최소 {MIN_NEGATIVES}개, 미확인 {waiting}개).")
    shutil.rmtree(V3_DATASET, ignore_errors=True)
    link_all(DATASET_DIR / "train" / "images", V3_DATASET / "train" / "images")
    link_all(DATASET_DIR / "train" / "labels", V3_DATASET / "train" / "labels")
    for row in negatives:
        name = f"busan_negative_{row['file']}"
        shutil.copy(CROPS / row["file"], V3_DATASET / "train" / "images" / name)
        (V3_DATASET / "train" / "labels" / f"{Path(name).stem}.txt").write_text("", encoding="utf-8")
    for split in ("valid", "test"):     # 평가 기준은 v2와 똑같이 둔다
        (V3_DATASET / split).mkdir()
        os.symlink(DATASET_DIR / split / "images", V3_DATASET / split / "images")
        os.symlink(DATASET_DIR / split / "labels", V3_DATASET / split / "labels")
    (V3_DATASET / "data.yaml").write_text(yaml.safe_dump({
        "path": str(V3_DATASET), "train": "train/images", "val": "valid/images", "test": "test/images",
        "names": dict(enumerate(CLASSES)),
    }, allow_unicode=True), encoding="utf-8")
    print(f"v3 학습 데이터 완성: 장애물 없음 사진 {len(negatives)}장 추가 (미확인 {waiting}개 제외)")


if __name__ == "__main__":
    commands = {"prepare": prepare, "review": review, "build": build}
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in commands:
        raise SystemExit("사용법: python 09_hard_negatives.py prepare | review | build")
    commands[command]()
