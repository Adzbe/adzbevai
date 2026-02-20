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


## Vercel deployment notes (`NOT_FOUND` fix)

If Vercel returns `NOT_FOUND`, it usually means no deployable route matched the incoming path.

This repo now includes:

- `api/index.py` as a Vercel Python serverless entrypoint (FastAPI app),
- `vercel.json` rewrites so both `/` and any other path route to `api/index.py`.

After pushing, redeploy and verify:

- `/` returns API status,
- `/health` returns healthy response.


### `FUNCTION_INVOCATION_FAILED` note

If Vercel shows `FUNCTION_INVOCATION_FAILED`, your function matched a route but crashed while running.

In serverless environments, writing to the project directory can fail because it is read-only.
This API now resolves DB path as:

1. `VOICE_AGENT_DB_PATH` (if provided),
2. `/tmp/voice_agents.db` on Vercel,
3. local default path in non-serverless runs.

This prevents SQLite initialization crashes during function startup.


## Live API endpoints

- `GET /` - service status
- `GET /health` - runtime readiness
- `GET /admin/users` - list users
- `PATCH /admin/users/{user_id}/active?is_active=true|false` - activate/deactivate user
- `POST /users` - create user
- `POST /users/{user_id}/agents` - create trained agent with unique link
- `GET /users/{user_id}/agents` - list user agents
- `GET /agents/public?link=<unique_link>&language=en|es` - get customer question flow
- `POST /agents/{agent_id}/conversations` - capture customer conversation
- `POST /conversations/{conversation_id}/push-crm` - mark/push to CRM
- `GET /users/{user_id}/crm/export` - download CRM `.xlsx`

## Go-live checklist

1. Set Vercel env vars if needed: `VOICE_AGENT_DB_PATH` (optional override).
2. Deploy and verify `GET /` and `GET /health`.
3. Create a user via `POST /users`.
4. Create an agent via `POST /users/{user_id}/agents` and place the returned `unique_link` in ads/websites.
5. Capture leads via `/agents/{agent_id}/conversations` and push to CRM with `/conversations/{id}/push-crm`.
6. Export records from `/users/{user_id}/crm/export`.


## Website

- Open the root URL of your deployment to access the live dashboard UI (`index.html`).
- The dashboard connects to backend endpoints under `/api/*` and lets you create users/agents and fetch agent scripts.
