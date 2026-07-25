from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

load_dotenv()
from db import Base, engine, get_db  # noqa: E402
from gemma_client import GemmaClient, GemmaError  # noqa: E402
from models import Hostel, UtilityReport  # noqa: E402
from tools import (  # noqa: E402
    alert_community_security,
    check_rent_fairness,
    check_utility_reliability,
    flag_scam_risk,
    notify_hostel_authority,
)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Housing Scout API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class AgentRequest(BaseModel):
    message: str = Field(min_length=1)


class HostelCreate(BaseModel):
    name: str
    location: str
    price_naira: int = Field(alias="priceNaira", gt=0)
    amenities: list[str] = Field(default_factory=list)
    description: str
    photo_url: str | None = None
    lat: float | None = None
    lng: float | None = None
    model_config = ConfigDict(populate_by_name=True)


class ReportCreate(BaseModel):
    water_available: bool
    electricity_issue: bool
    comment: str


class Action(BaseModel):
    type: str
    url: str | None = None


class ApiResponse(BaseModel):
    message: str
    data: Any
    action: Action | None
    error: dict[str, Any] | None


def response(message: str, data: Any = None, action: dict | None = None, error: dict | None = None) -> dict:
    return {"message": message, "data": data if data is not None else {}, "action": action, "error": error}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=response(
            str(exc.detail),
            error={"code": f"HTTP_{exc.status_code}", "details": exc.detail},
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=response(
            "Request validation failed",
            error={"code": "VALIDATION_ERROR", "details": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=response(
            "An unexpected server error occurred",
            error={"code": "INTERNAL_SERVER_ERROR", "details": str(exc)},
        ),
    )


def report_dict(report: UtilityReport) -> dict:
    return {"id": report.id, "hostel_id": report.hostel_id, "water_available": report.water_available, "electricity_issue": report.electricity_issue, "comment": report.comment, "reported_at": report.reported_at.isoformat() if report.reported_at else None}


def hostel_dict(hostel: Hostel, include_reports: bool = False) -> dict:
    data = {"id": hostel.id, "name": hostel.name, "location": hostel.location, "priceNaira": hostel.price_naira, "amenities": hostel.amenities or [], "description": hostel.description, "photo_url": hostel.photo_url, "lat": hostel.lat, "lng": hostel.lng, "utility_reports": []}
    if include_reports:
        data["utility_reports"] = [report_dict(r) for r in hostel.utility_reports]
    return data


@app.get("/health", response_model=ApiResponse)
def health():
    return response("API is healthy", {"status": "ok"})


@app.post("/hostels", status_code=201, response_model=ApiResponse)
def create_hostel(payload: HostelCreate, db: Session = Depends(get_db)):
    hostel = Hostel(**payload.model_dump(by_alias=False))
    db.add(hostel)
    db.commit()
    db.refresh(hostel)
    return response("Hostel created successfully", {"hostel": hostel_dict(hostel)})


@app.get("/hostels", response_model=ApiResponse)
def list_hostels(location: str | None = None, max_price: int | None = Query(None, alias="maxPrice", gt=0), db: Session = Depends(get_db)):
    stmt = select(Hostel).order_by(Hostel.name)
    if location:
        stmt = stmt.where(func.lower(Hostel.location) == location.strip().lower())
    if max_price is not None:
        stmt = stmt.where(Hostel.price_naira <= max_price)
    return response("Hostels retrieved successfully", {"hostels": [hostel_dict(hostel) for hostel in db.scalars(stmt)]})


@app.get("/hostels/{hostel_id}", response_model=ApiResponse)
def get_hostel(hostel_id: str, db: Session = Depends(get_db)):
    hostel = db.scalar(select(Hostel).options(selectinload(Hostel.utility_reports)).where(Hostel.id == hostel_id))
    if hostel is None:
        raise HTTPException(404, "Hostel not found")
    return response("Hostel retrieved successfully", {"hostel": hostel_dict(hostel, include_reports=True)})


@app.post("/hostels/{hostel_id}/reports", status_code=201, response_model=ApiResponse)
def create_report(hostel_id: str, payload: ReportCreate, db: Session = Depends(get_db)):
    if db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")
    report = UtilityReport(hostel_id=hostel_id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return response("Utility report created successfully", {"report": report_dict(report)})


@app.post("/agent", response_model=ApiResponse)
def agent(payload: AgentRequest, db: Session = Depends(get_db)):
    client = GemmaClient()

    def dispatch(name: str, args: dict[str, Any]) -> dict:
        if name == "checkRentFairness":
            return check_rent_fairness(db, args["location"], args["priceNaira"], args.get("amenities"))
        if name == "checkUtilityReliability":
            return check_utility_reliability(db, args["hostelId"])
        if name == "flagScamRisk":
            return flag_scam_risk(args["listingText"], args.get("chatTranscript"), client.explain_scam_flags)
        if name == "notifyHostelAuthority":
            return notify_hostel_authority(args["hostelId"], args["issueType"], args["details"])
        if name == "alertCommunitySecurity":
            return alert_community_security(args["hostelId"], args["reason"], args.get("evidence", ""))
        return {"error": f"Unknown tool: {name}"}

    try:
        reply, calls = client.ask(payload.message, dispatch)
        return response("Agent request completed", {"reply": reply, "tool_used": ", ".join(call["name"] for call in calls) or None, "tool_calls": calls})
    except GemmaError as exc:
        return response("Housing Scout's AI service is temporarily unavailable. Please retry shortly.", {"reply": None, "tool_used": None, "tool_calls": []}, error={"code": "GEMMA_UNAVAILABLE", "details": str(exc)})
    except Exception as exc:
        return response("I could not complete that check, but the API is still running.", {"reply": None, "tool_used": None, "tool_calls": []}, error={"code": "AGENT_ERROR", "details": str(exc)})
