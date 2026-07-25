from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models import Hostel, UtilityReport


def check_utility_reliability(db: Session, hostel_id: str) -> dict:
    hostel = db.get(Hostel, hostel_id)
    if hostel is None:
        return {"hostel_id": hostel_id, "hostel_name": None, "report_count": 0, "water_reliability_pct": None, "electricity_issue_count": 0, "recent_comments": [], "error": "Hostel not found"}
    reports = list(
        db.scalars(
            select(UtilityReport)
            .where(UtilityReport.hostel_id == hostel_id)
            .order_by(desc(UtilityReport.reported_at))
        )
    )
    if not reports:
        return {
            "hostel_id": hostel_id,
            "hostel_name": hostel.name,
            "report_count": 0,
            "water_reliability_pct": None,
            "electricity_issue_count": 0,
            "recent_comments": [],
            "error": None,
        }
    return {
        "hostel_id": hostel_id,
        "hostel_name": hostel.name,
        "report_count": len(reports),
        "water_reliability_pct": round(
            sum(report.water_available for report in reports) / len(reports) * 100, 1
        ),
        "electricity_issue_count": sum(report.electricity_issue for report in reports),
        "recent_comments": [report.comment for report in reports[:5]],
        "error": None,
    }
