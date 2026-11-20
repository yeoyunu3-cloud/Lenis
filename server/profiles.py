"""사용자 유형별 기준 (개발 가이드북 6장 표).

obstacle_penalty: OSM·현장 조사·제보로 확인된 장애물
ai_penalty: AI가 추정한 장애물. 틀렸을 수 있으므로 길을 막지 않고 비용만 늘린다.
값의 뜻:
  None  → 그 구간을 아예 지나가지 않음 (경로에서 제외)
  숫자  → 그 구간의 비용을 길이 × 숫자로 늘림 (클수록 더 피함)
grade_penalty: 경사 구간의 비용 배수 (soft: 5.6% 초과, hard: 8.3% 초과). None이면 지나가지 않음.
downhill_factor: 내리막 부담 비율. 1이면 오르막과 같고, 0이면 내리막 경사 비용을 더하지 않음.
TODO: 값은 임시. 현장 조사·인터뷰 후 조정. 경사 기준은 법령 원문을 확인한 뒤 확정.
"""

GRADE_SOFT = 5.6    # 접근로 기울기 1/18
GRADE_HARD = 8.3    # 접근로 기울기 1/12

PROFILES = {
    "stroller": {
        "label": "유아차",
        "speed_mps": 1.0,
        "obstacle_penalty": {"stairs": None, "curb": 3.0},
        "ai_penalty": {"stairs": 10.0, "curb": 2.0},
        "grade_penalty": {"soft": 2.0, "hard": 4.0},
        "downhill_factor": 0.8,
    },
    "tourist": {
        "label": "여행용 캐리어",
        "speed_mps": 1.0,
        "obstacle_penalty": {"stairs": 10.0, "curb": 1.5},
        "ai_penalty": {"stairs": 3.0, "curb": 1.2},
        "grade_penalty": {"soft": 1.5, "hard": 3.0},
        "downhill_factor": 0.5,
    },
    "elderly": {
        "label": "어르신·무릎 불편",
        "speed_mps": 0.9,
        "obstacle_penalty": {"stairs": 20.0, "curb": 1.0},
        "ai_penalty": {"stairs": 3.0, "curb": 1.0},
        "grade_penalty": {"soft": 2.0, "hard": 5.0},
        "downhill_factor": 1.0,
    },
    "wheelchair": {
        "label": "휠체어",
        "speed_mps": 0.9,
        "obstacle_penalty": {"stairs": None, "curb": None},
        "ai_penalty": {"stairs": 10.0, "curb": 5.0},
        # TODO: 5m DEM을 쓰게 되면 hard를 None(불가)으로. 30m DEM은 오차가 커서 길을 막지 않는다.
        "grade_penalty": {"soft": 5.0, "hard": 10.0},
        "downhill_factor": 1.0,
    },
    "general": {
        "label": "일반",
        "speed_mps": 1.2,
        "obstacle_penalty": {"stairs": 1.0, "curb": 1.0},
        "ai_penalty": {"stairs": 1.0, "curb": 1.0},
        "grade_penalty": {"soft": 1.0, "hard": 1.0},
        "downhill_factor": 1.0,
    },
}

DEFAULT_PROFILE = "stroller"
# 개발서의 초기 개발 대상. 나머지 유형은 검증된 데이터를 확보한 뒤 연다.
ACTIVE_PROFILES = ("stroller", "tourist")
