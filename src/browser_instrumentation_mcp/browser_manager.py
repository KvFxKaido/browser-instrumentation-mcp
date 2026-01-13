"""Browser session lifecycle management."""

from datetime import datetime
from typing import Optional

from . import storage as storage_module
from .backends.base import BrowserBackend
from .backends.playwright_backend import PlaywrightBackend
from .models import ActionResult, EventLog, SessionStatus


class BrowserManager:
    """Manages browser sessions with instrumentation.

    Provides a high-level interface for browser observation and action.
    Observation is primary; actions require explicit escalation.
    """

    def __init__(
        self,
        backend: Optional[BrowserBackend] = None,
        storage: Optional[object] = None,
    ):
        """Initialize browser manager.

        Args:
            backend: Browser backend to use. Defaults to PlaywrightBackend.
            storage: Optional storage provider for persistence.
        """
        self._backend = backend or PlaywrightBackend()
        self._storage = storage or storage_module
        self._initialized = False

    async def _persist_session(self, name: str) -> None:
        """Persist current session metadata."""
        if self._storage is None:
            return

        session = await self._backend.get_session(name)
        if session is None:
            created_at = datetime.now()
            status = SessionStatus.ACTIVE
            escalation_reason = None
        else:
            created_at = getattr(session, "created_at", datetime.now())
            status = getattr(session, "status", SessionStatus.ACTIVE)
            escalation_reason = getattr(session, "escalation_reason", None)

        await self._storage.save_session(
            name=name,
            status=status,
            created_at=created_at,
            escalation_reason=escalation_reason,
        )

    @property
    def backend(self) -> BrowserBackend:
        """Get the browser backend."""
        return self._backend

    async def initialize(self) -> None:
        """Initialize the browser manager and backend."""
        if not self._initialized:
            await self._backend.initialize()
            self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the browser manager and backend."""
        if self._initialized:
            await self._backend.shutdown()
            self._initialized = False

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        name: str,
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> str:
        """Create a new browser session.

        Sessions start in observation-only mode.
        """
        if not self._initialized:
            await self.initialize()

        session_name = await self._backend.create_session(
            name=name,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        await self._persist_session(session_name)
        return session_name

    async def destroy_session(self, name: str) -> bool:
        """Destroy a session."""
        destroyed = await self._backend.destroy_session(name)
        if destroyed and self._storage is not None:
            await self._storage.delete_session(name)
        return destroyed

    async def list_sessions(self) -> list[dict]:
        """List all sessions."""
        return await self._backend.list_sessions()

    async def is_escalated(self, name: str) -> bool:
        """Check if session is escalated for actions."""
        return await self._backend.is_escalated(name)

    async def escalate_session(self, name: str, reason: str) -> dict:
        """Escalate session to allow actions."""
        result = await self._backend.escalate_session(name, reason)
        await self._persist_session(name)
        return result

    # =========================================================================
    # Event Log
    # =========================================================================

    def get_event_log(self, name: str) -> EventLog:
        """Get the event log for a session."""
        return self._backend.get_event_log(name)

    # =========================================================================
    # INSPECT Operations (Safe)
    # =========================================================================

    async def navigate(self, session: str, url: str) -> dict:
        """Navigate to URL in session."""
        return await self._backend.navigate(session, url)

    async def screenshot(self, session: str, full_page: bool = False) -> bytes:
        """Take screenshot in session."""
        return await self._backend.screenshot(session, full_page)

    async def get_dom(self, session: str, selector: Optional[str] = None) -> dict:
        """Get DOM HTML content."""
        return await self._backend.get_dom(session, selector)

    async def get_text(self, session: str, selector: Optional[str] = None) -> dict:
        """Get text content from page."""
        return await self._backend.get_text(session, selector)

    async def get_console_logs(self, session: str) -> list[dict]:
        """Get captured console log entries."""
        return await self._backend.get_console_logs(session)

    async def get_network_logs(self, session: str) -> list[dict]:
        """Get captured network request entries."""
        return await self._backend.get_network_logs(session)

    # =========================================================================
    # ACT Operations (Require Escalation + Reason)
    # =========================================================================

    async def click(self, session: str, selector: str, reason: str) -> ActionResult:
        """Click element. Requires escalation."""
        return await self._backend.click(session, selector, reason)

    async def type_text(
        self,
        session: str,
        selector: str,
        text: str,
        reason: str,
        clear_first: bool = False,
    ) -> ActionResult:
        """Type text. Requires escalation."""
        return await self._backend.type_text(session, selector, text, reason, clear_first)

    async def execute_script(self, session: str, script: str, reason: str) -> ActionResult:
        """Execute JavaScript. Requires escalation."""
        return await self._backend.execute_script(session, script, reason)
