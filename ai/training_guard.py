"""GPU를 쓰는 스크립트가 학습과 동시에 돌지 않게 막는다."""
import subprocess


def stop_if_training():
    # 실제 학습 프로세스만 찾는다. 학습 종료를 기다리는 셸의 명령어까지 잡으면 영원히 막힌다.
    if subprocess.run(["pgrep", "-f", "python 02_train.py"], capture_output=True).returncode == 0:
        raise SystemExit("학습이 아직 진행 중입니다. 학습이 끝난 뒤 다시 실행하세요.")
