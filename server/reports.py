"""이용자 통과 기록·제보 저장. 처음에는 참고 정보로만 쓰고, 쌓이면 경로 계산에 반영한다."""
import json
from datetime import datetime
from pathlib import Path

REPORTS = Path(__file__).resolve().parent.parent / "data" / "processed" / "reports.json"


def load_reports():
    if not REPORTS.exists():
        return []
    return json.loads(REPORTS.read_text(encoding="utf-8"))


def add_report(report: dict):
    reports = load_reports()
    report["created_at"] = datetime.now().isoformat(timespec="seconds")
    reports.append(report)
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    REPORTS.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
