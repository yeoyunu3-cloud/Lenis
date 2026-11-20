"""4단계: 학습한 모델로 부산 사진에서 장애물을 찾아 위치와 함께 저장한다.

360도 사진은 일반 화면 4개로 나눠서 탐지한다 (panorama.py).
출력: data/processed/detections.csv (image_id, view, class, conf, lat, lon, source)
      data/processed/mapillary/views/  장애물을 찾은 화면 (사진 확인·라벨링용)
      → server/가 detections.csv에서 서비스 지역 안의 탐지만 읽어 경로 계산에 반영한다.
주의: 위치는 '사진을 찍은 위치'라서 실제 장애물과 몇 m 차이가 날 수 있다 (근사 위치).
"""
import csv
import shutil
from collections import Counter

import cv2
from ultralytics import YOLO

from config import CONF, DETECTIONS_CSV, DEVICE, MAPILLARY_DIR, RUN_NAME, RUNS_DIR
from panorama import VIEWS, frames, view_file
from training_guard import stop_if_training

BATCH = 16
COLUMNS = ["image_id", "view", "class", "conf", "lat", "lon", "source"]


def detect_batch(model, batch, places, rows):
    results = model.predict([image for _, _, image in batch], conf=CONF, device=DEVICE, verbose=False)
    for (image_id, view, image), result in zip(batch, results):
        if not len(result.boxes):
            continue
        cv2.imwrite(str(view_file(image_id, view)), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        for cls, conf in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist()):
            rows.append({
                "image_id": image_id, "view": view, "class": result.names[int(cls)], "conf": round(conf, 3),
                "lat": places[image_id]["lat"], "lon": places[image_id]["lon"],
                "source": "ai",     # 신뢰도 표시용: ai / survey(현장 조사) / report(제보)
            })


def detect(places):
    model = YOLO(str(RUNS_DIR / RUN_NAME / "weights" / "best.pt"))
    rows, batch = [], []
    checked = Counter()
    for number, image_id in enumerate(places, 1):
        views = frames(image_id)
        checked["사진"] += bool(views)
        checked["깨진 사진"] += not views
        checked["화면"] += len(views)
        for view, image in views:
            batch.append((image_id, view, image))
            if len(batch) == BATCH:
                detect_batch(model, batch, places, rows)
                batch = []
        print(f"{number}/{len(places)}장 분석", end="\r", flush=True)
    if batch:
        detect_batch(model, batch, places, rows)
    print()
    return rows, checked


if __name__ == "__main__":
    stop_if_training()
    with open(MAPILLARY_DIR / "images.csv", newline="", encoding="utf-8") as f:
        places = {row["image_id"]: row for row in csv.DictReader(f)}
    shutil.rmtree(VIEWS, ignore_errors=True)
    VIEWS.mkdir(parents=True)
    rows, checked = detect(places)
    DETECTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(DETECTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print("분석:", dict(checked))
    print("탐지 수:", dict(Counter(row["class"] for row in rows)))
