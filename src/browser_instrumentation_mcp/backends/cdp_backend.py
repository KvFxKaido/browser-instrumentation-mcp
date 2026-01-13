"""Playwright CDP-based browser instrumentation backend."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Playwright,
    Request,
    Response,
    async_playwright,
)

from ..models import (
    ActionResult,
    Confidence,
    Event,
    EventLog,
    EventType,
    ObservedChanges,
    PrePostState,
    SessionStatus,
)
from .base import BrowserBackend


@dataclass
class ConsoleEntry:
    """Captured console message."""

    level: str
    message: str
    timestamp: datetime


@dataclass
class NetworkEntry:
    """Captured network request."""

    method: str
    url: str
    status: Optional[int]
    timestamp: datetime


@dataclass
class CDPSession:
    """Holds Playwright objects and instrumentation data for a CDP session."""

    name: str
    cdp_url: str
    browser: Browser
    context: BrowserContext
    page: Page
    created_at: datetime = field(default_factory=datetime.now)
    status: SessionStatus = SessionStatus.ACTIVE
    escalation_reason: Optional[str] = None
    owns_context: bool = False
    owns_page: bool = False

    # Instrumentation data
    event_log: EventLog = field(default_factory=lambda: EventLog(session=""))
    console_logs: list[ConsoleEntry] = field(default_factory=list)
    network_logs: list[NetworkEntry] = field(default_factory=list)

    # Counters for action observation
    dom_mutation_count: int = 0
    pending_network_count: int = 0

    def __post_init__(self):
        self.event_log = EventLog(session=self.name)


class CDPBackend(BrowserBackend):
    """Playwright CDP-based browser instrumentation backend.

    Connects to an already-running browser over CDP.
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._sessions: dict[str, CDPSession] = {}

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self) -> None:
        """Start Playwright (no browser launch)."""
        self._playwright = await async_playwright().start()

    async def shutdown(self) -> None:
        """Disconnect all sessions and stop Playwright."""
        for name in list(self._sessions.keys()):
            await self.destroy_session(name)

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

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
        """CDP backend does not support create_session."""
        raise ValueError("CDP backend requires connect_session(name, cdp_url)")

    async def connect_session(self, name: str, cdp_url: str) -> str:
        """Connect to an existing browser over CDP."""
        if not self._playwright:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        if name in self._sessions:
            raise ValueError(f"Session '{name}' already exists")

        browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
        context, page, owns_context, owns_page = await self._select_context_and_page(
            browser
        )

        session = CDPSession(
            name=name,
            cdp_url=cdp_url,
            browser=browser,
            context=context,
            page=page,
            owns_context=owns_context,
            owns_page=owns_page,
        )

        self._setup_console_handler(session)
        self._setup_network_handler(session)

        self._sessions[name] = session

        self.log_event(
            Event(
                event_type=EventType.SESSION_CREATED,
                session=name,
                details={"cdp_url": cdp_url},
            )
        )

        return name

    async def _select_context_and_page(
        self, browser: Browser
    ) -> tuple[BrowserContext, Page, bool, bool]:
        """Pick a context/page, creating them if necessary."""
        owns_context = False
        owns_page = False

        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await browser.new_context()
            owns_context = True

        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = await context.new_page()
            owns_page = True

        return context, page, owns_context, owns_page

    async def destroy_session(self, name: str) -> bool:
        """Disconnect from CDP session."""
        session = self._sessions.pop(name, None)
        if session is None:
            return False

        self.log_event(
            Event(
                event_type=EventType.SESSION_DESTROYED,
                session=name,
            )
        )

        if session.owns_page:
            try:
                await session.page.close()
            except Exception:
                pass

        if session.owns_context:
            try:
                await session.context.close()
            except Exception:
                pass

        await self._disconnect_browser(session.browser)
        return True

    async def _disconnect_browser(self, browser: Browser) -> None:
        """Disconnect from the remote browser without closing it."""
        disconnect = getattr(browser, "disconnect", None)
        if callable(disconnect):
            await disconnect()
            return
        await browser.close()

    async def list_sessions(self) -> list[dict]:
        """Return info about all active sessions."""
        result = []
        for session in self._sessions.values():
            try:
                current_url = session.page.url
            except Exception:
                current_url = None

            result.append(
                {
                    "name": session.name,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat(),
                    "current_url": current_url,
                    "event_count": len(session.event_log.events),
                }
            )
        return result

    async def get_session(self, name: str) -> Optional[CDPSession]:
        """Get session by name."""
        return self._sessions.get(name)

    def _require_session(self, name: str) -> CDPSession:
        """Get session or raise error."""
        session = self._sessions.get(name)
        if session is None:
            raise ValueError(f"Session '{name}' not found")
        return session

    async def is_escalated(self, name: str) -> bool:
        """Check if session has been escalated for actions."""
        session = self._require_session(name)
        return session.status == SessionStatus.ESCALATED

    async def escalate_session(self, name: str, reason: str) -> dict:
        """Escalate session to allow actions."""
        session = self._require_session(name)

        if session.status == SessionStatus.ESCALATED:
            return {
                "escalated": True,
                "warning": "Session already escalated",
                "requires_ack": False,
            }

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

    # =========================================================================
    # Event Log
    # =========================================================================

    def get_event_log(self, name: str) -> EventLog:
        """Get the event log for a session."""
        session = self._require_session(name)
        return session.event_log

    def log_event(self, event: Event) -> None:
        """Append an event to a session's log."""
        session = self._sessions.get(event.session)
        if session:
            session.event_log.append(event)

    def _setup_console_handler(self, session: CDPSession) -> None:
        """Set up console message capture."""

        def on_console(msg: ConsoleMessage):
            session.console_logs.append(
                ConsoleEntry(
                    level=msg.type,
                    message=msg.text,
                    timestamp=datetime.now(),
                )
            )

        session.page.on("console", on_console)

    def _setup_network_handler(self, session: CDPSession) -> None:
        """Set up network request capture."""

        def on_request(request: Request):
            session.pending_network_count += 1
            session.network_logs.append(
                NetworkEntry(
                    method=request.method,
                    url=request.url,
                    status=None,
                    timestamp=datetime.now(),
                )
            )

        def on_response(response: Response):
            for entry in reversed(session.network_logs):
                if entry.url == response.url and entry.status is None:
                    entry.status = response.status
                    break

        session.page.on("request", on_request)
        session.page.on("response", on_response)

    # =========================================================================
    # INSPECT Operations
    # =========================================================================

    async def navigate(self, session: str, url: str) -> dict:
        """Navigate to URL."""
        sess = self._require_session(session)

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        await sess.page.goto(url)

        result = {
            "url": sess.page.url,
            "title": await sess.page.title(),
        }

        self.log_event(
            Event(
                event_type=EventType.NAVIGATE,
                session=session,
                details=result,
            )
        )

        return result

    async def screenshot(self, session: str, full_page: bool = False) -> bytes:
        """Take screenshot, return PNG bytes."""
        sess = self._require_session(session)

        screenshot_bytes = await sess.page.screenshot(full_page=full_page)

        self.log_event(
            Event(
                event_type=EventType.SCREENSHOT,
                session=session,
                details={"full_page": full_page, "size_bytes": len(screenshot_bytes)},
            )
        )

        return screenshot_bytes

    async def get_dom(self, session: str, selector: Optional[str] = None) -> dict:
        """Get DOM HTML content."""
        sess = self._require_session(session)

        max_length = 100000

        if selector:
            element = await sess.page.query_selector(selector)
            if element:
                html = await element.inner_html()
            else:
                html = ""
        else:
            html = await sess.page.content()

        original_length = len(html)
        truncated = original_length > max_length

        if truncated:
            html = html[:max_length]

        result = {
            "html": html,
            "truncated": truncated,
            "original_length": original_length if truncated else None,
        }

        self.log_event(
            Event(
                event_type=EventType.DOM_READ,
                session=session,
                details={"selector": selector, "length": len(html), "truncated": truncated},
            )
        )

        return result

    async def get_text(self, session: str, selector: Optional[str] = None) -> dict:
        """Get text content from page or element."""
        sess = self._require_session(session)

        if selector:
            element = await sess.page.query_selector(selector)
            if element:
                text = await element.inner_text()
            else:
                text = ""
        else:
            text = await sess.page.inner_text("body")

        result = {
            "text": text,
            "selector": selector,
        }

        self.log_event(
            Event(
                event_type=EventType.TEXT_READ,
                session=session,
                details={"selector": selector, "length": len(text)},
            )
        )

        return result

    async def get_console_logs(self, session: str) -> list[dict]:
        """Get captured console log entries."""
        sess = self._require_session(session)

        self.log_event(
            Event(
                event_type=EventType.CONSOLE_READ,
                session=session,
                details={"count": len(sess.console_logs)},
            )
        )

        return [
            {
                "level": entry.level,
                "message": entry.message,
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in sess.console_logs
        ]

    async def get_network_logs(self, session: str) -> list[dict]:
        """Get captured network request entries."""
        sess = self._require_session(session)

        self.log_event(
            Event(
                event_type=EventType.NETWORK_READ,
                session=session,
                details={"count": len(sess.network_logs)},
            )
        )

        return [
            {
                "method": entry.method,
                "url": entry.url,
                "status": entry.status,
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in sess.network_logs
        ]

    # =========================================================================
    # ACT Operations
    # =========================================================================

    async def _capture_pre_state(self, sess: CDPSession) -> dict:
        """Capture state before an action."""
        return {
            "url": sess.page.url,
            "title": await sess.page.title(),
            "network_count": len(sess.network_logs),
            "console_count": len(sess.console_logs),
        }

    async def _capture_post_state(self, sess: CDPSession, pre: dict) -> ActionResult:
        """Capture state after an action and compute changes."""
        await asyncio.sleep(0.1)

        post_url = sess.page.url
        post_title = await sess.page.title()
        post_network = len(sess.network_logs)
        post_console = len(sess.console_logs)

        observed = ObservedChanges(
            url_changed=post_url != pre["url"],
            dom_mutations=0,
            network_requests=post_network - pre["network_count"],
            console_messages=post_console - pre["console_count"],
            new_url=post_url if post_url != pre["url"] else None,
        )

        state = PrePostState(
            pre_url=pre["url"],
            post_url=post_url,
            pre_title=pre["title"],
            post_title=post_title,
        )

        if observed.url_changed or observed.network_requests > 0:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        return ActionResult(
            action="",
            observed_changes=observed,
            state=state,
            confidence=confidence,
        )

    def _require_escalation(self, session: str) -> CDPSession:
        """Get session and verify it's escalated for actions."""
        sess = self._require_session(session)
        if sess.status != SessionStatus.ESCALATED:
            raise PermissionError(
                f"Session '{session}' not escalated for actions. "
                "Call browser_session_escalate first with a reason."
            )
        return sess

    async def click(self, session: str, selector: str, reason: str) -> ActionResult:
        """Click element. Requires escalation."""
        sess = self._require_escalation(session)

        pre = await self._capture_pre_state(sess)

        try:
            await sess.page.click(selector, timeout=5000)
            notes = ""
        except Exception as e:
            notes = f"Click may have failed: {e}"

        result = await self._capture_post_state(sess, pre)
        result.action = "click"
        result.selector = selector
        if notes:
            result.notes = notes
            result.confidence = Confidence.LOW

        self.log_event(
            Event(
                event_type=EventType.CLICK,
                session=session,
                reason=reason,
                details={
                    "selector": selector,
                    "observed_changes": result.observed_changes.model_dump(),
                    "confidence": result.confidence.value,
                },
            )
        )

        return result

    async def type_text(
        self,
        session: str,
        selector: str,
        text: str,
        reason: str,
        clear_first: bool = False,
    ) -> ActionResult:
        """Type text into element. Requires escalation."""
        sess = self._require_escalation(session)

        pre = await self._capture_pre_state(sess)

        try:
            if clear_first:
                await sess.page.fill(selector, text, timeout=5000)
            else:
                await sess.page.type(selector, text, timeout=5000)
            notes = ""
        except Exception as e:
            notes = f"Type may have failed: {e}"

        result = await self._capture_post_state(sess, pre)
        result.action = "type"
        result.selector = selector
        if notes:
            result.notes = notes
            result.confidence = Confidence.LOW

        self.log_event(
            Event(
                event_type=EventType.TYPE,
                session=session,
                reason=reason,
                details={
                    "selector": selector,
                    "text_length": len(text),
                    "clear_first": clear_first,
                    "confidence": result.confidence.value,
                },
            )
        )

        return result

    async def execute_script(
        self,
        session: str,
        script: str,
        reason: str,
    ) -> ActionResult:
        """Execute JavaScript. Requires escalation."""
        sess = self._require_escalation(session)

        pre = await self._capture_pre_state(sess)

        try:
            await sess.page.evaluate(script)
            notes = ""
        except Exception as e:
            notes = f"Script may have failed: {e}"

        result = await self._capture_post_state(sess, pre)
        result.action = "execute"
        if notes:
            result.notes = notes
            result.confidence = Confidence.LOW

        self.log_event(
            Event(
                event_type=EventType.EXECUTE,
                session=session,
                reason=reason,
                details={
                    "script_length": len(script),
                    "confidence": result.confidence.value,
                },
            )
        )

        return result
