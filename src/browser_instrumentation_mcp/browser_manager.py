"""Browser session lifecycle management."""

from datetime import datetime
from typing import Optional

from . import storage as storage_module
from .backends.base import BrowserBackend
from .backends.cdp_backend import CDPBackend
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
        cdp_backend: Optional[CDPBackend] = None,
        storage: Optional[object] = None,
    ):
        """Initialize browser manager.

        Args:
            backend: Browser backend to use. Defaults to PlaywrightBackend.
            cdp_backend: CDP backend to use for connecting to existing browsers.
            storage: Optional storage provider for persistence.
        """
        self._backend = backend or PlaywrightBackend()
        self._cdp_backend = cdp_backend or CDPBackend()
        self._storage = storage or storage_module
        self._initialized = False
        self._cdp_initialized = False
        self._session_backends: dict[str, BrowserBackend] = {}

    async def _persist_session(self, name: str) -> None:
        """Persist current session metadata."""
        if self._storage is None:
            return

        session = None
        backend = self._session_backends.get(name)
        if backend:
            session = await backend.get_session(name)
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
        if self._cdp_initialized:
            await self._cdp_backend.shutdown()
            self._cdp_initialized = False

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

        if name in self._session_backends:
            raise ValueError(f"Session '{name}' already exists")

        session_name = await self._backend.create_session(
            name=name,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        self._session_backends[session_name] = self._backend
        await self._persist_session(session_name)
        return session_name

    async def connect_session(self, name: str, cdp_url: str) -> str:
        """Connect to an existing browser session over CDP."""
        if not self._cdp_initialized:
            await self._cdp_backend.initialize()
            self._cdp_initialized = True

        if name in self._session_backends:
            raise ValueError(f"Session '{name}' already exists")

        session_name = await self._cdp_backend.connect_session(name, cdp_url)
        self._session_backends[session_name] = self._cdp_backend
        await self._persist_session(session_name)
        return session_name

    async def destroy_session(self, name: str) -> bool:
        """Destroy a session."""
        backend = self._session_backends.get(name)
        if backend:
            destroyed = await backend.destroy_session(name)
        else:
            destroyed = await self._backend.destroy_session(name)
            if not destroyed and self._cdp_initialized:
                destroyed = await self._cdp_backend.destroy_session(name)
        if destroyed and self._storage is not None:
            await self._storage.delete_session(name)
        if destroyed:
            self._session_backends.pop(name, None)
        return destroyed

    async def list_sessions(self) -> list[dict]:
        """List all sessions."""
        sessions = await self._backend.list_sessions()
        for session in sessions:
            self._session_backends.setdefault(session["name"], self._backend)
        if self._cdp_initialized:
            cdp_sessions = await self._cdp_backend.list_sessions()
            for session in cdp_sessions:
                self._session_backends.setdefault(session["name"], self._cdp_backend)
            sessions.extend(cdp_sessions)
        return sessions

    async def is_escalated(self, name: str) -> bool:
        """Check if session is escalated for actions."""
        backend = await self._resolve_backend(name)
        return await backend.is_escalated(name)

    async def escalate_session(self, name: str, reason: str) -> dict:
        """Escalate session to allow actions."""
        backend = await self._resolve_backend(name)
        result = await backend.escalate_session(name, reason)
        await self._persist_session(name)
        return result

    # =========================================================================
    # Event Log
    # =========================================================================

    def get_event_log(self, name: str) -> EventLog:
        """Get the event log for a session."""
        backend = self._session_backends.get(name)
        if backend is None:
            raise ValueError(f"Session '{name}' not found")
        return backend.get_event_log(name)

    # =========================================================================
    # INSPECT Operations (Safe)
    # =========================================================================

    async def navigate(self, session: str, url: str) -> dict:
        """Navigate to URL in session."""
        backend = await self._resolve_backend(session)
        return await backend.navigate(session, url)

    async def screenshot(self, session: str, full_page: bool = False) -> bytes:
        """Take screenshot in session."""
        backend = await self._resolve_backend(session)
        return await backend.screenshot(session, full_page)

    async def get_dom(self, session: str, selector: Optional[str] = None) -> dict:
        """Get DOM HTML content."""
        backend = await self._resolve_backend(session)
        return await backend.get_dom(session, selector)

    async def get_text(self, session: str, selector: Optional[str] = None) -> dict:
        """Get text content from page."""
        backend = await self._resolve_backend(session)
        return await backend.get_text(session, selector)

    async def get_console_logs(self, session: str) -> list[dict]:
        """Get captured console log entries."""
        backend = await self._resolve_backend(session)
        return await backend.get_console_logs(session)

    async def get_network_logs(self, session: str) -> list[dict]:
        """Get captured network request entries."""
        backend = await self._resolve_backend(session)
        return await backend.get_network_logs(session)

    # =========================================================================
    # ACT Operations (Require Escalation + Reason)
    # =========================================================================

    async def click(self, session: str, selector: str, reason: str) -> ActionResult:
        """Click element. Requires escalation."""
        backend = await self._resolve_backend(session)
        return await backend.click(session, selector, reason)

    async def type_text(
        self,
        session: str,
        selector: str,
        text: str,
        reason: str,
        clear_first: bool = False,
    ) -> ActionResult:
        """Type text. Requires escalation."""
        backend = await self._resolve_backend(session)
        return await backend.type_text(session, selector, text, reason, clear_first)

    async def execute_script(self, session: str, script: str, reason: str) -> ActionResult:
        """Execute JavaScript. Requires escalation."""
        backend = await self._resolve_backend(session)
        return await backend.execute_script(session, script, reason)

    async def _resolve_backend(self, name: str) -> BrowserBackend:
        """Find which backend owns the session."""
        backend = self._session_backends.get(name)
        if backend:
            return backend

        session = await self._backend.get_session(name)
        if session:
            self._session_backends[name] = self._backend
            return self._backend

        if self._cdp_initialized:
            session = await self._cdp_backend.get_session(name)
            if session:
                self._session_backends[name] = self._cdp_backend
                return self._cdp_backend

        raise ValueError(f"Session '{name}' not found")
