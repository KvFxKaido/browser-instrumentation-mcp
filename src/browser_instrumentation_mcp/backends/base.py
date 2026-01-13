"""Abstract base class for browser instrumentation backends."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models import ActionResult, Event, EventLog


class BrowserBackend(ABC):
    """Abstract base class for browser instrumentation backends.

    Implementations provide browser observation and action capabilities.
    Observation is primary; action is secondary and requires justification.
    """

    # =========================================================================
    # Lifecycle
    # =========================================================================

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (start browser, etc.)."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up backend resources."""
        pass

    # =========================================================================
    # Session Management
    # =========================================================================

    @abstractmethod
    async def create_session(
        self,
        name: str,
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> str:
        """Create a new browser session.

        Sessions start in observation-only mode.
        Actions require explicit escalation.
        """
        pass

    @abstractmethod
    async def destroy_session(self, name: str) -> bool:
        """Destroy a session and clean up resources."""
        pass

    @abstractmethod
    async def list_sessions(self) -> list[dict]:
        """List all active sessions with status and event count."""
        pass

    @abstractmethod
    async def get_session(self, name: str) -> Optional[Any]:
        """Get session by name, or None if not found."""
        pass

    @abstractmethod
    async def is_escalated(self, name: str) -> bool:
        """Check if session has been escalated for actions."""
        pass

    @abstractmethod
    async def escalate_session(self, name: str, reason: str) -> dict:
        """Escalate session to allow actions. Returns warning info."""
        pass

    # =========================================================================
    # Event Log
    # =========================================================================

    @abstractmethod
    def get_event_log(self, name: str) -> EventLog:
        """Get the event log for a session."""
        pass

    @abstractmethod
    def log_event(self, event: Event) -> None:
        """Append an event to a session's log."""
        pass

    # =========================================================================
    # INSPECT Operations (Safe, Encouraged)
    # =========================================================================

    @abstractmethod
    async def navigate(self, session: str, url: str) -> dict:
        """Navigate to URL. Returns url, title."""
        pass

    @abstractmethod
    async def screenshot(self, session: str, full_page: bool = False) -> bytes:
        """Take screenshot. Returns PNG bytes."""
        pass

    @abstractmethod
    async def get_dom(self, session: str, selector: Optional[str] = None) -> dict:
        """Get DOM HTML. Returns html, truncated flag, original_length."""
        pass

    @abstractmethod
    async def get_text(self, session: str, selector: Optional[str] = None) -> dict:
        """Get text content. Returns text, selector."""
        pass

    @abstractmethod
    async def get_console_logs(self, session: str) -> list[dict]:
        """Get captured console log entries."""
        pass

    @abstractmethod
    async def get_network_logs(self, session: str) -> list[dict]:
        """Get captured network request entries."""
        pass

    # =========================================================================
    # ACT Operations (Dangerous, Require Escalation + Reason)
    # =========================================================================

    @abstractmethod
    async def click(self, session: str, selector: str, reason: str) -> ActionResult:
        """Click element. Requires escalation and reason.

        Returns observed changes, not success/failure.
        """
        pass

    @abstractmethod
    async def type_text(
        self,
        session: str,
        selector: str,
        text: str,
        reason: str,
        clear_first: bool = False,
    ) -> ActionResult:
        """Type text into element. Requires escalation and reason.

        Returns observed changes, not success/failure.
        """
        pass

    @abstractmethod
    async def execute_script(
        self,
        session: str,
        script: str,
        reason: str,
    ) -> ActionResult:
        """Execute JavaScript. Requires escalation and reason.

        Returns observed changes, not success/failure.
        """
        pass
