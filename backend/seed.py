import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from db import Base, engine, session_scope
from models import AreaPriceAverage, Hostel, ScamTranscript, UtilityReport

DATA_DIR = Path(__file__).parent / "seed_data"

HOSTEL_COLUMN_MIGRATIONS = {
    "is_school_managed": "BOOLEAN NOT NULL DEFAULT FALSE",
    "scam_risk_level": "VARCHAR NULL",
}


def load(name: str) -> list[dict]:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError(f"{name} must contain a JSON array")
    return value


def migrate():
    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("hostels")
    }
    missing_columns = {
        name: definition
        for name, definition in HOSTEL_COLUMN_MIGRATIONS.items()
        if name not in existing_columns
    }
    if not missing_columns:
        return

    with engine.begin() as connection:
        for name, definition in missing_columns.items():
            connection.execute(
                text(f"ALTER TABLE hostels ADD COLUMN {name} {definition}")
            )
            print(f"Added hostels.{name}.")


def seed():
    Base.metadata.create_all(bind=engine)
    migrate()
    with session_scope() as db:
        db.query(UtilityReport).delete()
        db.query(ScamTranscript).delete()
        db.query(Hostel).delete()
        db.query(AreaPriceAverage).delete()
        for row in load("hostels.json"):
            db.add(Hostel(**row))
        for row in load("area_prices.json"):
            db.add(AreaPriceAverage(**row))
        db.flush()
        for row in load("utility_reports.json"):
            row = row.copy()
            if isinstance(row.get("reported_at"), str):
                row["reported_at"] = datetime.fromisoformat(row["reported_at"].replace("Z", "+00:00"))
            db.add(UtilityReport(**row))
        for row in load("scam_transcripts.json"):
            db.add(ScamTranscript(**row))
    print("Seed data loaded successfully.")


if __name__ == "__main__":
    seed()
