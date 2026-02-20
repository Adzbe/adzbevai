from pathlib import Path


def test_vercel_config_and_entrypoint_exist() -> None:
    assert Path("vercel.json").exists()
    website = Path("index.html")
    assert website.exists()
    assert "Complete Live Website" in website.read_text(encoding="utf-8")

    entrypoint = Path("api/index.py")
    assert entrypoint.exists()

    content = entrypoint.read_text(encoding="utf-8")
    assert "VOICE_AGENT_DB_PATH" in content
    assert "/tmp/voice_agents.db" in content
    assert "ADMIN_EMAIL" in content
    assert "ADMIN_PASSWORD" in content


def test_live_endpoints_are_exposed() -> None:
    content = Path("api/index.py").read_text(encoding="utf-8")
    for endpoint in [
        '@app.post("/admin/login")',
        '@app.get("/health")',
        '@app.get("/api/health")',
        '@app.post("/users")',
        '@app.post("/api/users")',
        '@app.post("/users/{user_id}/agents")',
        '@app.get("/agents/public")',
        '@app.post("/agents/{agent_id}/conversations")',
        '@app.post("/conversations/{conversation_id}/push-crm")',
        '@app.get("/users/{user_id}/crm/leads")',
        '@app.patch("/crm/leads/{conversation_id}")',
        '@app.get("/users/{user_id}/crm/export")',
    ]:
        assert endpoint in content
