"""API 서버. 실행: uvicorn main:app --reload  →  http://localhost:8000

API 목록
  GET  /api/profiles               사용자 유형 목록
  POST /api/route                  맞춤 경로 계산
  GET  /api/obstacles              지도에 표시할 장애물
  GET  /api/entrances?lat=&lon=    목적지 근처 출입구
  POST /api/reports                통과 기록·제보 저장
  GET  /api/reports                제보 목록 (이 노트북에서만)
  POST /api/reports/{id}/review    제보 승인·거절 (이 노트북에서만) → 화면: /admin.html
"""
import json
import math
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import reports
from area import BUSAN_BOUNDS, in_busan
import routing
from profiles import ACTIVE_PROFILES, DEFAULT_PROFILE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# 가짜 샘플은 USE_SAMPLE_DATA=1 일 때만 쓴다
ENTRANCE_FILES = (
    [DATA / "sample" / "entrances.json"] if routing.USE_SAMPLE_DATA
    else [DATA / "processed" / "entrances.json", DATA / "processed" / "osm_ramp_entrances.json"]
)

app = FastAPI(title="Lenis API")


class RouteRequest(BaseModel):
    start: tuple[float, float]       # (위도, 경도)
    end: tuple[float, float]
    profile: str = DEFAULT_PROFILE


class Report(BaseModel):
    lat: float = Field(ge=BUSAN_BOUNDS[1], le=BUSAN_BOUNDS[3])     # 부산 범위 밖의 제보는 받지 않는다
    lon: float = Field(ge=BUSAN_BOUNDS[0], le=BUSAN_BOUNDS[2])
    profile: str = Field(max_length=20)
    kind: Literal["passed", "blocked", "obstacle", "construction"]
    obstacle: Optional[str] = Field(None, max_length=20)   # stairs / curb / narrow / etc
    needed_help: bool = False
    stroller_type: Optional[str] = Field(None, max_length=30)
    memo: str = Field("", max_length=300)


@app.get("/api/profiles")
def get_profiles():
    return [{"key": k, "label": PROFILES[k]["label"]} for k in ACTIVE_PROFILES]


@app.post("/api/route")
def post_route(req: RouteRequest):
    if req.profile not in ACTIVE_PROFILES:
        raise HTTPException(400, f"알 수 없는 사용자 유형: {req.profile}")
    if not (in_busan(*req.start) and in_busan(*req.end)):
        raise HTTPException(400, "부산 안의 출발지와 도착지만 안내해요")
    try:
        routes = routing.find_routes(req.start, req.end, req.profile)
    except routing.TooFar as e:
        raise HTTPException(400, str(e))
    return {"profile": req.profile, "routes": routes}


@app.get("/api/stats")
def get_stats():
    return routing.stats()


@app.get("/api/obstacles")
def get_obstacles():
    return routing.list_obstacles()


def distance_m(a, b):
    dy = (a[0] - b[0]) * 111_000
    dx = (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


@app.get("/api/entrances")
def get_entrances(lat: float, lon: float, radius: float = 300):
    items = [e for path in ENTRANCE_FILES if path.exists() for e in json.loads(path.read_text(encoding="utf-8"))]
    near = [dict(e, distance_m=round(distance_m((lat, lon), (e["lat"], e["lon"])))) for e in items]
    return sorted((e for e in near if e["distance_m"] <= radius), key=lambda e: e["distance_m"])


@app.post("/api/reports")
def post_report(report: Report):
    return reports.add_report(report.model_dump())


def local_only(request: Request):
    # 제보에는 위치와 메모가 들어 있으므로 외부 주소(cloudflared)로 들어온 요청은 막는다
    if "cf-connecting-ip" in request.headers or request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "제보 관리는 이 노트북에서만 할 수 있습니다")


@app.get("/api/reports")
def get_reports(request: Request):
    local_only(request)
    return sorted(reports.load_reports(), key=lambda r: (r["status"] != "pending", r["created_at"]), reverse=False)


class Review(BaseModel):
    status: Literal["pending", "approved", "rejected"]
    type: Optional[str] = None      # 관리자가 고친 종류


@app.post("/api/reports/{report_id}/review")
def post_review(report_id: str, review: Review, request: Request):
    local_only(request)
    try:
        report = reports.review(report_id, review.status, review.type)
    except KeyError:
        raise HTTPException(404, "없는 제보입니다")
    except ValueError as e:
        raise HTTPException(400, str(e))
    routing.refresh_reports()
    return report


# 화면(web/) 제공 — API 아래에 둬야 /api가 먼저 잡힌다
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
