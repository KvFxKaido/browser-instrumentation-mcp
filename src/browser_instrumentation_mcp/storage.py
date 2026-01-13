"""Async storage layer for session persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from platformdirs import user_data_dir

from .models import SessionStatus


_APP_NAME = "browser-instrumentation-mcp"
_DB_FILENAME = "sessions.db"


def _get_db_path() -> Path:
    data_dir = Path(user_data_dir(_APP_NAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / _DB_FILENAME


async def _ensure_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            name TEXT PRIMARY KEY,
            status TEXT,
            created_at TEXT,
            escalation_reason TEXT
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            session TEXT,
            event_type TEXT,
            timestamp TEXT,
            details TEXT,
            reason TEXT
        )
        """
    )
    await conn.commit()


def _normalize_status(status: SessionStatus | str) -> str:
    if isinstance(status, SessionStatus):
        return status.value
    return str(status)


def _normalize_timestamp(timestamp: datetime | str) -> str:
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return str(timestamp)


async def save_session(
    name: str,
    status: SessionStatus | str,
    created_at: datetime | str,
    escalation_reason: Optional[str],
) -> None:
    """Insert or update a session record."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        await conn.execute(
            """
            INSERT INTO sessions (name, status, created_at, escalation_reason)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                status = excluded.status,
                created_at = excluded.created_at,
                escalation_reason = excluded.escalation_reason
            """,
            (
                name,
                _normalize_status(status),
                _normalize_timestamp(created_at),
                escalation_reason,
            ),
        )
        await conn.commit()


async def load_session(name: str) -> Optional[dict]:
    """Load a single session record."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        async with conn.execute(
            """
            SELECT name, status, created_at, escalation_reason
            FROM sessions
            WHERE name = ?
            """,
            (name,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)


async def delete_session(name: str) -> bool:
    """Delete a session record."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        cursor = await conn.execute(
            "DELETE FROM sessions WHERE name = ?",
            (name,),
        )
        await conn.commit()
        return cursor.rowcount > 0


async def list_sessions() -> list[dict]:
    """List all session records."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        async with conn.execute(
            """
            SELECT name, status, created_at, escalation_reason
            FROM sessions
            ORDER BY created_at ASC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def save_event(
    session: str,
    event_type: str,
    timestamp: datetime | str,
    details: Optional[dict],
    reason: Optional[str],
) -> None:
    """Insert an event record."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        details_json = json.dumps(details or {}, ensure_ascii=True)
        await conn.execute(
            """
            INSERT INTO events (session, event_type, timestamp, details, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session,
                event_type,
                _normalize_timestamp(timestamp),
                details_json,
                reason,
            ),
        )
        await conn.commit()


async def load_events(session: str) -> list[dict]:
    """Load all events for a session."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)
        async with conn.execute(
            """
            SELECT id, session, event_type, timestamp, details, reason
            FROM events
            WHERE session = ?
            ORDER BY id ASC
            """,
            (session,),
        ) as cursor:
            rows = await cursor.fetchall()
            events: list[dict] = []
            for row in rows:
                event = dict(row)
                details_raw = event.get("details")
                if details_raw:
                    try:
                        event["details"] = json.loads(details_raw)
                    except json.JSONDecodeError:
                        event["details"] = {}
                else:
                    event["details"] = {}
                events.append(event)
            return events
