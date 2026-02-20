# Voice Agent SaaS (improved MVP backend)

This backend MVP now supports the requested business flow more completely:

- multi-tenant users with subscription tiers,
- admin-style user controls (list users, activate/deactivate),
- user-created AI voice agents with **unique public links** for ads/websites,
- training context per agent (products, services, prices, patterns),
- multilingual question generation and goal-driven customer data capture,
- conversation logging with required-field validation,
- CRM push tracking with CRM reference IDs,
- true `.xlsx` export for CRM leads.

## Core class

Use `VoiceAgentPlatform` from `app/main.py`.

## Quick example

```python
from pathlib import Path
from app.main import VoiceAgentPlatform

platform = VoiceAgentPlatform()

user = platform.create_user("Acme Dental", "owner@acme.test", "client", "growth")
agent = platform.create_agent(
    user_id=user.id,
    name="Dental Assistant AI",
    business_type="dental",
    goals=["bookings", "customer_service"],
    languages=["en", "es"],
    products=["Teeth Whitening"],
    services=["Cleaning", "Braces Consultation"],
    prices=["Cleaning: $80", "Consultation: $30"],
    patterns=["Ask preferred date", "Confirm contact details"],
)

script = platform.public_agent_script(agent["unique_link"], language="es")
capture = platform.capture_conversation(
    agent_id=agent["id"],
    language="es",
    intent="booking",
    details="Wants cleaning appointment",
    customer_payload={
        "full_name": "Carlos",
        "phone": "+123456",
        "email": "carlos@example.com",
        "preferred_date": "2026-03-01 10:00",
        "service_interest": "Cleaning",
    },
)
crm_reference = platform.push_conversation_to_crm(capture["conversation_id"], crm_name="hubspot")
platform.export_crm_xlsx(user.id, Path("exports/crm.xlsx"))
```

## Tests

```bash
pytest -q
```
