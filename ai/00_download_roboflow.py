"""0단계: Roboflow에서 config.CANDIDATES 데이터셋을 data/raw/ 로 받는다.

API 키는 코드에 넣지 않는다. 맥 키체인에서 읽거나 환경변수 ROBOFLOW_API_KEY를 쓴다.
키체인에 넣는 법 (터미널에서 한 번, 키를 붙여넣으라고 물어봄):
    security add-generic-password -a "$USER" -s ROBOFLOW_API_KEY -w
"""
import os
import subprocess

from roboflow import Roboflow

from config import CANDIDATES, MAX_PER_CLASS, RAW_DIR


def api_key():
    key = os.environ.get("ROBOFLOW_API_KEY")
    if key:
        return key
    r = subprocess.run(["security", "find-generic-password", "-s", "ROBOFLOW_API_KEY", "-w"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("Roboflow 키가 없음. 파일 위쪽 설명대로 키체인에 넣으세요.")
    return r.stdout.strip()


if __name__ == "__main__":
    rf = Roboflow(api_key=api_key())
    for cls, cands in CANDIDATES.items():
        got = 0
        for ws, proj in cands:
            if got >= MAX_PER_CLASS:
                break
            path = RAW_DIR / proj
            if (path / "data.yaml").exists():
                print(f"[{cls}] 이미 받음: {proj}")
                got += 1
                continue
            try:
                project = rf.workspace(ws).project(proj)
                versions = [int(str(v.version).split("/")[-1]) for v in project.versions()]
                if not versions:
                    print(f"[{cls}] 건너뜀: {proj} (받을 수 있는 버전 없음)")
                    continue
                project.version(max(versions)).download("yolov11", location=str(path))
                print(f"[{cls}] 받음: {proj} (버전 {max(versions)})")
                got += 1
            except Exception as e:
                print(f"[{cls}] 실패: {ws}/{proj} → {str(e)[:120]}")
        print(f"== {cls}: {got}개 데이터셋 ==")
