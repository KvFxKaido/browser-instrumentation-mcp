"""Browser session lifecycle management."""

from typing import Optional

from .backends.base import BrowserBackend
from .backends.playwright_backend import PlaywrightBackend
from .models import ActionResult, EventLog


class BrowserManager:
    """Manages browser sessions with instrumentation.

    Provides a high-level interface for browser observation and action.
    Observation is primary; actions require explicit escalation.
    """

    def __init__(self, backend: Optional[BrowserBackend] = None):
        """Initialize browser manager.

        Args:
            backend: Browser backend to use. Defaults to PlaywrightBackend.
        """
        self._backend = backend or PlaywrightBackend()
        self._initialized = False

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

        return await self._backend.create_session(
            name=name,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )

    async def destroy_session(self, name: str) -> bool:
        """Destroy a session."""
        return await self._backend.destroy_session(name)

    async def list_sessions(self) -> list[dict]:
        """List all sessions."""
        return await self._backend.list_sessions()

    async def is_escalated(self, name: str) -> bool:
        """Check if session is escalated for actions."""
        return await self._backend.is_escalated(name)

    async def escalate_session(self, name: str, reason: str) -> dict:
        """Escalate session to allow actions."""
        return await self._backend.escalate_session(name, reason)

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
