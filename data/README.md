# data

| 폴더 | 내용 | Git에 올리기 |
|---|---|---|
| `raw/` | Roboflow·AI Hub 원본 데이터셋, 공공데이터 원본 | ❌ (용량 큼) |
| `processed/` | `detections.csv`, `reports.json`, 학습 결과, Mapillary 사진 | ❌ |
| `sample/` | 테스트용 **가짜** 데이터 (위치·내용 모두 실제 아님) | ✅ |

## 파일 형식 약속

**detections.csv** — 장애물 위치 (AI 탐지 + 현장 조사 + 제보를 같은 형식으로)
```
image_id,class,conf,lat,lon,source
```
- `class`: stairs / curb / ramp / elevator
- `source`: ai / survey(현장 조사) / report(이용자 제보) → 화면의 신뢰도 표시에 사용. `ai`는 길을 막지 않고 감점만 합니다.
- 현장 조사 결과는 `conf`를 1.0으로 넣으면 됩니다.

**entrances.json** — 출입구
```json
{"name": "", "type": "subway_elevator | ramp_entrance | building_elevator",
 "lat": 0, "lon": 0, "note": "", "source": "", "checked_at": "YYYY-MM-DD"}
```
