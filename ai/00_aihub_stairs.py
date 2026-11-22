"""AI Hub '보행 안전을 위한 도로 시설물 데이터'의 보행자 계단 사진을 YOLO 학습 형식으로 바꾼다.

AI Hub에서 받을 파일 (로그인·승인 후 직접 받기):
  라벨: 1.Training/라벨링데이터/TL33.zip, 2.Validation/라벨링데이터/VL5.zip  (이미 받음)
  사진: 1.Training/원천데이터/TS33.zip,  2.Validation/원천데이터/VS5.zip
        (TL32/TS32에도 계단 사진 2만 장이 있지만 용량이 커서 필요할 때만)

실행: AIHUB_DIR="<받은 폴더>" python 00_aihub_stairs.py
출력: data/raw/aihub_stairs/ (train/images, train/labels, data.yaml) → 01_merge_datasets.py가 같이 합친다.

- 사진은 zip 안에서 바로 읽는다 (압축을 풀지 않아도 된다). 이미 풀어 둔 폴더의 jpg도 찾는다.
- 학습은 640px로 하므로 사진을 긴 변 1280px로 줄여 저장한다 (원본은 4032px라 용량이 크다).
- 라벨 bbox는 [x, y, 너비, 높이] (왼쪽 위 기준, 픽셀).
"""
import io
import json
import os
import zipfile
from pathlib import Path

from PIL import Image

from config import RAW_DIR

AIHUB_DIR = Path(os.environ.get("AIHUB_DIR", Path.home() / "Downloads" / "119.보행 안전을 위한 도로 시설물 데이터"))
OUT = RAW_DIR / "aihub_stairs"
STAIRS_FOLDER = "38."          # AI Hub 분류 폴더 "38. 보행자_계단"
MAX_SIDE = 1280


def zip_name(info):
    """AI Hub zip은 파일 이름이 CP949인데 UTF-8 표시가 없다. 둘 다 처리한다."""
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def open_zips(folder_word):
    zips = []
    for path in sorted(AIHUB_DIR.rglob("*.zip")):
        if folder_word in str(path):
            try:
                zips.append(zipfile.ZipFile(path))
            except zipfile.BadZipFile:
                print(f"건너뜀 (다운로드가 덜 끝난 듯): {path.name}")
    return zips


def load_labels():
    """사진 파일 이름 → YOLO 라벨 줄들."""
    labels = {}
    for z in open_zips("라벨링데이터"):
        for info in z.infolist():
            name = zip_name(info)
            if info.is_dir() or not name.startswith(STAIRS_FOLDER) or not name.endswith(".json"):
                continue
            d = json.loads(z.read(info))
            W, H = d["info"]["width"], d["info"]["height"]
            lines = []
            for a in d["annotations"]:
                if a["annotation_type"] != "bbox":
                    continue
                x, y, w, h = a["annotation_info"][0]
                x, y = max(x, 0), max(y, 0)
                w, h = min(w, W - x), min(h, H - y)
                if w > 0 and h > 0:
                    lines.append(f"0 {(x + w / 2) / W:.6f} {(y + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}")
            if lines:
                labels[d["info"]["filename"]] = (lines, "valid" if "Validation" in z.filename else "train")
    return labels


def find_images(wanted):
    """원천데이터 zip과 풀어 둔 폴더에서 라벨이 있는 사진을 찾는다. 이름 → 사진 bytes를 읽는 함수."""
    found = {}
    for z in open_zips("원천데이터"):
        for info in z.infolist():
            base = zip_name(info).rsplit("/", 1)[-1]
            if base in wanted and base not in found:
                found[base] = lambda z=z, info=info: z.read(info)
    for path in AIHUB_DIR.rglob("*.jpg"):
        if path.name in wanted and path.name not in found:
            found[path.name] = path.read_bytes
    return found


def save(name, read, lines, split):
    img = Image.open(io.BytesIO(read())).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))      # 비율 유지 (YOLO 라벨은 비율 좌표라 그대로 맞다)
    (OUT / split / "images").mkdir(parents=True, exist_ok=True)
    (OUT / split / "labels").mkdir(parents=True, exist_ok=True)
    img.save(OUT / split / "images" / name, quality=90)
    (OUT / split / "labels" / (Path(name).stem + ".txt")).write_text("\n".join(lines) + "\n")


def main():
    labels = load_labels()
    print(f"계단 라벨: {len(labels)}장")
    images = find_images(set(labels))
    print(f"찾은 사진: {len(images)}장")
    if not images:
        print("사진이 없습니다. AI Hub에서 원천데이터 TS33.zip, VS5.zip을 받아 AIHUB_DIR 안에 넣어 주세요.")
        return
    done = 0
    for name, read in images.items():
        if (OUT / labels[name][1] / "images" / name).exists():
            done += 1
            continue
        try:
            save(name, read, *labels[name])
            done += 1
        except (OSError, zipfile.BadZipFile) as e:
            print(f"사진을 못 읽음 {name}: {e}")
        if done % 500 == 0:
            print(f"  {done}/{len(images)}")
    (OUT / "data.yaml").write_text("names: ['stairs']\n", encoding="utf-8")
    print(f"완료: {done}장 → {OUT}")


if __name__ == "__main__":
    main()
