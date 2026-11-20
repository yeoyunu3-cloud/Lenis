"""AI 파이프라인 공통 설정. 경로와 클래스는 여기서만 바꾼다."""
import os
from pathlib import Path

# Colab에서는 BASE를 Drive 경로로 바꾼다. 예: /content/drive/MyDrive/busan_project
BASE = Path(os.environ.get("BUSAN_BASE", Path(__file__).resolve().parent.parent / "data"))

RAW_DIR = BASE / "raw"                      # Roboflow 등에서 받은 원본 데이터셋
DATASET_DIR = BASE / "processed" / "busan_obstacles"   # 합친 학습용 데이터셋
RUNS_DIR = BASE / "processed" / "runs"      # 학습 결과
MAPILLARY_DIR = BASE / "processed" / "mapillary"
DETECTIONS_CSV = BASE / "processed" / "detections.csv"

# 우리 클래스 (번호 0, 1, 2, 3)
CLASSES = ["stairs", "curb", "ramp", "elevator"]

# 데이터셋의 클래스 이름(소문자) → 우리 클래스. 여기 없는 클래스는 버린다.
NAME_MAP = {
    "stairs": "stairs", "stair": "stairs", "staircase": "stairs", "steps": "stairs",
    "curb": "curb", "kerb": "curb",
    "ramp": "ramp", "wheelchair ramp": "ramp",
    "elevator": "elevator", "elevator door": "elevator", "lift": "elevator",
}

# 학습
MODEL = "yolo11n.pt"
RUN_NAME = "v1"          # 학습할 때마다 v2, v3 … 로 바꾸기
EPOCHS = 100
IMGSZ = 640
BATCH = 16

# 조사 지역 (서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도) — TODO: 생활권 정해지면 바꾸기
AREA = (129.030, 35.112, 129.045, 35.122)
MAX_IMAGES = 1500
CONF = 0.4
