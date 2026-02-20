from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.main import DB_PATH, VoiceAgentPlatform

app = FastAPI(title="Voice Agent SaaS API")
_platform: VoiceAgentPlatform | None = None


class CreateUserPayload(BaseModel):
    company_name: str
    email: str
    role: str
    subscription_plan: str


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
    except Exception as exc:  # runtime guard for serverless boot errors
        raise HTTPException(status_code=500, detail=f"Initialization failed: {exc}") from exc
    return {"status": "healthy"}


@app.post("/users")
def create_user(payload: CreateUserPayload) -> dict:
    try:
        platform = _get_platform()
        user = platform.create_user(
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
