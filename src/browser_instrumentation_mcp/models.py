"""Pydantic models for browser instrumentation data."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class SessionStatus(str, Enum):
    """Status of a browser session."""

    ACTIVE = "active"
    ESCALATED = "escalated"  # Session has been granted action privileges
    CLOSED = "closed"


class Confidence(str, Enum):
    """Confidence level in action outcome."""

    LOW = "low"  # Significant uncertainty about what happened
    MEDIUM = "medium"  # Some uncertainty
    HIGH = "high"  # High confidence in observed outcome


class EventType(str, Enum):
    """Type of event in the session log."""

    SESSION_CREATED = "session_created"
    SESSION_DESTROYED = "session_destroyed"
    SESSION_ESCALATED = "session_escalated"
    NAVIGATE = "navigate"
    SCREENSHOT = "screenshot"
    DOM_READ = "dom_read"
    TEXT_READ = "text_read"
    CONSOLE_READ = "console_read"
    NETWORK_READ = "network_read"
    CLICK = "click"
    TYPE = "type"
    EXECUTE = "execute"
    ERROR = "error"


# =============================================================================
# Event Log Models
# =============================================================================


class Event(BaseModel):
    """A single event in the session log."""

    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: EventType
    session: str
    details: dict = Field(default_factory=dict)
    reason: Optional[str] = None  # Required for ACT events


class EventLog(BaseModel):
    """Append-only event log for a session."""

    session: str
    events: list[Event] = Field(default_factory=list)

    def append(self, event: Event) -> None:
        """Append an event to the log."""
        self.events.append(event)

    def to_list(self) -> list[dict]:
        """Convert to list of dicts for serialization."""
        return [e.model_dump() for e in self.events]


# =============================================================================
# Session Models
# =============================================================================


class SessionInfo(BaseModel):
    """Information about a browser session."""

    name: str
    status: SessionStatus
    created_at: datetime
    current_url: Optional[str] = None
    event_count: int = 0


class SessionCreateOptions(BaseModel):
    """Options for creating a new browser session."""

    headless: bool = Field(default=False, description="Run browser in headless mode")
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)


# =============================================================================
# Observation Models (for INSPECT tools)
# =============================================================================


class NavigateResult(BaseModel):
    """Result of a navigation observation."""

    url: str
    title: str
    timestamp: datetime = Field(default_factory=datetime.now)


class DomSnapshot(BaseModel):
    """Snapshot of DOM state."""

    html: str
    timestamp: datetime = Field(default_factory=datetime.now)
    truncated: bool = False
    original_length: Optional[int] = None


class TextContent(BaseModel):
    """Text content extracted from page."""

    text: str
    selector: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ConsoleEntry(BaseModel):
    """A console log entry."""

    level: str  # log, warn, error, info
    message: str
    timestamp: datetime


class NetworkEntry(BaseModel):
    """A network request entry."""

    method: str
    url: str
    status: Optional[int] = None
    timestamp: datetime


# =============================================================================
# Action Result Models (for ACT tools)
# =============================================================================


class ObservedChanges(BaseModel):
    """Changes observed after an action."""

    url_changed: bool = False
    dom_mutations: int = 0
    network_requests: int = 0
    console_messages: int = 0
    new_url: Optional[str] = None


class PrePostState(BaseModel):
    """Pre and post state for an action."""

    pre_url: str
    post_url: str
    pre_title: str
    post_title: str


class ActionResult(BaseModel):
    """Result of an action (click, type, execute).

    Does NOT use success/failure boolean.
    Instead reports what was observed.
    """

    action: str
    selector: Optional[str] = None
    observed_changes: ObservedChanges
    state: PrePostState
    confidence: Confidence
    notes: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Escalation Models
# =============================================================================


class EscalationRequest(BaseModel):
    """Request to escalate a session for action privileges."""

    session: str
    reason: str
    acknowledged_warning: bool = False


class EscalationResult(BaseModel):
    """Result of an escalation request."""

    session: str
    escalated: bool
    warning: str
    requires_ack: bool = True
