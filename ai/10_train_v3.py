"""10단계: v2 모델에 부산 오탐 사진을 더 학습시켜 v3를 만든다.

먼저 python 09_hard_negatives.py build 를 끝낸다.
실행: caffeinate -i .venv/bin/python 10_train_v3.py
출력: data/processed/runs/v3/weights/best.pt
"""
from ultralytics import YOLO

from config import BATCH, DEVICE, IMGSZ, RUNS_DIR
from training_guard import stop_if_training

V3_DATA = RUNS_DIR.parent / "busan_obstacles_v3" / "data.yaml"
EPOCHS = 20
PATIENCE = 8

if __name__ == "__main__":
    stop_if_training()
    if not V3_DATA.exists():
        raise SystemExit("v3 학습 데이터가 없습니다. 먼저 python 09_hard_negatives.py build 를 실행하세요.")
    model = YOLO(str(RUNS_DIR / "v2" / "weights" / "best.pt"))
    model.train(
        data=str(V3_DATA),
        epochs=EPOCHS,
        patience=PATIENCE,
        imgsz=IMGSZ,
        batch=BATCH,
        device=DEVICE,
        optimizer="AdamW",
        lr0=0.001,          # 이미 학습된 모델이라 조금씩만 고친다
        project=str(RUNS_DIR),
        name="v3",
        exist_ok=True,
    )
