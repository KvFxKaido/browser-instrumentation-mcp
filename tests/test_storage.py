from datetime import datetime

import pytest

from browser_instrumentation_mcp import storage
from browser_instrumentation_mcp.models import SessionStatus


@pytest.mark.asyncio
async def test_save_and_load_session(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(storage, "_get_db_path", lambda: db_path)

    created_at = datetime.now()
    await storage.save_session(
        name="alpha",
        status=SessionStatus.ACTIVE,
        created_at=created_at,
        escalation_reason=None,
    )

    loaded = await storage.load_session("alpha")
    assert loaded is not None
    assert loaded["name"] == "alpha"
    assert loaded["status"] == SessionStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_list_and_delete_sessions(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(storage, "_get_db_path", lambda: db_path)

    await storage.save_session(
        name="alpha",
        status="active",
        created_at=datetime.now(),
        escalation_reason=None,
    )
    await storage.save_session(
        name="beta",
        status="closed",
        created_at=datetime.now(),
        escalation_reason="done",
    )

    sessions = await storage.list_sessions()
    names = {session["name"] for session in sessions}
    assert names == {"alpha", "beta"}

    deleted = await storage.delete_session("alpha")
    assert deleted is True
    assert await storage.load_session("alpha") is None


@pytest.mark.asyncio
async def test_save_and_load_events(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(storage, "_get_db_path", lambda: db_path)

    await storage.save_event(
        session="alpha",
        event_type="navigate",
        timestamp=datetime.now(),
        details={"url": "https://example.com"},
        reason=None,
    )
    await storage.save_event(
        session="alpha",
        event_type="click",
        timestamp=datetime.now(),
        details={"selector": "#button"},
        reason="testing",
    )

    events = await storage.load_events("alpha")
    assert len(events) == 2
    assert events[0]["event_type"] == "navigate"
    assert events[1]["reason"] == "testing"
