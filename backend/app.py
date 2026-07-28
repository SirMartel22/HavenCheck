from datetime import datetime, timezone
from typing import Any
import base64
import os
import json

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException
import cloudinary
import cloudinary.uploader

load_dotenv()
from db import Base, engine, get_db  # noqa: E402
from gemma_client import GemmaClient, GemmaError  # noqa: E402
from models import ChatMessage, Hostel, UtilityReport  # noqa: E402
from tools import (  # noqa: E402
    alert_community_security,
    check_rent_fairness,
    check_utility_reliability,
    flag_scam_risk,
    notify_hostel_authority,
)
from voice import VoiceError, speak, transcribe_audio  # noqa: E402

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

app = FastAPI(title="Housing Scout API", version="1.0.0")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class AgentRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = Field(None, alias="sessionId")
    hostel_id: str | None = Field(None, alias="hostelId")
    model_config = ConfigDict(populate_by_name=True)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1)


class HostelCreate(BaseModel):
    name: str
    location: str
    price_naira: int = Field(alias="priceNaira", gt=0)
    amenities: list[str] = Field(default_factory=list)
    description: str
    lat: float | None = None
    lng: float | None = None
    photo_url: str | None = Field(None, alias="photoUrl")
    model_config = ConfigDict(populate_by_name=True)


class ReportCreate(BaseModel):
    water_available: bool
    electricity_issue: bool
    comment: str


class NotifyAuthorityRequest(BaseModel):
    issue_type: str = Field(alias="issueType")
    details: str
    model_config = ConfigDict(populate_by_name=True)


class AlertSecurityRequest(BaseModel):
    reason: str
    evidence: str = ""
    model_config = ConfigDict(populate_by_name=True)


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


def detect_image_type(content: bytes) -> str | None:
    if len(content) < 12:
        return None
    # Check magic bytes for PNG, JPEG, GIF, and WebP
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


async def upload_image_to_cloudinary(file: UploadFile) -> str | None:
    """Upload image to Cloudinary and return the URL"""
    if not file:
        return None
    
    # 5MB size limit
    MAX_SIZE = 5 * 1024 * 1024
    try:
        file_content = await file.read()
        if len(file_content) > MAX_SIZE:
            raise HTTPException(400, "File size exceeds the 5MB limit.")
        
        # Detect the true content type using magic bytes on the backend
        true_type = detect_image_type(file_content)
        allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if true_type not in allowed_types:
            raise HTTPException(400, "Only JPEG, PNG, GIF, and WebP images are allowed.")
        
        result = cloudinary.uploader.upload(
            file_content,
            folder="housing-scout",
            resource_type="image",
            public_id=f"hostel_{os.urandom(8).hex()}"
        )
        return result.get("secure_url")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Image upload failed: {exc}")


def report_dict(report: UtilityReport) -> dict:
    return {"id": report.id, "hostel_id": report.hostel_id, "water_available": report.water_available, "electricity_issue": report.electricity_issue, "comment": report.comment, "reported_at": report.reported_at.isoformat() if report.reported_at else None}


def hostel_dict(hostel: Hostel, include_reports: bool = False) -> dict:
    data = {"id": hostel.id, "name": hostel.name, "location": hostel.location, "priceNaira": hostel.price_naira, "amenities": hostel.amenities or [], "description": hostel.description, "photo_url": hostel.photo_url, "lat": hostel.lat, "lng": hostel.lng, "isSchoolManaged": hostel.is_school_managed, "scamRiskLevel": hostel.scam_risk_level, "utility_reports": []}
    if include_reports:
        data["utility_reports"] = [report_dict(r) for r in hostel.utility_reports]
    return data


def chat_message_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "sessionId": message.session_id,
        "hostelId": message.hostel_id,
        "role": message.role,
        "content": message.content,
        "createdAt": message.created_at.isoformat() if message.created_at else None,
    }

@app.get("/", response_model=ApiResponse)
def root():
    return response("Welcome to the Housing Scout API. Access /docs for API documentation.", {"status": "ok"})

@app.get("/health", response_model=ApiResponse)
def health():
    return response("API is healthy", {"status": "ok"})


@app.get("/chat/history", response_model=ApiResponse)
def chat_history(
    session_id: str | None = Query(None, alias="sessionId"),
    hostel_id: str | None = Query(None, alias="hostelId"),
    db: Session = Depends(get_db),
):
    if not session_id or not session_id.strip():
        raise HTTPException(400, "sessionId is required")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id.strip())
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    if hostel_id:
        stmt = stmt.where(ChatMessage.hostel_id == hostel_id)
    messages = [chat_message_dict(item) for item in db.scalars(stmt)]
    return response("Chat history retrieved successfully", {"messages": messages})


@app.post("/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)):
    try:
        content = await audio.read()
        if not content:
            raise HTTPException(400, "Audio file is empty")
        text_value = transcribe_audio(
            content,
            audio.filename or "recording.webm",
            audio.content_type or "application/octet-stream",
        )
        return {"text": text_value}
    except HTTPException:
        raise
    except VoiceError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/voice/chat", response_model=ApiResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str | None = Form(None, alias="sessionId"),
    hostel_id: str | None = Form(None, alias="hostelId"),
    speak_reply: bool = Form(True, alias="speakReply"),
    db: Session = Depends(get_db),
):
    if not session_id or not session_id.strip():
        raise HTTPException(400, "sessionId is required")
    content = await audio.read()
    if not content:
        raise HTTPException(400, "Audio file is empty")
    try:
        transcript = transcribe_audio(
            content,
            audio.filename or "recording.webm",
            audio.content_type or "application/octet-stream",
        )
    except VoiceError as exc:
        raise HTTPException(502, str(exc)) from exc

    agent_result = run_agent(
        AgentRequest(
            message=transcript,
            sessionId=session_id,
            hostelId=hostel_id,
        ),
        db,
    )
    agent_data = agent_result["data"]
    reply = agent_data.get("reply")
    audio_base64 = None
    voice_error = None
    if speak_reply and reply:
        try:
            audio_base64 = base64.b64encode(speak(reply)).decode("ascii")
        except VoiceError as exc:
            voice_error = str(exc)

    return response(
        "Voice chat completed",
        {
            "transcript": transcript,
            "reply": reply,
            "tool_used": agent_data.get("tool_used"),
            "tool_calls": agent_data.get("tool_calls", []),
            "audioBase64": audio_base64,
            "audioContentType": "audio/mpeg" if audio_base64 else None,
            "voiceError": voice_error,
        },
        error=agent_result["error"],
    )


@app.post("/voice/speak")
def voice_speak(payload: SpeakRequest):
    try:
        audio = speak(payload.text)
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="speech.mp3"'},
        )
    except VoiceError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/mock-email")
def mock_email(payload: dict):
    return {"message": "Email sent mock successfully", "payload": payload}


@app.post("/hostels", status_code=201, response_model=ApiResponse)
async def create_hostel(
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a hostel with optional image upload to Cloudinary, supporting both JSON and multipart form data"""
    content_type = request.headers.get("content-type", "")
    photo_file = None
    photo_url = None
    
    if "application/json" in content_type:
        try:
            body = await request.json()
            payload = HostelCreate.model_validate(body)
            # Support passing a photo URL in JSON body directly
            photo_url = body.get("photo_url") or body.get("photoUrl")
        except ValidationError as exc:
            raise RequestValidationError(exc.errors())
        except Exception as exc:
            raise RequestValidationError(errors=[{"loc": ["body"], "msg": str(exc), "type": "value_error"}])
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            photo_item = form.get("photo")
            if isinstance(photo_item, UploadFile):
                photo_file = photo_item
            
            # amenities parsing
            amenities_val = form.get("amenities", "[]")
            try:
                amenities_list = json.loads(amenities_val) if isinstance(amenities_val, str) else amenities_val
                if not isinstance(amenities_list, list):
                    amenities_list = []
            except Exception:
                amenities_list = []
            
            price_val = form.get("priceNaira") or form.get("price_naira")
            
            payload_data = {
                "name": form.get("name"),
                "location": form.get("location"),
                "priceNaira": int(price_val) if price_val is not None else None,
                "description": form.get("description", ""),
                "amenities": amenities_list,
                "lat": float(form.get("lat")) if form.get("lat") else None,
                "lng": float(form.get("lng")) if form.get("lng") else None,
            }
            # Remove keys with None values to let Pydantic handle validation/defaults
            payload_data = {k: v for k, v in payload_data.items() if v is not None}
            payload = HostelCreate.model_validate(payload_data)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors())
        except Exception as exc:
            raise RequestValidationError(errors=[{"loc": ["body"], "msg": str(exc), "type": "value_error"}])
    else:
        raise HTTPException(415, "Unsupported Media Type. Must be application/json or multipart/form-data")

    # Upload image to Cloudinary if a file was uploaded in form data
    if photo_file:
        photo_url = await upload_image_to_cloudinary(photo_file)
    
    hostel = Hostel(
        name=payload.name,
        location=payload.location,
        price_naira=payload.price_naira,
        description=payload.description,
        amenities=payload.amenities,
        lat=payload.lat,
        lng=payload.lng,
        photo_url=photo_url or payload.photo_url,
    )
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


@app.put("/hostels/{hostel_id}/photo", response_model=ApiResponse)
async def update_hostel_photo(hostel_id: str, photo: UploadFile, db: Session = Depends(get_db)):
    """Update hostel photo on Cloudinary"""
    hostel = db.get(Hostel, hostel_id)
    if hostel is None:
        raise HTTPException(404, "Hostel not found")
    
    photo_url = await upload_image_to_cloudinary(photo)
    hostel.photo_url = photo_url
    db.commit()
    db.refresh(hostel)
    return response("Hostel photo updated successfully", {"hostel": hostel_dict(hostel)})


@app.post("/hostels/{hostel_id}/reports", status_code=201, response_model=ApiResponse)
def create_report(hostel_id: str, payload: ReportCreate, db: Session = Depends(get_db)):
    if db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")
    report = UtilityReport(hostel_id=hostel_id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return response("Utility report created successfully", {"report": report_dict(report)})


@app.post("/hostels/{hostel_id}/notify-authority", response_model=ApiResponse)
def notify_authority_direct(hostel_id: str, payload: NotifyAuthorityRequest, db: Session = Depends(get_db)):
    if db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")
    result = notify_hostel_authority(hostel_id, payload.issue_type, payload.details)
    status = result.get("status", "failed")
    timestamp = result.get("timestamp")
    return response(
        f"Authority notification {'sent successfully' if status == 'sent' else 'failed'}",
        {"status": status, "timestamp": timestamp},
        error={"code": "NOTIFY_FAILED", "details": result.get("error")} if status == "failed" else None
    )


@app.post("/hostels/{hostel_id}/alert-security", response_model=ApiResponse)
def alert_security_direct(hostel_id: str, payload: AlertSecurityRequest, db: Session = Depends(get_db)):
    if db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")
    result = alert_community_security(hostel_id, payload.reason, payload.evidence)
    status = result.get("status", "failed")
    timestamp = result.get("timestamp")
    return response(
        f"Security alert {'sent successfully' if status == 'sent' else 'failed'}",
        {"status": status, "timestamp": timestamp},
        error={"code": "ALERT_FAILED", "details": result.get("error")} if status == "failed" else None
    )


def run_agent(payload: AgentRequest, db: Session) -> dict:
    if not payload.session_id or not payload.session_id.strip():
        raise HTTPException(400, "sessionId is required")
    session_id = payload.session_id.strip()
    hostel_id = payload.hostel_id.strip() if payload.hostel_id else None
    if hostel_id and db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")

    user_message = ChatMessage(
        session_id=session_id,
        hostel_id=hostel_id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    db.commit()

    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    if hostel_id:
        history_stmt = history_stmt.where(ChatMessage.hostel_id == hostel_id)
    history = [
        {"role": item.role, "content": item.content}
        for item in db.scalars(history_stmt)
    ]
    if hostel_id and history:
        history[-1]["content"] = (
            f"[Current hostel ID: {hostel_id}. Default hostel-specific tool "
            f"arguments to this ID.] {history[-1]['content']}"
        )

    client = GemmaClient()
    message = history[-1]["content"]

    def dispatch(name: str, args: dict[str, Any]) -> dict:
        if name == "checkRentFairness":
            return check_rent_fairness(db, args["location"], args["priceNaira"], args.get("amenities"))
        if name == "checkUtilityReliability":
            selected_hostel_id = args.get("hostelId") or hostel_id
            if not selected_hostel_id:
                return {"error": "hostelId is required"}
            return check_utility_reliability(db, selected_hostel_id)
        if name == "flagScamRisk":
            return flag_scam_risk(db, args["listingText"], args.get("chatTranscript"), client.explain_scam_flags, hostel_id)
        if name == "notifyHostelAuthority":
            selected_hostel_id = args.get("hostelId") or hostel_id
            if not selected_hostel_id:
                return {"error": "hostelId is required"}
            return notify_hostel_authority(selected_hostel_id, args["issueType"], args["details"])
        if name == "alertCommunitySecurity":
            selected_hostel_id = args.get("hostelId") or hostel_id
            if not selected_hostel_id:
                return {"error": "hostelId is required"}
            return alert_community_security(selected_hostel_id, args["reason"], args.get("evidence", ""))
        return {"error": f"Unknown tool: {name}"}

    try:
        reply, calls = client.ask(message, dispatch, history=history)
        db.add(
            ChatMessage(
                session_id=session_id,
                hostel_id=hostel_id,
                role="assistant",
                content=reply,
            )
        )
        db.commit()
        return response("Agent request completed", {"reply": reply, "tool_used": ", ".join(call["name"] for call in calls) or None, "tool_calls": calls})
    except GemmaError as exc:
        return response("Housing Scout's AI service is temporarily unavailable. Please retry shortly.", {"reply": None, "tool_used": None, "tool_calls": []}, error={"code": "GEMMA_UNAVAILABLE", "details": str(exc)})
    except Exception as exc:
        return response("I could not complete that check, but the API is still running.", {"reply": None, "tool_used": None, "tool_calls": []}, error={"code": "AGENT_ERROR", "details": str(exc)})


@app.post("/agent", response_model=ApiResponse)
def agent(payload: AgentRequest, db: Session = Depends(get_db)):
    return run_agent(payload, db)
