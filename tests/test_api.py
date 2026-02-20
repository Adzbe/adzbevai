from pathlib import Path

from app.main import VoiceAgentPlatform


def test_end_to_end_with_multilingual_crm_and_xlsx(tmp_path: Path) -> None:
    platform = VoiceAgentPlatform(tmp_path / "db.sqlite")

    user = platform.create_user("Acme Dental", "owner@acme.test", "client", "starter")
    agent = platform.create_agent(
        user_id=user.id,
        name="Acme Voice",
        business_type="dental",
        goals=["bookings", "customer_service"],
        languages=["en", "es"],
        products=["Whitening"],
        services=["Cleaning", "Braces"],
        prices=["Cleaning: $80"],
        patterns=["Collect name and phone", "Offer nearest slot"],
    )

    assert agent["unique_link"].startswith("https://voice.example.com/a/")

    script = platform.public_agent_script(agent["unique_link"], language="es")
    assert "supported_languages" in script
    assert "es" in script["supported_languages"]
    assert len(script["questions"]) >= 4

    capture = platform.capture_conversation(
        agent_id=agent["id"],
        language="es",
        intent="booking",
        details="Customer asked for next-week cleaning",
        customer_payload={
            "full_name": "Carlos",
            "phone": "+34123456",
            "email": "carlos@example.com",
            "preferred_date": "2026-03-10 10:30",
            "service_interest": "Cleaning",
            "issue_summary": "Need appointment support",
        },
    )
    assert capture["conversation_id"] > 0
    assert capture["missing_fields"] == []

    crm_ref = platform.push_conversation_to_crm(capture["conversation_id"], crm_name="hubspot")
    assert crm_ref.startswith("hubspot-")

    xlsx_file = platform.export_crm_xlsx(user.id, tmp_path / "crm_export.xlsx")
    assert xlsx_file.exists()
    assert xlsx_file.suffix == ".xlsx"


def test_subscription_limit_and_admin_control(tmp_path: Path) -> None:
    platform = VoiceAgentPlatform(tmp_path / "db.sqlite")
    user = platform.create_user("One Agent Co", "a@b.com", "client", "starter")

    platform.create_agent(
        user_id=user.id,
        name="Agent 1",
        business_type="clinic",
        goals=["bookings"],
        languages=["en"],
        products=["Consultation"],
        services=["General visit"],
        prices=["Visit: $60"],
        patterns=["Collect booking info"],
    )

    try:
        platform.create_agent(
            user_id=user.id,
            name="Agent 2",
            business_type="clinic",
            goals=["bookings"],
            languages=["en"],
            products=["Follow-up"],
            services=["Follow-up visit"],
            prices=["Visit: $30"],
            patterns=["Collect issue summary"],
        )
    except ValueError as err:
        assert "subscription limit reached" in str(err)
    else:
        raise AssertionError("Expected subscription limit error")

    platform.set_user_active(user.id, False)
    try:
        platform.create_agent(
            user_id=user.id,
            name="Agent 3",
            business_type="clinic",
            goals=["customer_service"],
            languages=["en"],
            products=["N/A"],
            services=["Support"],
            prices=["N/A"],
            patterns=["Collect phone"],
        )
    except ValueError as err:
        assert "active user not found" in str(err)
    else:
        raise AssertionError("Expected deactivated user error")
