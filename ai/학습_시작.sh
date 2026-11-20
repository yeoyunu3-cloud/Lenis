#!/bin/bash
# 맥에서 v2 학습 전체 실행: 데이터 받기 → 합치기 → 학습 → test 점수
# 실행 중 맥이 잠들지 않게 caffeinate로 감쌈. 로그는 학습_로그.txt
cd "$(dirname "$0")"
caffeinate -i bash -c '
  .venv/bin/python 00_download_roboflow.py &&
  .venv/bin/python 01_merge_datasets.py &&
  .venv/bin/python 02_train.py
' 2>&1 | tee 학습_로그.txt
