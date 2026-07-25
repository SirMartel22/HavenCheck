import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Hostel(Base):
    __tablename__ = "hostels"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False, index=True)
    price_naira: Mapped[int] = mapped_column(Integer, nullable=False)
    amenities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_school_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scam_risk_level: Mapped[str | None] = mapped_column(String, nullable=True)

    utility_reports: Mapped[list["UtilityReport"]] = relationship(
        back_populates="hostel", cascade="all, delete-orphan"
    )


class AreaPriceAverage(Base):
    __tablename__ = "area_price_averages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    avg_price_naira: Mapped[int] = mapped_column(Integer, nullable=False)
    price_range_low: Mapped[int] = mapped_column(Integer, nullable=False)
    price_range_high: Mapped[int] = mapped_column(Integer, nullable=False)


class UtilityReport(Base):
    __tablename__ = "utility_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hostel_id: Mapped[str] = mapped_column(ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    water_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    electricity_issue: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    hostel: Mapped[Hostel] = relationship(back_populates="utility_reports")


class ScamTranscript(Base):
    __tablename__ = "scam_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hostel_id: Mapped[str | None] = mapped_column(ForeignKey("hostels.id", ondelete="SET NULL"), nullable=True)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_scam: Mapped[bool] = mapped_column(Boolean, nullable=False)
