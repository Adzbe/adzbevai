from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

DB_PATH = Path(__file__).resolve().parent.parent / "voice_agents.db"
SUBSCRIPTION_LIMITS = {"starter": 1, "growth": 5, "enterprise": 50}
GOAL_REQUIRED_FIELDS = {
    "bookings": ["full_name", "phone", "preferred_date", "service_interest"],
    "customer_service": ["full_name", "phone", "issue_summary"],
    "sales": ["full_name", "phone", "budget_range", "product_interest"],
}

QUESTION_TEMPLATES = {
    "en": {
        "full_name": "What is your full name?",
        "phone": "What is your phone number?",
        "email": "What is your email address?",
        "preferred_date": "What date/time do you prefer?",
        "service_interest": "Which service are you interested in?",
        "issue_summary": "Can you briefly describe your issue?",
        "budget_range": "What budget range are you targeting?",
        "product_interest": "Which product are you interested in?",
    },
    "es": {
        "full_name": "¿Cuál es tu nombre completo?",
        "phone": "¿Cuál es tu número de teléfono?",
        "email": "¿Cuál es tu correo electrónico?",
        "preferred_date": "¿Qué fecha/hora prefieres?",
        "service_interest": "¿Qué servicio te interesa?",
        "issue_summary": "¿Puedes describir brevemente tu problema?",
        "budget_range": "¿Cuál es tu rango de presupuesto?",
        "product_interest": "¿Qué producto te interesa?",
    },
}


@dataclass
class User:
    id: int
    company_name: str
    email: str
    role: str
    subscription_plan: str
    is_active: bool


class VoiceAgentPlatform:
    """Core backend logic for a subscription-based voice-agent SaaS MVP."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                subscription_plan TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                business_type TEXT NOT NULL,
                goals TEXT NOT NULL,
                unique_link TEXT NOT NULL UNIQUE,
                languages TEXT NOT NULL,
                training_catalog TEXT NOT NULL,
                training_services TEXT NOT NULL,
                training_prices TEXT NOT NULL,
                training_patterns TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                customer_email TEXT,
                language TEXT,
                intent TEXT,
                details TEXT,
                required_fields_missing TEXT,
                created_at TEXT NOT NULL,
                pushed_to_crm INTEGER NOT NULL DEFAULT 0,
                crm_reference TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                external_crm_name TEXT NOT NULL,
                payload TEXT NOT NULL,
                pushed_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def create_user(self, company_name: str, email: str, role: str, subscription_plan: str) -> User:
        if role not in {"admin", "client"}:
            raise ValueError("role must be admin or client")
        if subscription_plan not in SUBSCRIPTION_LIMITS:
            raise ValueError("invalid subscription plan")

        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users(company_name, email, role, subscription_plan) VALUES (?, ?, ?, ?)",
            (company_name, email, role, subscription_plan),
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return User(user_id, company_name, email, role, subscription_plan, True)

    def list_users(self) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        conn = self._conn()
        updated = conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, user_id),
        ).rowcount
        conn.commit()
        conn.close()
        if updated == 0:
            raise ValueError("user not found")

    def _serialize_training(self, data: list[str]) -> str:
        return " | ".join(item.strip() for item in data if item.strip())

    def create_agent(
        self,
        user_id: int,
        name: str,
        business_type: str,
        goals: list[str],
        languages: list[str],
        products: list[str],
        services: list[str],
        prices: list[str],
        patterns: list[str],
    ) -> dict[str, Any]:
        if not goals:
            raise ValueError("at least one goal is required")
        conn = self._conn()
        user = conn.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
        if not user:
            conn.close()
            raise ValueError("active user not found")
        plan_limit = SUBSCRIPTION_LIMITS[user["subscription_plan"]]
        existing = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE user_id = ?", (user_id,)).fetchone()["c"]
        if existing >= plan_limit:
            conn.close()
            raise ValueError("subscription limit reached")

        link_token = str(uuid.uuid4())
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agents(
                user_id, name, business_type, goals, unique_link, languages,
                training_catalog, training_services, training_prices, training_patterns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name,
                business_type,
                ",".join(goals),
                f"https://voice.example.com/a/{link_token}",
                ",".join(languages),
                self._serialize_training(products),
                self._serialize_training(services),
                self._serialize_training(prices),
                self._serialize_training(patterns),
            ),
        )
        conn.commit()
        agent_id = cur.lastrowid
        conn.close()

        return {
            "id": agent_id,
            "user_id": user_id,
            "name": name,
            "business_type": business_type,
            "goals": goals,
            "unique_link": f"https://voice.example.com/a/{link_token}",
            "languages": languages,
            "training": {
                "products": products,
                "services": services,
                "prices": prices,
                "patterns": patterns,
            },
        }

    def list_agents(self, user_id: int | None = None) -> list[dict[str, Any]]:
        conn = self._conn()
        if user_id is None:
            rows = conn.execute("SELECT * FROM agents ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM agents WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def public_agent_script(self, unique_link: str, language: str = "en") -> dict[str, Any]:
        conn = self._conn()
        agent = conn.execute("SELECT * FROM agents WHERE unique_link = ? AND is_active = 1", (unique_link,)).fetchone()
        conn.close()
        if not agent:
            raise ValueError("agent not found")

        available_languages = [code.strip().lower() for code in agent["languages"].split(",") if code.strip()]
        lang = language.lower() if language.lower() in QUESTION_TEMPLATES else "en"

        goals = [g.strip() for g in agent["goals"].split(",") if g.strip()]
        required_fields: list[str] = ["full_name", "phone", "email"]
        for goal in goals:
            required_fields.extend(GOAL_REQUIRED_FIELDS.get(goal, []))
        required_fields = list(dict.fromkeys(required_fields))

        q_bank = QUESTION_TEMPLATES.get(lang, QUESTION_TEMPLATES["en"])
        questions = [q_bank.get(field, QUESTION_TEMPLATES["en"].get(field, field)) for field in required_fields]

        return {
            "agent_name": agent["name"],
            "business_type": agent["business_type"],
            "supported_languages": available_languages,
            "message": (
                f"Hello, I am {agent['name']}. I can assist with {agent['goals']} for your {agent['business_type']} business."
            ),
            "questions": questions,
            "training_context": {
                "products": agent["training_catalog"],
                "services": agent["training_services"],
                "prices": agent["training_prices"],
            },
        }

    def capture_conversation(
        self,
        agent_id: int,
        language: str,
        intent: str,
        details: str,
        customer_payload: dict[str, str],
    ) -> dict[str, Any]:
        conn = self._conn()
        agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not agent:
            conn.close()
            raise ValueError("agent not found")

        goals = [g.strip() for g in agent["goals"].split(",") if g.strip()]
        required = {"full_name", "phone", "email"}
        for goal in goals:
            required.update(GOAL_REQUIRED_FIELDS.get(goal, []))
        missing = sorted(field for field in required if not customer_payload.get(field, "").strip())

        now = datetime.utcnow().isoformat()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversations(
                agent_id, customer_name, customer_phone, customer_email,
                language, intent, details, required_fields_missing,
                created_at, pushed_to_crm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                customer_payload.get("full_name"),
                customer_payload.get("phone"),
                customer_payload.get("email"),
                language,
                intent,
                details,
                ",".join(missing),
                now,
                0,
            ),
        )
        conn.commit()
        conversation_id = cur.lastrowid
        conn.close()
        return {"conversation_id": conversation_id, "missing_fields": missing}

    def push_conversation_to_crm(self, conversation_id: int, crm_name: str = "generic-crm") -> str:
        conn = self._conn()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not row:
            conn.close()
            raise ValueError("conversation not found")

        crm_ref = f"{crm_name}-{conversation_id}-{uuid.uuid4().hex[:8]}"
        payload = (
            f"name={row['customer_name']};phone={row['customer_phone']};email={row['customer_email']};"
            f"intent={row['intent']};details={row['details']}"
        )
        conn.execute(
            "INSERT INTO crm_events(conversation_id, external_crm_name, payload, pushed_at) VALUES (?, ?, ?, ?)",
            (conversation_id, crm_name, payload, datetime.utcnow().isoformat()),
        )
        conn.execute(
            "UPDATE conversations SET pushed_to_crm = 1, crm_reference = ? WHERE id = ?",
            (crm_ref, conversation_id),
        )
        conn.commit()
        conn.close()
        return crm_ref

    def export_crm_xlsx(self, user_id: int, output_file: Path) -> Path:
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT c.id, a.name AS agent_name, c.customer_name, c.customer_phone,
                   c.customer_email, c.language, c.intent, c.details,
                   c.required_fields_missing, c.created_at, c.pushed_to_crm, c.crm_reference
            FROM conversations c
            JOIN agents a ON a.id = c.agent_id
            WHERE a.user_id = ?
            ORDER BY c.id DESC
            """,
            (user_id,),
        ).fetchall()
        conn.close()

        headers = [
            "Conversation ID",
            "Agent",
            "Customer Name",
            "Phone",
            "Email",
            "Language",
            "Intent",
            "Details",
            "Missing Required Fields",
            "Created At",
            "Pushed To CRM",
            "CRM Reference",
        ]

        table_rows = [headers]
        for row in rows:
            table_rows.append(
                [
                    row["id"],
                    row["agent_name"],
                    row["customer_name"],
                    row["customer_phone"],
                    row["customer_email"],
                    row["language"],
                    row["intent"],
                    row["details"],
                    row["required_fields_missing"],
                    row["created_at"],
                    "yes" if row["pushed_to_crm"] else "no",
                    row["crm_reference"] or "",
                ]
            )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        _write_xlsx(output_file, "CRM Leads", table_rows)
        return output_file


def _write_xlsx(path: Path, sheet_name: str, rows: list[list[Any]]) -> None:
    def cell_xml(value: Any) -> str:
        text = "" if value is None else str(value)
        return f'<c t="inlineStr"><is><t>{escape(text)}</t></is></c>'

    sheet_rows = []
    for idx, row in enumerate(rows, start=1):
        cells = "".join(cell_xml(col) for col in row)
        sheet_rows.append(f'<row r="{idx}">{cells}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
