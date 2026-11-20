"""2단계: YOLO 학습 후 test 데이터로 점수를 출력한다.

출력: data/processed/runs/<RUN_NAME>/weights/best.pt
점수는 docs/실험_기록.md에 옮겨 적는다.
"""
from ultralytics import YOLO

from config import BATCH, CLASSES, DATASET_DIR, DEVICE, EPOCHS, IMGSZ, MODEL, PATIENCE, RUN_NAME, RUNS_DIR

DATA_YAML = str(DATASET_DIR / "data.yaml")


def train():
    model = YOLO(MODEL)
    model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        patience=PATIENCE,
        device=DEVICE,
        project=str(RUNS_DIR),
        name=RUN_NAME,
        exist_ok=True,
    )


def evaluate():
    best = YOLO(str(RUNS_DIR / RUN_NAME / "weights" / "best.pt"))
    m = best.val(data=DATA_YAML, split="test", device=DEVICE)
    print(f"\n[{RUN_NAME}] mAP50 {m.box.map50:.3f} | P {m.box.mp:.3f} | R {m.box.mr:.3f}")
    for idx, ap in zip(m.box.ap_class_index, m.box.ap50):
        print(f"  {CLASSES[int(idx)]:10s} {ap:.3f}")


if __name__ == "__main__":
    train()
    evaluate()
