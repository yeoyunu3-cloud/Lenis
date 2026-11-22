# 편한길로 – 가장 빠른 길이 아니라, 나에게 가장 편한 길

> 부산의 오르막·계단·턱을 고려해, 이동 유형에 맞는 편한 길과 들어갈 수 있는 출입구까지 안내하는 서비스

---

## 폴더 구조

```
부우산/
├── README.md            ← 지금 이 파일
├── docs/                ← 기획 문서 (노션 정리, YOLO 가이드 등)
├── ai/                  ← AI 파이프라인 (YOLO 학습 → 부산 사진 분석)
│   ├── config.py            경로·클래스 등 공통 설정
│   ├── 01_merge_datasets.py 공개 데이터셋 합치기 (클래스 통일, 70/20/10 분할)
│   ├── 02_train.py          YOLO 학습 + test 점수
│   ├── 03_fetch_mapillary.py 부산 도심 거리 사진 수집
│   ├── 04_detect.py         부산 사진에서 장애물 탐지 → detections.csv
│   ├── 05_match_osm.py      AI 탐지와 OSM 계단 비교 → 지도에 없는 후보
│   ├── 08_busan_test.py     부산 사진 60장으로 모델 점수 측정
│   ├── 09_hard_negatives.py 부산 오탐을 사람이 확인해 v3 학습 데이터 생성
│   ├── 10_train_v3.py       v2에 오탐 사진을 더 학습해 v3 생성
│   └── 11_compare_models.py v2와 v3 비교
├── server/              ← 경로 계산 서버 (FastAPI)
│   ├── main.py              API 주소 정의 + web/ 화면 제공
│   ├── profiles.py          사용자 유형별 기준 (어르신, 유아차, 휠체어 …)
│   ├── routing.py           보행 도로망 + 장애물 + 경사 → 맞춤 경로 계산
│   ├── slope.py             DEM으로 구간별·방향별 경사 계산
│   ├── compare_routes.py    네이버지도 경로와 비교 → docs/경로_비교_검증표.md
│   └── reports.py           이용자 제보 저장
├── web/                 ← 휴대폰용 화면 (홈 화면에 설치 가능)
│   ├── index.html           화면 구성 요소
│   ├── app.js               동작 (서버 호출, 지도 표시)
│   ├── style.css            화면 스타일
│   └── manifest.json        앱 설치 정보 (icons/ 아이콘)
└── data/
    ├── raw/                 원본 데이터 (데이터셋, 공공데이터, dem/ 고도 자료)
    ├── processed/           가공 결과 (detections.csv, reports.json …)
    └── sample/              테스트용 가짜 데이터
```

## 전체 흐름

```
[ai/]  공개 데이터셋 → YOLO 학습 → Mapillary 부산 사진 분석 → data/processed/detections.csv
                                                                     ↓
[server/]          OpenStreetMap 보행 도로망 + 장애물 위치 + 사용자 유형 → 맞춤 경로
                                                                     ↓
[web/]             사용자 유형 선택 → 출발·도착 → 경로 2~3개 비교 → 출입구 안내 → 제보
```

## 실행 방법

### 1) 화면 + 서버 (샘플 데이터로 바로 확인 가능)
```bash
cd server
pip install -r requirements.txt
uvicorn main:app --reload
```
브라우저에서 http://localhost:8000 접속.
서비스 지역은 부산광역시 전체입니다 (`server/area.py`). 처음 경로를 계산할 때 부산 전체 보행 도로망(OpenStreetMap)을 내려받고(약 2분), 경사·장애물을 계산해 `data/processed/walk_graph_busan_ready.pkl`에 저장합니다. 이후에는 저장한 파일을 씁니다. 걸어서 갈 거리(직선 10km 이내)만 안내합니다.

고도 자료는 `data/raw/dem/`에 넣습니다. 부산은 FABDEM 도엽 4장에 걸쳐 있어서, 받은 뒤 한 장으로 합칩니다. 없으면 경사를 "정보 없음"으로 표시합니다.
```bash
mkdir -p ../data/raw/dem
for t in N34E128 N34E129 N35E128 N35E129; do
  f=$(echo $t | tr 'NE' 'ne' | sed 's/\(n[0-9]*\)\(e[0-9]*\)/fabdem_\1_\2.tif/')
  curl -L -o ../data/raw/dem/$f https://huggingface.co/buckets/links-ads/fabdem/resolve/tiles/N30E120-N40E130_FABDEM_V1-2/${t}_FABDEM_V1-2.tif
done
python build_dem.py      # → data/raw/dem/fabdem_busan.tif
```

장소 검색 목록(`web/places.json`, 부산 전체 OSM 장소)은 `python build_places.py`로 다시 만듭니다.

화면만 가짜 데이터로 시험하려면 `USE_SAMPLE_DATA=1 uvicorn main:app --reload`로 실행합니다. 실제 경로 결과에는 샘플을 쓰지 않습니다.

휴대폰으로 접속하려면 `uvicorn main:app --host 0.0.0.0`로 실행한 뒤, 같은 Wi-Fi에서 `http://<노트북IP>:8000`을 엽니다.

### 2) AI 파이프라인 (Colab 권장, GPU 필요)
`ai/` 스크립트를 번호 순서대로 실행합니다. 자세한 설명은 `docs/`의 YOLO 가이드 참고.
```bash
cd ai
pip install -r requirements.txt
python 01_merge_datasets.py
python 02_train.py
python 03_fetch_mapillary.py
python 04_detect.py
python 05_match_osm.py
python 08_busan_test.py prepare   # 고른 사진 60장을 라벨링한 뒤
python 08_busan_test.py eval
```
경로 시연은 초량에서 OSM과 경사 자료로 계산하고, AI 성능은 부산 도심 거리 사진으로 검증합니다. 서버는 서비스 지역 안의 탐지만 경로에 반영합니다.

---

## 역할 분담 (빈칸 채우기)

| 영역 | 폴더 | 담당 |
|---|---|---|
| 현장 조사·데이터 | `data/` | |
| AI 모델 | `ai/` | |
| 경로·서버 | `server/` | |
| 화면 디자인 | `web/` | |
| 포스터·발표 | `docs/` | |

## 아직 정해지지 않은 것 (TODO)

- [x] 서비스 지역: 부산광역시 전체 (`server/area.py`)
- [ ] Mapillary에 해당 지역 사진이 충분한지 확인
- [ ] 더 정밀한 고도 자료로 교체 (지금은 FABDEM 30m: 짧은 급경사는 실제보다 낮게 나올 수 있음)
- [ ] 출입구 데이터 (엘리베이터 출구, 경사로 출입구) → `data/processed/entrances.json`에 같은 형식으로 수집
- [ ] (선택) 사진 없는 구간 예측 모델 (XGBoost)
