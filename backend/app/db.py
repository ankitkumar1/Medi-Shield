import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import ROOT, settings


def database_path() -> Path:
    raw = settings.database_url.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        existing = {row[1] for row in connection.execute("PRAGMA table_info(cases)")}
        for name, declaration in (
            ("doc_type", "TEXT"),
            ("decision", "TEXT"),
            ("confidence", "REAL"),
            ("justification", "TEXT"),
            ("agents_json", "TEXT"),
        ):
            if name not in existing:
                connection.execute(f"ALTER TABLE cases ADD COLUMN {name} {declaration}")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL
            )
            """
        )


def add_audit(case_id: str, actor: str, action: str, detail: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO audit_log (case_id, created_at, actor, action, detail) VALUES (?, ?, ?, ?, ?)",
            (case_id, datetime.now(timezone.utc).isoformat(), actor, action, detail),
        )


def audit_for(case_id: str) -> list[sqlite3.Row]:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY id ASC",
            (case_id,),
        ).fetchall()
