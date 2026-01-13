"""Shared pytest fixtures and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from browser_instrumentation_mcp.backends.base import BrowserBackend
from browser_instrumentation_mcp.models import (
    ActionResult,
    Confidence,
    Event,
    EventLog,
    EventType,
    ObservedChanges,
    PrePostState,
    SessionStatus,
)


@dataclass
class FakeSession:
    name: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    escalation_reason: Optional[str] = None
    event_log: EventLog = field(default_factory=lambda: EventLog(session=""))

    def __post_init__(self) -> None:
        self.event_log = EventLog(session=self.name)


class FakeBackend(BrowserBackend):
    def __init__(self) -> None:
        self.sessions: dict[str, FakeSession] = {}

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        self.sessions.clear()

    async def create_session(
        self,
        name: str,
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> str:
        if name in self.sessions:
            raise ValueError(f"Session '{name}' already exists")
        self.sessions[name] = FakeSession(name=name)
        self.log_event(
            Event(event_type=EventType.SESSION_CREATED, session=name, details={})
        )
        return name

    async def destroy_session(self, name: str) -> bool:
        if name not in self.sessions:
            return False
        self.log_event(Event(event_type=EventType.SESSION_DESTROYED, session=name))
        self.sessions.pop(name, None)
        return True

    async def list_sessions(self) -> list[dict]:
        return [
            {
                "name": session.name,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "current_url": None,
                "event_count": len(session.event_log.events),
            }
            for session in self.sessions.values()
        ]

    async def get_session(self, name: str) -> Optional[FakeSession]:
        return self.sessions.get(name)

    async def is_escalated(self, name: str) -> bool:
        session = self.sessions.get(name)
        if session is None:
            raise ValueError(f"Session '{name}' not found")
        return session.status == SessionStatus.ESCALATED

    async def escalate_session(self, name: str, reason: str) -> dict:
        session = self.sessions.get(name)
        if session is None:
            raise ValueError(f"Session '{name}' not found")
        session.status = SessionStatus.ESCALATED
        session.escalation_reason = reason
        self.log_event(
            Event(
                event_type=EventType.SESSION_ESCALATED,
                session=name,
                reason=reason,
                details={"escalation_reason": reason},
            )
        )
        return {
            "escalated": True,
            "warning": "Session now allows actions. Actions will be logged and may have side effects.",
            "requires_ack": True,
        }

    def get_event_log(self, name: str) -> EventLog:
        session = self.sessions.get(name)
        if session is None:
            raise ValueError(f"Session '{name}' not found")
        return session.event_log

    def log_event(self, event: Event) -> None:
        session = self.sessions.get(event.session)
        if session:
            session.event_log.append(event)

    async def navigate(self, session: str, url: str) -> dict:
        self.log_event(Event(event_type=EventType.NAVIGATE, session=session, details={}))
        return {"url": url, "title": "Fake"}

    async def screenshot(self, session: str, full_page: bool = False) -> bytes:
        self.log_event(
            Event(
                event_type=EventType.SCREENSHOT,
                session=session,
                details={"full_page": full_page},
            )
        )
        return b"fake-png"

    async def get_dom(self, session: str, selector: Optional[str] = None) -> dict:
        self.log_event(
            Event(
                event_type=EventType.DOM_READ,
                session=session,
                details={"selector": selector},
            )
        )
        return {"html": "<html></html>", "truncated": False, "original_length": None}

    async def get_text(self, session: str, selector: Optional[str] = None) -> dict:
        self.log_event(
            Event(
                event_type=EventType.TEXT_READ,
                session=session,
                details={"selector": selector},
            )
        )
        return {"text": "hello", "selector": selector}

    async def get_console_logs(self, session: str) -> list[dict]:
        self.log_event(
            Event(
                event_type=EventType.CONSOLE_READ,
                session=session,
                details={"count": 0},
            )
        )
        return []

    async def get_network_logs(self, session: str) -> list[dict]:
        self.log_event(
            Event(
                event_type=EventType.NETWORK_READ,
                session=session,
                details={"count": 0},
            )
        )
        return []

    async def click(self, session: str, selector: str, reason: str) -> ActionResult:
        return _build_action_result("click", selector)

    async def type_text(
        self,
        session: str,
        selector: str,
        text: str,
        reason: str,
        clear_first: bool = False,
    ) -> ActionResult:
        return _build_action_result("type", selector)

    async def execute_script(self, session: str, script: str, reason: str) -> ActionResult:
        return _build_action_result("execute", None)


class FakeCDPBackend(FakeBackend):
    async def connect_session(self, name: str, cdp_url: str) -> str:
        return await self.create_session(name=name)


def _build_action_result(action: str, selector: Optional[str]) -> ActionResult:
    observed = ObservedChanges(url_changed=False, dom_mutations=0, network_requests=0)
    state = PrePostState(
        pre_url="about:blank",
        post_url="about:blank",
        pre_title="",
        post_title="",
    )
    return ActionResult(
        action=action,
        selector=selector,
        observed_changes=observed,
        state=state,
        confidence=Confidence.LOW,
    )


class FakeStorage:
    def __init__(self) -> None:
        self.saved: list[dict] = []
        self.deleted: list[str] = []

    async def save_session(
        self,
        name: str,
        status: SessionStatus,
        created_at: datetime,
        escalation_reason: Optional[str],
    ) -> None:
        self.saved.append(
            {
                "name": name,
                "status": status,
                "created_at": created_at,
                "escalation_reason": escalation_reason,
            }
        )

    async def delete_session(self, name: str) -> bool:
        self.deleted.append(name)
        return True


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def fake_cdp_backend() -> FakeCDPBackend:
    return FakeCDPBackend()


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest_asyncio.fixture
async def manager(fake_backend: FakeBackend, fake_cdp_backend: FakeCDPBackend, fake_storage: FakeStorage):
    from browser_instrumentation_mcp.browser_manager import BrowserManager

    return BrowserManager(
        backend=fake_backend,
        cdp_backend=fake_cdp_backend,
        storage=fake_storage,
    )
