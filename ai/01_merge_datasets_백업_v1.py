"""1단계: data/raw/ 아래 여러 YOLO 데이터셋을 우리 클래스 기준으로 합치고 70/20/10으로 나눈다.

입력:  data/raw/<데이터셋>/data.yaml, */images, */labels
출력:  data/processed/busan_obstacles/ (train/valid/test + data.yaml)
"""
import random
import shutil
from collections import Counter

import yaml

from config import CLASSES, DATASET_DIR, NAME_MAP, RAW_DIR

SPLIT_RATIO = {"train": 0.7, "valid": 0.2, "test": 0.1}


def load_names(yaml_path):
    names = yaml.safe_load(open(yaml_path, encoding="utf-8"))["names"]
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names, key=int)]
    return [str(n).strip().lower() for n in names]


def collect_pairs():
    """모든 데이터셋에서 (사진 경로, 변환된 라벨 줄들)을 모은다."""
    pairs = []
    for yaml_path in sorted(RAW_DIR.glob("*/data.yaml")):
        ds_dir = yaml_path.parent
        names = load_names(yaml_path)
        id_map = {i: CLASSES.index(NAME_MAP[n]) for i, n in enumerate(names) if n in NAME_MAP}
        print(f"[{ds_dir.name}] {names} → 사용: {[names[i] for i in id_map]}")

        for img in ds_dir.glob("*/images/*"):
            lbl = img.parent.parent / "labels" / (img.stem + ".txt")
            if not lbl.exists():
                continue
            lines = []
            for line in open(lbl):
                parts = line.split()
                if len(parts) != 5:  # 폴리곤 라벨은 건너뜀
                    continue
                c = int(parts[0])
                if c in id_map:
                    lines.append(" ".join([str(id_map[c])] + parts[1:]))
            if lines:
                pairs.append((img, lines))
    return pairs


def split(pairs):
    random.seed(42)
    random.shuffle(pairs)
    n = len(pairs)
    n_train, n_valid = int(n * SPLIT_RATIO["train"]), int(n * SPLIT_RATIO["valid"])
    return {
        "train": pairs[:n_train],
        "valid": pairs[n_train:n_train + n_valid],
        "test": pairs[n_train + n_valid:],
    }


def write(splits):
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    box_count = Counter()
    for name, items in splits.items():
        (DATASET_DIR / name / "images").mkdir(parents=True)
        (DATASET_DIR / name / "labels").mkdir(parents=True)
        for k, (img, lines) in enumerate(items):
            new = f"{name}_{k:05d}"
            shutil.copy(img, DATASET_DIR / name / "images" / f"{new}{img.suffix}")
            (DATASET_DIR / name / "labels" / f"{new}.txt").write_text("\n".join(lines) + "\n")
            for l in lines:
                box_count[CLASSES[int(l.split()[0])]] += 1

    with open(DATASET_DIR / "data.yaml", "w") as f:
        yaml.safe_dump({
            "path": str(DATASET_DIR),
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "names": dict(enumerate(CLASSES)),
        }, f, sort_keys=False)
    return box_count


if __name__ == "__main__":
    pairs = collect_pairs()
    if not pairs:
        raise SystemExit(f"사진을 찾지 못했습니다. {RAW_DIR}에 데이터셋을 넣었는지 확인하세요.")
    splits = split(pairs)
    box_count = write(splits)
    print("사진 수:", {k: len(v) for k, v in splits.items()})
    print("클래스별 박스 수:", dict(box_count))
    missing = [c for c in CLASSES if box_count[c] < 200]
    if missing:
        print("⚠️ 박스가 200개 미만인 클래스:", missing)
