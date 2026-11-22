"""이용자 통과 기록·제보 저장과 검토.

흐름: 제보 → report_triage가 정리(status "pending") → 관리자가 web/admin.html에서 승인/거절
→ 승인된 계단·턱·통행 불가 제보만 경로 계산에 확인된 장애물로 들어간다.
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from report_triage import ROUTE_CLASS, TYPE_LABEL, triage

REPORTS = Path(__file__).resolve().parent.parent / "data" / "processed" / "reports.json"
STATUSES = ("pending", "approved", "rejected")
_lock = threading.Lock()


def _save(reports):
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    REPORTS.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


def load_reports():
    """예전 형식(id·status 없음) 제보는 읽을 때 채워 넣는다."""
    if not REPORTS.exists():
        return []
    reports = json.loads(REPORTS.read_text(encoding="utf-8"))
    changed = False
    for r in reports:
        if "id" not in r:
            r["id"], changed = uuid.uuid4().hex[:8], True
        r.setdefault("status", "pending")
        if "triage" not in r:
            r["triage"], changed = triage(r), True
    if changed:
        _save(reports)
    return reports


def add_report(report: dict):
    report["id"] = uuid.uuid4().hex[:8]
    report["created_at"] = datetime.now().isoformat(timespec="seconds")
    report["status"] = "pending"
    report["triage"] = triage(report)          # 저장 전에 정리 (Claude가 안 되면 규칙)
    with _lock:
        reports = load_reports()
        reports.append(report)
        _save(reports)
    return {"id": report["id"], "status": "pending"}   # 정리 결과는 관리자만 본다


def review(report_id: str, status: str, type_: str | None = None):
    """승인/거절. type_을 주면 관리자가 종류를 고친다. 바뀐 제보를 돌려준다."""
    if status not in STATUSES:
        raise ValueError(f"알 수 없는 상태: {status}")
    if type_ is not None and type_ not in TYPE_LABEL:
        raise ValueError(f"알 수 없는 종류: {type_}")
    with _lock:
        reports = load_reports()
        for r in reports:
            if r["id"] == report_id:
                r["status"] = status
                r["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                if type_:
                    r["triage"]["type"] = type_
                _save(reports)
                return r
    raise KeyError(report_id)


def approved_obstacles():
    """경로 계산에 넣을 승인된 제보 (routing의 장애물 형식)."""
    return [
        {"class": ROUTE_CLASS[r["triage"]["type"]], "conf": 1.0, "lat": r["lat"], "lon": r["lon"], "source": "report"}
        for r in load_reports()
        if r["status"] == "approved" and r["triage"]["type"] in ROUTE_CLASS
    ]
