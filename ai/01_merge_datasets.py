"""1단계: data/raw/ 아래 여러 YOLO 데이터셋을 우리 클래스 기준으로 합치고 70/20/10으로 나눈다.

입력:  data/raw/<데이터셋>/data.yaml, */images, */labels
출력:  data/processed/busan_obstacles/ (train/valid/test + data.yaml)
"""
import random
import re
import shutil
from collections import Counter

import yaml

from config import CLASSES, DATASET_DIR, MAX_IMAGES_PER_DATASET, NAME_MAP, RAW_DIR

SPLIT_RATIO = {"train": 0.7, "valid": 0.2, "test": 0.1}


def load_names(yaml_path):
    names = yaml.safe_load(open(yaml_path, encoding="utf-8"))["names"]
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names, key=int)]
    # "1 curb ramp" → "curb ramp"
    return [re.sub(r"^\d+\s+", "", str(n).strip().lower()) for n in names]


def collect_pairs():
    """모든 데이터셋에서 (사진 경로, 변환된 라벨 줄들)을 모은다."""
    pairs = []
    for yaml_path in sorted(RAW_DIR.glob("*/data.yaml")):
        ds_dir = yaml_path.parent
        names = load_names(yaml_path)
        id_map = {i: CLASSES.index(NAME_MAP[n]) for i, n in enumerate(names) if n in NAME_MAP}
        print(f"[{ds_dir.name}] {names} → 사용: {[names[i] for i in id_map]}")

        imgs = sorted(ds_dir.glob("*/images/*"))
        cap = MAX_IMAGES_PER_DATASET.get(ds_dir.name)
        if cap and len(imgs) > cap:
            imgs = random.Random(0).sample(imgs, cap)
        for img in imgs:
            lbl = img.parent.parent / "labels" / (img.stem + ".txt")
            if not lbl.exists():
                continue
            lines = []
            for line in open(lbl):
                parts = line.split()
                if not parts or int(parts[0]) not in id_map:
                    continue
                c = id_map[int(parts[0])]
                if len(parts) == 5:  # 박스 라벨
                    lines.append(" ".join([str(c)] + parts[1:]))
                elif len(parts) >= 7 and len(parts) % 2 == 1:  # 다각형 라벨 → 박스로 바꿈
                    xs = [float(v) for v in parts[1::2]]
                    ys = [float(v) for v in parts[2::2]]
                    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                    lines.append(f"{c} {(x0+x1)/2:.6f} {(y0+y1)/2:.6f} {x1-x0:.6f} {y1-y0:.6f}")
            if lines:
                pairs.append((img, lines))
    return pairs


def source_photo(img):
    """Roboflow는 한 사진을 여러 장으로 늘려 '원본이름.rf.해시.jpg'로 저장한다. 원본 사진 단위로 묶는다."""
    return (img.parts[-4], img.name.split(".rf.")[0])


def split(pairs):
    """같은 원본 사진에서 나온 사진은 같은 묶음(train/valid/test)에만 들어가게 나눈다.
    섞이면 시험 문제를 미리 본 셈이라 점수가 실제보다 높게 나온다."""
    groups = {}
    for pair in pairs:
        groups.setdefault(source_photo(pair[0]), []).append(pair)
    keys = sorted(groups)
    random.Random(42).shuffle(keys)
    n = len(keys)
    n_train, n_valid = int(n * SPLIT_RATIO["train"]), int(n * SPLIT_RATIO["valid"])
    parts = {"train": keys[:n_train], "valid": keys[n_train:n_train + n_valid], "test": keys[n_train + n_valid:]}
    print("원본 사진 수:", {k: len(v) for k, v in parts.items()})
    return {k: [pair for key in v for pair in groups[key]] for k, v in parts.items()}


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
