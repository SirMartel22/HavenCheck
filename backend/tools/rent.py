from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AreaPriceAverage


def check_rent_fairness(
    db: Session, location: str, price_naira: float, amenities: list[str] | None = None
) -> dict:
    area = db.scalar(
        select(AreaPriceAverage).where(func.lower(AreaPriceAverage.location) == location.strip().lower())
    )
    if area is None:
        return {
            "verdict": "unknown",
            "location": location,
            "price_naira": round(price_naira),
            "area_average_naira": None,
            "area_range_naira": {"low": None, "high": None},
            "difference_from_average_pct": None,
            "amenities_considered": amenities or [],
            "message": "No area price data is available for this location.",
        }

    difference_pct = ((price_naira - area.avg_price_naira) / area.avg_price_naira) * 100
    if price_naira > area.price_range_high:
        verdict = "overpriced"
    elif price_naira < area.price_range_low:
        verdict = "underpriced"
    else:
        verdict = "fair"
    return {
        "verdict": verdict,
        "location": area.location,
        "price_naira": round(price_naira),
        "area_average_naira": area.avg_price_naira,
        "area_range_naira": {"low": area.price_range_low, "high": area.price_range_high},
        "difference_from_average_pct": round(difference_pct, 1),
        "amenities_considered": amenities or [],
        "message": None,
    }
