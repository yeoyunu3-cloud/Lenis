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

# 우리 클래스 (번호 0, 1, 2) — elevator는 데이터가 없어서 v2부터 뺌
CLASSES = ["stairs", "curb", "ramp"]

# 데이터셋의 클래스 이름(소문자) → 우리 클래스. 여기 없는 클래스는 버린다.
NAME_MAP = {
    "stairs": "stairs", "stair": "stairs", "staircase": "stairs", "steps": "stairs",
    "caution_zone_stairs": "stairs",
    "curb": "curb", "kerb": "curb", "curbs": "curb",
    "ramp": "ramp", "ramps": "ramp", "wheelchair ramp": "ramp", "wheelchair_ramp": "ramp",
    "curbramp": "ramp", "curb ramp": "ramp", "curb_ramp": "ramp", "curb-ramp": "ramp",
}

# Roboflow에서 받을 데이터셋. 클래스마다 위에서부터 시도해서 받을 수 있는 것만 최대 2개.
CANDIDATES = {
    "stairs": [("obstaclesonroads", "stairs-lusiz-hm7ja")],
    "curb": [("failsafesystem", "road-curbs"), ("curbstone", "curb-zjoev"), ("curbs", "curb-jk8ge"),
             ("vspace", "curb-xtrmz"), ("ebyeol", "curb-xtrmz-v1orm")],
    "ramp": [("vdk", "wheelchair-ijcoz"), ("smithfield", "cache-valley-5jllb"),
             ("experiments-ypxgq", "intersections-thyhz"), ("mitre-lfjxx", "stairs-aj4wy")],
}
MAX_PER_CLASS = 2
# 사진이 너무 많은 데이터셋은 줄인다 (학습 시간·클래스 균형)
# v4: AI Hub 계단 사진은 계단을 가까이 찍어 상자가 사진 전체인 경우가 많다. 너무 많으면 모델이 큰 상자만 배우므로 줄인다.
MAX_IMAGES_PER_DATASET = {"aihub_stairs": 4000}

# 학습
MODEL = "yolo11n.pt"
RUN_NAME = os.environ.get("RUN_NAME", "v2")   # 다른 모델로 실행: RUN_NAME=v3 python 04_detect.py
EPOCHS = 50
IMGSZ = 640
BATCH = 16
PATIENCE = 15
DEVICE = "mps"           # 맥 GPU. Colab이면 0, GPU 없으면 "cpu"

# 조사 지역 (서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도) — TODO: 생활권 정해지면 바꾸기
AREA = (129.030, 35.112, 129.045, 35.122)
MAX_IMAGES = 1500
CONF = 0.25
