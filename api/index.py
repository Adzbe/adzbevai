from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.main import DB_PATH, VoiceAgentPlatform

app = FastAPI(title="Voice Agent SaaS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_platform: VoiceAgentPlatform | None = None


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


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "Voice Agent SaaS API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    try:
        _get_platform()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {exc}") from exc
    return {"status": "healthy"}


@app.get("/admin/users")
def list_users() -> list[dict]:
    try:
        return _get_platform().list_users()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.patch("/admin/users/{user_id}/active")
def set_user_active(user_id: int, is_active: bool) -> dict[str, str]:
    try:
        _get_platform().set_user_active(user_id, is_active)
        return {"status": "updated"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.post("/users")
def create_user(payload: CreateUserPayload) -> dict:
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
def list_agents(user_id: int) -> list[dict]:
    try:
        return _get_platform().list_agents(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/agents/public")
def public_agent_script(link: str, language: str = "en") -> dict:
    try:
        return _get_platform().public_agent_script(unique_link=link, language=language)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.post("/agents/{agent_id}/conversations")
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
def push_conversation_to_crm(conversation_id: int, payload: PushCrmPayload) -> dict[str, str]:
    try:
        crm_ref = _get_platform().push_conversation_to_crm(conversation_id, crm_name=payload.crm_name)
        return {"crm_reference": crm_ref}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime failure: {exc}") from exc


@app.get("/users/{user_id}/crm/export")
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
