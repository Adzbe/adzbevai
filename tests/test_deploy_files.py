from pathlib import Path


def test_vercel_config_and_entrypoint_exist() -> None:
    assert Path("vercel.json").exists()
    entrypoint = Path("api/index.py")
    assert entrypoint.exists()

    content = entrypoint.read_text(encoding="utf-8")
    assert "VOICE_AGENT_DB_PATH" in content
    assert "/tmp/voice_agents.db" in content
