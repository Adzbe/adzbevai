from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.main import DB_PATH, VoiceAgentPlatform

app = FastAPI(title="Voice Agent SaaS API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_platform: VoiceAgentPlatform | None = None


class AdminLoginPayload(BaseModel):
    email: str
    password: str


class CreateUserPayload(BaseModel):
    company_name: str
    email: str
    role: str
    subscription_plan: str


class CreateAgentPayload(BaseModel):
    name: str
    business_type: str
    goals: list[str]
    languages: list[str]
    products: list[str]
    services: list[str]
    prices: list[str]
    patterns: list[str]


class CaptureConversationPayload(BaseModel):
    language: str
    intent: str
    details: str
    customer_payload: dict[str, str]


class PushCrmPayload(BaseModel):
    crm_name: str = "generic-crm"


class UpdateLeadPayload(BaseModel):
    lead_status: str | None = None
    lead_notes: str | None = None
    assigned_to: str | None = None


def _resolve_db_path() -> Path:
    override = os.getenv("VOICE_AGENT_DB_PATH")
    if override:
        return Path(override)
    if os.getenv("VERCEL"):
        return Path("/tmp/voice_agents.db")
    return DB_PATH


def _get_platform() -> VoiceAgentPlatform:
    global _platform
    if _platform is None:
        db_path = _resolve_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _platform = VoiceAgentPlatform(db_path=db_path)
    return _platform


def _admin_email() -> str:
    return os.getenv("ADMIN_EMAIL", "admin@voiceagent.ai")


def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "Admin@2026")


def _auth_secret() -> str:
    return os.getenv("AUTH_SECRET", "voice-agent-secret")


def _create_admin_token(email: str) -> str:
    expiration = int(time.time()) + 60 * 60 * 8
    payload = f"{email}:{expiration}"
    signature = hmac.new(_auth_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _require_admin(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin token required")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        email, expiry_text, signature = decoded.split(":", maxsplit=2)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid admin token") from exc

    payload = f"{email}:{expiry_text}"
    expected = hmac.new(_auth_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token signature")

    if email != _admin_email() or int(expiry_text) < int(time.time()):
        raise HTTPException(status_code=401, detail="Expired or unauthorized admin token")


@app.get("/")
def website_root() -> dict[str, str]:
    return {"status": "ok", "message": "Voice Agent SaaS API is running"}


@app.post("/admin/login")
@app.post("/api/admin/login")
def admin_login(payload: AdminLoginPayload) -> dict[str, str]:
    if payload.email != _admin_email() or payload.password != _admin_password():
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"access_token": _create_admin_token(payload.email), "token_type": "bearer"}


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        _get_platform()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {exc}") from exc
    return {"status": "healthy"}


@app.get("/admin/users")
@app.get("/api/admin/users")
def list_users(authorization: str | None = Header(default=None)) -> list[dict]:
    _require_admin(authorization)
    try:
        return _get_platform().list_users()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.patch("/admin/users/{user_id}/active")
@app.patch("/api/admin/users/{user_id}/active")
def set_user_active(user_id: int, is_active: bool, authorization: str | None = Header(default=None)) -> dict[str, str]:
    _require_admin(authorization)
    try:
        _get_platform().set_user_active(user_id, is_active)
        return {"status": "updated"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.post("/users")
@app.post("/api/users")
def create_user(payload: CreateUserPayload, authorization: str | None = Header(default=None)) -> dict:
    _require_admin(authorization)
    try:
        user = _get_platform().create_user(
            payload.company_name,
            payload.email,
            payload.role,
            payload.subscription_plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc

    return {
        "id": user.id,
        "company_name": user.company_name,
        "email": user.email,
        "role": user.role,
        "subscription_plan": user.subscription_plan,
        "is_active": user.is_active,
    }


@app.post("/users/{user_id}/agents")
@app.post("/api/users/{user_id}/agents")
def create_agent(user_id: int, payload: CreateAgentPayload) -> dict:
    try:
        return _get_platform().create_agent(
            user_id=user_id,
            name=payload.name,
            business_type=payload.business_type,
            goals=payload.goals,
            languages=payload.languages,
            products=payload.products,
            services=payload.services,
            prices=payload.prices,
            patterns=payload.patterns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/users/{user_id}/agents")
@app.get("/api/users/{user_id}/agents")
def list_agents(user_id: int) -> list[dict]:
    try:
        return _get_platform().list_agents(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/agents/public")
@app.get("/api/agents/public")
def public_agent_script(link: str, language: str = "en") -> dict:
    try:
        return _get_platform().public_agent_script(unique_link=link, language=language)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.post("/agents/{agent_id}/conversations")
@app.post("/api/agents/{agent_id}/conversations")
def capture_conversation(agent_id: int, payload: CaptureConversationPayload) -> dict:
    try:
        return _get_platform().capture_conversation(
            agent_id=agent_id,
            language=payload.language,
            intent=payload.intent,
            details=payload.details,
            customer_payload=payload.customer_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.post("/conversations/{conversation_id}/push-crm")
@app.post("/api/conversations/{conversation_id}/push-crm")
def push_conversation_to_crm(conversation_id: int, payload: PushCrmPayload) -> dict[str, str]:
    try:
        crm_ref = _get_platform().push_conversation_to_crm(conversation_id, crm_name=payload.crm_name)
        return {"crm_reference": crm_ref}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/users/{user_id}/crm/leads")
@app.get("/api/users/{user_id}/crm/leads")
def list_internal_crm_leads(user_id: int, status: str | None = None) -> list[dict]:
    try:
        return _get_platform().list_internal_crm_leads(user_id=user_id, status=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.patch("/crm/leads/{conversation_id}")
@app.patch("/api/crm/leads/{conversation_id}")
def update_internal_crm_lead(conversation_id: int, payload: UpdateLeadPayload) -> dict:
    try:
        return _get_platform().update_internal_crm_lead(
            conversation_id,
            lead_status=payload.lead_status,
            lead_notes=payload.lead_notes,
            assigned_to=payload.assigned_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/users/{user_id}/crm/export")
@app.get("/api/users/{user_id}/crm/export")
def export_crm(user_id: int) -> FileResponse:
    try:
        export_path = Path("/tmp") / f"crm-user-{user_id}.xlsx"
        file_path = _get_platform().export_crm_xlsx(user_id, export_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"crm-user-{user_id}.xlsx",
    )
