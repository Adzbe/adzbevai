from pathlib import Path

from app.main import VoiceAgentPlatform


def test_end_to_end_flow(tmp_path: Path) -> None:
    platform = VoiceAgentPlatform(tmp_path / "db.sqlite")

    user = platform.create_user("Acme Dental", "owner@acme.test", "client", "starter")
    agent = platform.create_agent(
        user.id,
        "Acme Voice",
        ["English", "Spanish"],
        "booking and customer support",
        "Braces, cleanings, pricing and promos",
    )

    public_script = platform.public_agent_script(agent["unique_link"])
    assert "questions" in public_script
    assert len(public_script["questions"]) >= 4

    conv_id = platform.capture_conversation(
        agent["id"],
        "John",
        "+123456",
        "john@test.com",
        "English",
        "book appointment",
        "Needs cleaning next week",
    )
    assert conv_id > 0

    export_file = platform.export_crm_excel_compatible_csv(user.id, tmp_path / "crm_export.csv")
    assert export_file.exists()
    assert "Conversation ID" in export_file.read_text(encoding="utf-8")


def test_subscription_limit(tmp_path: Path) -> None:
    platform = VoiceAgentPlatform(tmp_path / "db.sqlite")
    user = platform.create_user("One Agent Co", "a@b.com", "client", "starter")

    platform.create_agent(user.id, "Agent 1", ["English"], "bookings", "services and prices")

    try:
        platform.create_agent(user.id, "Agent 2", ["English"], "support", "faq")
    except ValueError as err:
        assert "subscription limit reached" in str(err)
    else:
        raise AssertionError("Expected subscription limit error")
