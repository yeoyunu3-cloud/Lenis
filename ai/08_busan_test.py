"""8단계: 부산 사진 60장으로 모델 점수를 잰다.

python 08_busan_test.py prepare   라벨링할 사진 60장을 data/raw/busan_labeled/images/ 에 고른다
python 08_busan_test.py eval      라벨을 data/raw/busan_labeled/labels/ 에 넣은 뒤 점수를 잰다

라벨 형식: YOLO txt, 클래스 번호 0 stairs, 1 curb, 2 ramp. 장애물이 없는 사진은 빈 txt 파일.
이 사진들은 시험 전용이다. 학습 데이터에 넣으면 점수가 부풀려진다.
"""
import csv
import json
import random
import sys

import cv2
import yaml

from config import BASE, CLASSES, DETECTIONS_CSV, DEVICE, MAPILLARY_DIR, RUN_NAME, RUNS_DIR
from panorama import YAWS, frame, image_path, is_panorama

LABELED = BASE / "raw" / "busan_labeled"
IMAGES = LABELED / "images"
LABELS = LABELED / "labels"
SCORE = BASE / "processed" / f"busan_test_score_{RUN_NAME}.json"
WITH_OBSTACLE = 40      # AI가 장애물을 찾은 사진
WITHOUT_OBSTACLE = 20   # AI가 아무것도 못 찾은 사진 (놓친 장애물 확인용)
SPREAD_DEGREE = 0.002   # 약 200m 칸마다 고르게 뽑아 비슷한 사진이 몰리지 않게 한다


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def spread_pick(rows, count, rng):
    """칸을 돌아가며 하나씩 뽑는다."""
    cells = {}
    for row in rng.sample(rows, len(rows)):
        key = (int(float(row["lat"]) / SPREAD_DEGREE), int(float(row["lon"]) / SPREAD_DEGREE))
        cells.setdefault(key, []).append(row)
    picked, queues = [], list(cells.values())
    while len(picked) < count and queues:
        for queue in list(queues):
            if len(picked) == count:
                break
            picked.append(queue.pop())
            if not queue:
                queues.remove(queue)
    return picked


def prepare():
    if IMAGES.exists() and any(IMAGES.iterdir()):
        raise SystemExit(f"이미 고른 사진이 있습니다: {IMAGES}. 라벨이 어긋나지 않게 그대로 씁니다.")
    photos = {r["image_id"]: r for r in read_csv(MAPILLARY_DIR / "images.csv") if image_path(r["image_id"]).exists()}
    rng = random.Random(42)
    detected = {}       # 사진마다 장애물을 찾은 화면 하나만 쓴다
    rows = read_csv(DETECTIONS_CSV)
    for row in rng.sample(rows, len(rows)):
        if row["image_id"] in photos:
            detected.setdefault(row["image_id"], {**photos[row["image_id"]], "view": row["view"]})
    others = [photo for image_id, photo in photos.items() if image_id not in detected]
    picked = spread_pick(list(detected.values()), WITH_OBSTACLE, rng)
    picked += spread_pick(others, WITHOUT_OBSTACLE, rng)
    IMAGES.mkdir(parents=True, exist_ok=True)
    LABELS.mkdir(parents=True, exist_ok=True)
    for photo in picked:
        view = photo.get("view")
        if view is None:
            view = str(rng.choice(YAWS)) if is_panorama(cv2.imread(str(image_path(photo["image_id"])))) else "photo"
        cv2.imwrite(str(IMAGES / f"{photo['image_id']}_{view}.jpg"), frame(photo["image_id"], view), [cv2.IMWRITE_JPEG_QUALITY, 95])
    (LABELED / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    print(f"라벨링할 사진 {len(picked)}장: {IMAGES}")


def check_labels():
    images = sorted(p.stem for p in IMAGES.glob("*.jpg"))
    if not images:
        raise SystemExit("고른 사진이 없습니다. 먼저 python 08_busan_test.py prepare 를 실행하세요.")
    missing = [stem for stem in images if not (LABELS / f"{stem}.txt").exists()]
    if missing:
        raise SystemExit(f"라벨이 없는 사진이 {len(missing)}장 있습니다. 장애물이 없는 사진은 빈 txt 파일을 넣으세요.")
    boxes = 0
    for stem in images:
        for line in (LABELS / f"{stem}.txt").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5 or not parts[0].isdigit() or int(parts[0]) >= len(CLASSES):
                raise SystemExit(f"라벨 형식 오류: {stem}.txt")
            boxes += 1
    if not boxes:
        raise SystemExit("라벨 박스가 하나도 없습니다. 라벨링을 마친 뒤 다시 실행하세요.")
    return len(images), boxes


def evaluate():
    from ultralytics import YOLO

    from training_guard import stop_if_training

    stop_if_training()
    image_count, box_count = check_labels()
    data = LABELED / "busan_test.yaml"
    data.write_text(yaml.safe_dump({
        "path": str(LABELED), "train": "images", "val": "images", "test": "images",
        "names": dict(enumerate(CLASSES)),
    }, allow_unicode=True), encoding="utf-8")
    model = YOLO(str(RUNS_DIR / RUN_NAME / "weights" / "best.pt"))
    m = model.val(data=str(data), split="test", device=DEVICE, project=str(RUNS_DIR),
                  name=f"{RUN_NAME}_busan_test", exist_ok=True)
    score = {
        "모델": RUN_NAME, "사진 수": image_count, "라벨 박스 수": box_count,
        "mAP50": round(float(m.box.map50), 3), "정밀도": round(float(m.box.mp), 3), "재현율": round(float(m.box.mr), 3),
        "클래스별 AP50": {CLASSES[int(i)]: round(float(ap), 3) for i, ap in zip(m.box.ap_class_index, m.box.ap50)},
    }
    SCORE.write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(score, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "prepare":
        prepare()
    elif command == "eval":
        evaluate()
    else:
        raise SystemExit("사용법: python 08_busan_test.py prepare 또는 eval")
