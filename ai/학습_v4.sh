#!/bin/bash
# v4 학습: AI Hub 계단 사진을 더해서 다시 학습하고, 부산 사진 시험 점수를 v2와 비교한다.
# 준비: AI Hub에서 원천데이터 TS33.zip, VS5.zip을 받아 AIHUB_DIR 폴더 안에 넣기
# 실행: bash 학습_v4.sh   (맥이 잠들지 않게 caffeinate로 감쌈, 로그는 학습_로그_v4.txt)
# 경로 계산에 쓰는 detections.csv는 바꾸지 않는다. 점수를 보고 나서 따로 바꾼다.
cd "$(dirname "$0")"
export RUN_NAME=v4
caffeinate -i bash -c '
  .venv/bin/python 00_aihub_stairs.py &&
  .venv/bin/python 01_merge_datasets.py &&
  .venv/bin/python 02_train.py &&
  .venv/bin/python 08_busan_test.py
' 2>&1 | tee 학습_로그_v4.txt
