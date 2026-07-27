from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar
import base64
import os
import json

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Path, Query, Request, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException
import cloudinary
import cloudinary.uploader

load_dotenv(".env.local")
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
    search_hostels,
)
from voice import VoiceError, speak, transcribe_audio  # noqa: E402

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

app = FastAPI(
    title="HavenCheck API",
    version="1.0.0",
    description=(
        "Find and evaluate student hostels, submit utility reports, contact "
        "hostel/community authorities, and use the text or voice housing assistant.\n\n"
        "Most JSON endpoints return the same envelope: `message`, `data`, `action`, "
        "and `error`. The voice transcription, speech, and mock-email endpoints are "
        "the documented exceptions."
    ),
    openapi_tags=[
        {"name": "System", "description": "API discovery and health checks."},
        {"name": "Hostels", "description": "Browse, create, and update hostel listings."},
        {"name": "Reports", "description": "Submit hostel utility observations."},
        {"name": "Escalations", "description": "Send authority notifications and security alerts."},
        {"name": "Assistant", "description": "Text chat and session-scoped conversation history."},
        {"name": "Voice", "description": "Speech transcription, voice chat, and text-to-speech."},
        {"name": "Development", "description": "Development-only helper endpoints."},
    ],
)

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class AgentRequest(BaseModel):
    message: str = Field(
        min_length=1,
        examples=["Is 150k for a room in Tanke fair?"],
    )
    session_id: str | None = Field(
        None,
        alias="sessionId",
        description="Required conversation identifier used to isolate chat history.",
        examples=["browser-session-123"],
    )
    hostel_id: str | None = Field(
        None,
        alias="hostelId",
        description="Optional hostel context for history and assistant tools.",
        examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"],
    )
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "message": "Is 150k for a room in Tanke fair?",
                    "sessionId": "browser-session-123",
                },
                {
                    "message": "Has this hostel had water problems?",
                    "sessionId": "browser-session-123",
                    "hostelId": "bd616ac1-3824-5a90-ae8a-ba1a0929c261",
                },
            ]
        },
    )


class SpeakRequest(BaseModel):
    text: str = Field(
        min_length=1,
        examples=["This hostel is within the normal price range."],
    )


class HostelCreate(BaseModel):
    name: str = Field(examples=["Test Lodge"])
    location: str = Field(examples=["Tanke"])
    price_naira: int = Field(alias="priceNaira", gt=0, examples=[145000])
    amenities: list[str] = Field(
        default_factory=list,
        examples=[["borehole"]],
    )
    description: str = Field(examples=["Inspection available"])
    lat: float | None = Field(None, examples=[8.48])
    lng: float | None = Field(None, examples=[4.54])
    photo_url: str | None = Field(
        None,
        alias="photoUrl",
        description="An existing image URL. For an upload, use multipart form data and `photo`.",
    )
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Test Lodge",
                    "location": "Tanke",
                    "priceNaira": 145000,
                    "amenities": ["borehole"],
                    "description": "Inspection available",
                    "photoUrl": None,
                    "lat": 8.48,
                    "lng": 4.54,
                }
            ]
        },
    )


class ReportCreate(BaseModel):
    water_available: bool = Field(examples=[False])
    electricity_issue: bool = Field(examples=[True])
    comment: str = Field(examples=["No water since Monday"])


class NotifyAuthorityRequest(BaseModel):
    issue_type: str = Field(alias="issueType", examples=["water outage"])
    details: str = Field(examples=["There has been no running water since Monday."])
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "issueType": "water outage",
                    "details": "There has been no running water since Monday.",
                }
            ]
        },
    )


class AlertSecurityRequest(BaseModel):
    reason: str = Field(examples=["Suspicious payment request"])
    evidence: str = Field(
        "",
        examples=["The agent requested payment before an inspection."],
    )
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "reason": "Suspicious payment request",
                    "evidence": "The agent requested payment before an inspection.",
                }
            ]
        },
    )


class Action(BaseModel):
    type: str
    url: str | None = None


class ApiError(BaseModel):
    code: str
    details: Any


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    message: str
    data: DataT
    action: Action | None = None
    error: ApiError | None = None


class StatusData(BaseModel):
    status: Literal["ok"]


class UtilityReportResponse(BaseModel):
    id: int
    hostel_id: str
    water_available: bool
    electricity_issue: bool
    comment: str
    reported_at: datetime | None


class HostelResponse(BaseModel):
    id: str
    name: str
    location: str
    priceNaira: int
    amenities: list[str]
    description: str
    photo_url: str | None
    lat: float | None
    lng: float | None
    isSchoolManaged: bool
    scamRiskLevel: str | None
    utility_reports: list[UtilityReportResponse] = Field(default_factory=list)


class HostelData(BaseModel):
    hostel: HostelResponse


class HostelsData(BaseModel):
    hostels: list[HostelResponse]


class ReportData(BaseModel):
    report: UtilityReportResponse


class ChatMessageResponse(BaseModel):
    id: int
    sessionId: str
    hostelId: str | None
    role: Literal["user", "assistant"]
    content: str
    createdAt: datetime | None


class ChatHistoryData(BaseModel):
    messages: list[ChatMessageResponse]


class ToolCallResponse(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentData(BaseModel):
    reply: str | None
    tool_used: str | None
    tool_calls: list[ToolCallResponse]


class VoiceChatData(AgentData):
    transcript: str
    audioBase64: str | None
    audioContentType: Literal["audio/mpeg"] | None
    voiceError: str | None


class TranscriptionResponse(BaseModel):
    text: str


class EscalationData(BaseModel):
    status: Literal["sent", "failed"]
    timestamp: datetime | None


class MockEmailResponse(BaseModel):
    message: str
    payload: dict[str, Any]


ERROR_RESPONSES = {
    400: {"model": ApiResponse[dict[str, Any]], "description": "Invalid request or empty upload."},
    404: {"model": ApiResponse[dict[str, Any]], "description": "The requested hostel or route was not found."},
    422: {"model": ApiResponse[dict[str, Any]], "description": "Request validation failed."},
    500: {"model": ApiResponse[dict[str, Any]], "description": "Unexpected server error."},
}


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
            folder="HavenCheck_Hostel_Image",
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

@app.get("/", response_model=ApiResponse[StatusData], tags=["System"], summary="API overview")
def root():
    return response("Welcome to the Housing Scout API. Access /docs for API documentation.", {"status": "ok"})

@app.get("/health", response_model=ApiResponse[StatusData], tags=["System"], summary="Check API health")
def health():
    return response("API is healthy", {"status": "ok"})


@app.get(
    "/chat/history",
    response_model=ApiResponse[ChatHistoryData],
    tags=["Assistant"],
    summary="Get session chat history",
    description=(
        "Returns one isolated conversation scope for the required `sessionId`. "
        "Without `hostelId`, only general-chat messages are returned. With "
        "`hostelId`, only messages for that hostel are returned."
    ),
    responses=ERROR_RESPONSES,
)
def chat_history(
    session_id: str | None = Query(
        None,
        alias="sessionId",
        description="Required conversation identifier.",
        examples=["browser-session-123"],
    ),
    hostel_id: str | None = Query(
        None,
        alias="hostelId",
        description="Optionally return only messages about this hostel.",
        examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"],
    ),
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
    else:
        stmt = stmt.where(ChatMessage.hostel_id.is_(None))
    messages = [chat_message_dict(item) for item in db.scalars(stmt)]
    return response("Chat history retrieved successfully", {"messages": messages})


@app.post(
    "/voice/transcribe",
    response_model=TranscriptionResponse,
    tags=["Voice"],
    summary="Transcribe an audio file",
    responses={400: ERROR_RESPONSES[400], 502: {"model": ApiResponse[dict[str, Any]], "description": "Speech provider failed."}},
)
async def voice_transcribe(
    audio: UploadFile = File(
        ...,
        description="Browser recording or another audio file to transcribe.",
    )
):
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


@app.post(
    "/voice/chat",
    response_model=ApiResponse[VoiceChatData],
    tags=["Voice"],
    summary="Send a voice message to the assistant",
    description="Transcribes the upload, saves the conversation, runs the assistant, and optionally embeds an MP3 reply as base64.",
    responses={**ERROR_RESPONSES, 502: {"model": ApiResponse[dict[str, Any]], "description": "Transcription provider failed."}},
)
async def voice_chat(
    audio: UploadFile = File(..., description="Browser recording or another audio file."),
    session_id: str | None = Form(
        None,
        alias="sessionId",
        description="Required conversation identifier.",
        examples=["browser-session-123"],
    ),
    hostel_id: str | None = Form(
        None,
        alias="hostelId",
        examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"],
    ),
    speak_reply: bool = Form(
        True,
        alias="speakReply",
        description="When true, attempt to include the assistant reply as a base64 MP3.",
    ),
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


@app.post(
    "/voice/speak",
    response_class=Response,
    tags=["Voice"],
    summary="Convert text to MP3 speech",
    responses={
        200: {"description": "MP3 audio.", "content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}}},
        502: {"model": ApiResponse[dict[str, Any]], "description": "Text-to-speech provider failed."},
    },
)
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


@app.post("/mock-email", response_model=MockEmailResponse, tags=["Development"], summary="Echo a mock email payload")
def mock_email(payload: dict):
    return {"message": "Email sent mock successfully", "payload": payload}


@app.post(
    "/hostels",
    status_code=201,
    response_model=ApiResponse[HostelData],
    tags=["Hostels"],
    summary="Create a hostel",
    description=(
        "Accepts either JSON or form data. In multipart requests, `amenities` is a "
        "JSON array string and `photo` is an optional JPEG, PNG, GIF, or WebP file "
        "(maximum 5 MB). A supplied photo is uploaded to Cloudinary."
    ),
    responses={**ERROR_RESPONSES, 415: {"model": ApiResponse[dict[str, Any]], "description": "Unsupported Content-Type."}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": HostelCreate.model_json_schema(by_alias=True),
                    "example": {
                        "name": "Test Lodge",
                        "location": "Tanke",
                        "priceNaira": 145000,
                        "amenities": ["borehole"],
                        "description": "Inspection available",
                        "photoUrl": None,
                        "lat": 8.48,
                        "lng": 4.54,
                    },
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["name", "location", "priceNaira"],
                        "properties": {
                            "name": {"type": "string"},
                            "location": {"type": "string"},
                            "priceNaira": {"type": "integer", "minimum": 1},
                            "amenities": {"type": "string", "default": "[]", "description": "JSON array string, e.g. `[\"borehole\", \"wifi\"]`."},
                            "description": {"type": "string", "default": ""},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                            "photo": {"type": "string", "format": "binary"},
                        },
                    }
                },
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "required": ["name", "location", "priceNaira"],
                        "properties": {
                            "name": {"type": "string"},
                            "location": {"type": "string"},
                            "priceNaira": {"type": "integer", "minimum": 1},
                            "amenities": {"type": "string", "default": "[]", "description": "JSON array string."},
                            "description": {"type": "string", "default": ""},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                        },
                    }
                },
            },
        }
    },
)
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


@app.get("/hostels", response_model=ApiResponse[HostelsData], tags=["Hostels"], summary="List and filter hostels", responses=ERROR_RESPONSES)
def list_hostels(
    location: str | None = Query(None, examples=["Tanke"]),
    max_price: int | None = Query(None, alias="maxPrice", gt=0, examples=[170000]),
    db: Session = Depends(get_db),
):
    stmt = select(Hostel).order_by(Hostel.name)
    if location:
        stmt = stmt.where(func.lower(Hostel.location) == location.strip().lower())
    if max_price is not None:
        stmt = stmt.where(Hostel.price_naira <= max_price)
    return response("Hostels retrieved successfully", {"hostels": [hostel_dict(hostel) for hostel in db.scalars(stmt)]})


@app.get("/hostels/{hostel_id}", response_model=ApiResponse[HostelData], tags=["Hostels"], summary="Get a hostel with utility reports", responses=ERROR_RESPONSES)
def get_hostel(
    hostel_id: str = Path(..., examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"]),
    db: Session = Depends(get_db),
):
    hostel = db.scalar(select(Hostel).options(selectinload(Hostel.utility_reports)).where(Hostel.id == hostel_id))
    if hostel is None:
        raise HTTPException(404, "Hostel not found")
    return response("Hostel retrieved successfully", {"hostel": hostel_dict(hostel, include_reports=True)})


@app.put(
    "/hostels/{hostel_id}/photo",
    response_model=ApiResponse[HostelData],
    tags=["Hostels"],
    summary="Replace a hostel photo",
    description="Uploads one JPEG, PNG, GIF, or WebP image (maximum 5 MB) to Cloudinary.",
    responses=ERROR_RESPONSES,
)
async def update_hostel_photo(
    hostel_id: str = Path(..., examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"]),
    photo: UploadFile = File(..., description="JPEG, PNG, GIF, or WebP image; maximum 5 MB."),
    db: Session = Depends(get_db),
):
    """Update hostel photo on Cloudinary"""
    hostel = db.get(Hostel, hostel_id)
    if hostel is None:
        raise HTTPException(404, "Hostel not found")
    
    photo_url = await upload_image_to_cloudinary(photo)
    hostel.photo_url = photo_url
    db.commit()
    db.refresh(hostel)
    return response("Hostel photo updated successfully", {"hostel": hostel_dict(hostel)})


@app.post("/hostels/{hostel_id}/reports", status_code=201, response_model=ApiResponse[ReportData], tags=["Reports"], summary="Submit a utility report", responses=ERROR_RESPONSES)
def create_report(
    hostel_id: str = Path(..., examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"]),
    payload: ReportCreate = ...,
    db: Session = Depends(get_db),
):
    if db.get(Hostel, hostel_id) is None:
        raise HTTPException(404, "Hostel not found")
    report = UtilityReport(hostel_id=hostel_id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return response("Utility report created successfully", {"report": report_dict(report)})


@app.post("/hostels/{hostel_id}/notify-authority", response_model=ApiResponse[EscalationData], tags=["Escalations"], summary="Notify a hostel authority", responses=ERROR_RESPONSES)
def notify_authority_direct(
    hostel_id: str = Path(..., examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"]),
    payload: NotifyAuthorityRequest = ...,
    db: Session = Depends(get_db),
):
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


@app.post("/hostels/{hostel_id}/alert-security", response_model=ApiResponse[EscalationData], tags=["Escalations"], summary="Alert community security", responses=ERROR_RESPONSES)
def alert_security_direct(
    hostel_id: str = Path(..., examples=["bd616ac1-3824-5a90-ae8a-ba1a0929c261"]),
    payload: AlertSecurityRequest = ...,
    db: Session = Depends(get_db),
):
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
    else:
        history_stmt = history_stmt.where(ChatMessage.hostel_id.is_(None))
    history = [
        {"role": item.role, "content": item.content}
        for item in db.scalars(history_stmt)
    ]
    if hostel_id and history:
        hostel = db.get(Hostel, hostel_id)
        hostel_context = {
            "id": hostel.id,
            "name": hostel.name,
            "location": hostel.location,
            "priceNaira": hostel.price_naira,
            "amenities": hostel.amenities or [],
            "description": hostel.description,
            "isSchoolManaged": hostel.is_school_managed,
            "scamRiskLevel": hostel.scam_risk_level,
            "frontendUrl": (
                f"{os.getenv('NEXT_PUBLIC_API_BASE_LIVE_FE_URL', 'http://localhost:3000').rstrip('/')}"
                f"/hostels/{hostel.id}"
            ),
        }
        history[-1]["content"] = (
            "TRUSTED CURRENT HOSTEL DATA FROM THE DATABASE:\n"
            f"{json.dumps(hostel_context, ensure_ascii=False)}\n\n"
            f"STUDENT QUESTION:\n{payload.message}"
        )

    client = GemmaClient()
    message = history[-1]["content"]

    def dispatch(name: str, args: dict[str, Any]) -> dict:
        if name == "searchHostels":
            return search_hostels(
                db,
                name=args.get("name"),
                location=args.get("location"),
            )
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


@app.post(
    "/agent",
    response_model=ApiResponse[AgentData],
    tags=["Assistant"],
    summary="Send a text message to the housing assistant",
    description="`sessionId` is required. `hostelId`, when supplied, scopes history and hostel-specific tool calls.",
    responses=ERROR_RESPONSES,
)
def agent(payload: AgentRequest, db: Session = Depends(get_db)):
    return run_agent(payload, db)
