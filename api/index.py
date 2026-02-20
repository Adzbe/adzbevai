from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.main import VoiceAgentPlatform

app = FastAPI(title="Voice Agent SaaS API")
platform = VoiceAgentPlatform()


class CreateUserPayload(BaseModel):
    company_name: str
    email: str
    role: str
    subscription_plan: str


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "Voice Agent SaaS API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/users")
def create_user(payload: CreateUserPayload) -> dict:
    try:
        user = platform.create_user(
            payload.company_name,
            payload.email,
            payload.role,
            payload.subscription_plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": user.id,
        "company_name": user.company_name,
        "email": user.email,
        "role": user.role,
        "subscription_plan": user.subscription_plan,
        "is_active": user.is_active,
    }
