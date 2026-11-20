"""11단계: v2와 v3를 같은 기준으로 비교한다.

비교 항목: 공개 데이터 test 점수, 학습에 쓰지 않은 부산 오탐 사진에서 다시 틀리는 비율,
          부산 시험 사진 점수 (라벨이 있을 때)
출력: data/processed/model_comparison.json
v3가 더 좋을 때만 config.py의 RUN_NAME을 "v3"로 바꾼다.
"""
import csv
import json

import yaml
from ultralytics import YOLO

from config import BASE, CLASSES, CONF, DATASET_DIR, DEVICE, RUNS_DIR
from training_guard import stop_if_training

HARD = BASE / "processed" / "hard_negatives"
LABELED = BASE / "raw" / "busan_labeled"
OUTPUT = BASE / "processed" / "model_comparison.json"
RUNS = ("v2", "v3")


def holdout_files():
    """사람이 '장애물 없음'으로 확인했고 학습에는 쓰지 않은 사진."""
    decisions = json.loads((HARD / "decisions.json").read_text(encoding="utf-8"))
    with open(HARD / "candidates.csv", newline="", encoding="utf-8") as f:
        return [HARD / "crops" / r["file"] for r in csv.DictReader(f)
                if r["split"] == "holdout" and decisions.get(r["file"]) == "negative"]


def busan_data():
    """라벨이 모두 있으면 부산 시험 데이터 설정을 만든다."""
    images = sorted((LABELED / "images").glob("*.jpg"))
    if not images or any(not (LABELED / "labels" / f"{p.stem}.txt").exists() for p in images):
        return None
    if not any((LABELED / "labels" / f"{p.stem}.txt").read_text(encoding="utf-8").strip() for p in images):
        return None
    data = LABELED / "busan_test.yaml"
    data.write_text(yaml.safe_dump({
        "path": str(LABELED), "train": "images", "val": "images", "test": "images",
        "names": dict(enumerate(CLASSES)),
    }, allow_unicode=True), encoding="utf-8")
    return data


def score(model, data, name):
    m = model.val(data=str(data), split="test", device=DEVICE, project=str(RUNS_DIR), name=name, exist_ok=True, verbose=False)
    return {"mAP50": round(float(m.box.map50), 3), "정밀도": round(float(m.box.mp), 3), "재현율": round(float(m.box.mr), 3)}


def false_alarm_rate(model, files):
    wrong = 0
    for start in range(0, len(files), 16):
        results = model.predict([str(p) for p in files[start:start + 16]], conf=CONF, device=DEVICE, verbose=False)
        wrong += sum(len(r.boxes) > 0 for r in results)
    return round(wrong / len(files) * 100, 1)


if __name__ == "__main__":
    stop_if_training()
    files = holdout_files()
    if not files:
        raise SystemExit("비교에 쓸 확인된 오탐 사진이 없습니다.")
    busan = busan_data()
    report = {"부산 오탐 평가 사진 수": len(files), "부산 시험 점수 포함": busan is not None}
    for run in RUNS:
        model = YOLO(str(RUNS_DIR / run / "weights" / "best.pt"))
        report[run] = {
            "공개 test": score(model, DATASET_DIR / "data.yaml", f"compare_{run}_public"),
            "부산 오탐 재발생률(%)": false_alarm_rate(model, files),
        }
        if busan:
            report[run]["부산 시험"] = score(model, busan, f"compare_{run}_busan")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
