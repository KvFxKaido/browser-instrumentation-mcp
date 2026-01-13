from datetime import datetime

import pytest

from browser_instrumentation_mcp.models import (
    ActionResult,
    Confidence,
    ConsoleEntry,
    DomSnapshot,
    EscalationRequest,
    EscalationResult,
    Event,
    EventLog,
    EventType,
    NavigateResult,
    NetworkEntry,
    ObservedChanges,
    PrePostState,
    SessionCreateOptions,
    SessionInfo,
    SessionStatus,
    TextContent,
)


def test_event_log_append_and_serialize() -> None:
    event_log = EventLog(session="alpha")
    event = Event(
        event_type=EventType.NAVIGATE,
        session="alpha",
        details={"url": "https://example.com"},
    )
    event_log.append(event)

    assert len(event_log.events) == 1
    payload = event_log.to_list()
    assert payload[0]["event_type"] == EventType.NAVIGATE.value
    assert payload[0]["details"]["url"] == "https://example.com"


def test_session_create_options_validation() -> None:
    options = SessionCreateOptions(headless=True, viewport_width=1280, viewport_height=720)
    assert options.headless is True

    with pytest.raises(ValueError):
        SessionCreateOptions(viewport_width=100)

    with pytest.raises(ValueError):
        SessionCreateOptions(viewport_height=10000)


def test_session_info_defaults() -> None:
    info = SessionInfo(
        name="alpha",
        status=SessionStatus.ACTIVE,
        created_at=datetime.now(),
    )
    assert info.event_count == 0


def test_observation_models_round_trip() -> None:
    nav = NavigateResult(url="https://example.com", title="Example")
    snap = DomSnapshot(html="<html></html>")
    text = TextContent(text="hello", selector="#main")
    console = ConsoleEntry(level="info", message="ok", timestamp=datetime.now())
    network = NetworkEntry(method="GET", url="https://example.com", status=200, timestamp=datetime.now())

    assert nav.url == "https://example.com"
    assert snap.truncated is False
    assert text.selector == "#main"
    assert console.level == "info"
    assert network.status == 200


def test_action_result_defaults() -> None:
    observed = ObservedChanges()
    state = PrePostState(
        pre_url="https://example.com",
        post_url="https://example.com",
        pre_title="Example",
        post_title="Example",
    )
    result = ActionResult(
        action="click",
        selector="#button",
        observed_changes=observed,
        state=state,
        confidence=Confidence.LOW,
    )

    assert result.notes == ""
    payload = result.model_dump()
    assert payload["confidence"] == Confidence.LOW.value


def test_escalation_models() -> None:
    request = EscalationRequest(session="alpha", reason="need to click")
    result = EscalationResult(session="alpha", escalated=True, warning="ok")

    assert request.acknowledged_warning is False
    assert result.requires_ack is True
