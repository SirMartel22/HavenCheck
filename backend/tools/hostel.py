from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Hostel


def search_hostels(
    db: Session,
    name: str | None = None,
    location: str | None = None,
) -> dict:
    """Find hostels by case-insensitive full or partial name and location."""
    name_query = (name or "").strip()
    location_query = (location or "").strip()
    if not name_query and not location_query:
        return {
            "name": None,
            "location": None,
            "count": 0,
            "matches": [],
            "error": "name or location is required",
        }

    stmt = select(Hostel)
    if name_query:
        stmt = stmt.where(func.lower(Hostel.name).contains(name_query.lower()))
    if location_query:
        stmt = stmt.where(
            func.lower(Hostel.location).contains(location_query.lower())
        )
    stmt = stmt.order_by(
        (
            func.lower(Hostel.name) == name_query.lower()
            if name_query
            else func.lower(Hostel.location) == location_query.lower()
        ).desc(),
        Hostel.price_naira,
        Hostel.name,
    ).limit(20)
    matches = [
        {
            "id": hostel.id,
            "name": hostel.name,
            "location": hostel.location,
            "priceNaira": hostel.price_naira,
            "amenities": hostel.amenities or [],
            "description": hostel.description,
            "photoUrl": hostel.photo_url,
            "lat": hostel.lat,
            "lng": hostel.lng,
            "isSchoolManaged": hostel.is_school_managed,
            "scamRiskLevel": hostel.scam_risk_level,
        }
        for hostel in db.scalars(stmt)
    ]
    return {
        "name": name_query or None,
        "location": location_query or None,
        "count": len(matches),
        "matches": matches,
        "error": None,
    }
