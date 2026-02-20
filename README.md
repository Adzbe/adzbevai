# Voice Agent SaaS (MVP backend logic)

A Python MVP that implements the core workflow for your request:

- client accounts with subscription plans,
- admin visibility/control over users,
- user-created and trained voice agents (business-specific data, prices, services, patterns),
- unique per-agent link for ads/websites,
- customer conversation capture for booking + support,
- multilingual configuration per agent,
- CRM push flag per conversation,
- Excel-compatible CRM export (CSV that opens in Excel).

## Quick usage

```python
from pathlib import Path
from app.main import VoiceAgentPlatform

platform = VoiceAgentPlatform()
user = platform.create_user("Acme Dental", "owner@acme.test", "client", "growth")
agent = platform.create_agent(
    user.id,
    "Dental Assistant AI",
    ["English", "Spanish", "Arabic"],
    "bookings and customer service",
    "Services, pricing, promos, call patterns",
)
script = platform.public_agent_script(agent["unique_link"])
conv_id = platform.capture_conversation(
    agent["id"],
    "John",
    "+1234567",
    "john@test.com",
    "English",
    "booking",
    "Requested cleaning appointment for next week",
)
platform.export_crm_excel_compatible_csv(user.id, Path("exports/user-crm.csv"))
```

## Tests

```bash
pytest
```
