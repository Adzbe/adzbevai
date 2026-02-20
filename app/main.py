from __future__ import annotations

import csv
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "voice_agents.db"
SUBSCRIPTION_LIMITS = {"starter": 1, "growth": 5, "enterprise": 50}


@dataclass
class User:
    id: int
    company_name: str
    email: str
    role: str
    subscription_plan: str
    is_active: bool


class VoiceAgentPlatform:
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
                unique_link TEXT NOT NULL UNIQUE,
                languages TEXT NOT NULL,
                goal TEXT NOT NULL,
                training_notes TEXT NOT NULL
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
                created_at TEXT NOT NULL,
                pushed_to_crm INTEGER NOT NULL DEFAULT 0
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

    def deactivate_user(self, user_id: int) -> None:
        conn = self._conn()
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

    def create_agent(self, user_id: int, name: str, languages: list[str], goal: str, training_notes: str) -> dict:
        conn = self._conn()
        user = conn.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
        if not user:
            conn.close()
            raise ValueError("active user not found")
        limit = SUBSCRIPTION_LIMITS[user["subscription_plan"]]
        existing = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE user_id = ?", (user_id,)).fetchone()["c"]
        if existing >= limit:
            conn.close()
            raise ValueError("subscription limit reached")

        link = str(uuid.uuid4())
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agents(user_id, name, unique_link, languages, goal, training_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, link, ",".join(languages), goal, training_notes),
        )
        conn.commit()
        agent_id = cur.lastrowid
        conn.close()
        return {
            "id": agent_id,
            "user_id": user_id,
            "name": name,
            "unique_link": link,
            "languages": languages,
            "goal": goal,
            "training_notes": training_notes,
        }

    def public_agent_script(self, unique_link: str) -> dict:
        conn = self._conn()
        agent = conn.execute("SELECT * FROM agents WHERE unique_link = ?", (unique_link,)).fetchone()
        conn.close()
        if not agent:
            raise ValueError("agent not found")

        return {
            "message": (
                f"Hi, I'm {agent['name']}. I can help with {agent['goal']} in {agent['languages']}. "
                "Please share your details for booking/support."
            ),
            "questions": [
                "What is your full name?",
                "Which product or service do you need?",
                "What date/time do you prefer?",
                "Please share your phone/email for confirmation.",
            ],
        }

    def capture_conversation(
        self,
        agent_id: int,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        language: str,
        intent: str,
        details: str,
    ) -> int:
        conn = self._conn()
        found = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not found:
            conn.close()
            raise ValueError("agent not found")
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversations(
                agent_id, customer_name, customer_phone, customer_email,
                language, intent, details, created_at, pushed_to_crm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                agent_id,
                customer_name,
                customer_phone,
                customer_email,
                language,
                intent,
                details,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conv_id = cur.lastrowid
        conn.close()
        return conv_id

    def export_crm_excel_compatible_csv(self, user_id: int, output_file: Path) -> Path:
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT c.*, a.name AS agent_name
            FROM conversations c
            JOIN agents a ON a.id = c.agent_id
            WHERE a.user_id = ?
            ORDER BY c.id DESC
            """,
            (user_id,),
        ).fetchall()
        conn.close()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Conversation ID",
                    "Agent",
                    "Customer Name",
                    "Phone",
                    "Email",
                    "Language",
                    "Intent",
                    "Details",
                    "Created At",
                    "Pushed To CRM",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["id"],
                        row["agent_name"],
                        row["customer_name"],
                        row["customer_phone"],
                        row["customer_email"],
                        row["language"],
                        row["intent"],
                        row["details"],
                        row["created_at"],
                        "yes" if row["pushed_to_crm"] else "no",
                    ]
                )
        return output_file
