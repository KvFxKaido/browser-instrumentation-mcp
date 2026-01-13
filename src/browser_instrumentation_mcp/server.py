"""Browser Instrumentation MCP Server - Observation first, action second."""

import base64
import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .browser_manager import BrowserManager

# Global browser manager instance
_manager: Optional[BrowserManager] = None


def get_manager() -> BrowserManager:
    """Get or create the browser manager."""
    global _manager
    if _manager is None:
        _manager = BrowserManager()
    return _manager


# Create FastMCP server
mcp = FastMCP(
    name="Browser Instrumentation",
)


# =============================================================================
# Session Management Tools
# =============================================================================


@mcp.tool()
async def browser_session_create(
    name: str,
    headless: bool = False,
    viewport_width: int = 1280,
    viewport_height: int = 720,
) -> str:
    """Create a new browser session for observation.

    Sessions start in observation-only mode. Actions require explicit escalation.

    Args:
        name: Unique name for the session (e.g., "main", "test-session")
        headless: If True, run browser without visible window
        viewport_width: Browser viewport width in pixels (default: 1280)
        viewport_height: Browser viewport height in pixels (default: 720)

    Returns:
        Confirmation message with session name and status
    """
    manager = get_manager()

    try:
        session_name = await manager.create_session(
            name=name,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        return f"Created session '{session_name}' (observation-only mode)"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Failed to create session: {e}"


@mcp.tool()
async def browser_session_list() -> str:
    """List all browser sessions with their status.

    Returns:
        List of sessions showing name, status (active/escalated), and current URL
    """
    manager = get_manager()
    sessions = await manager.list_sessions()

    if not sessions:
        return "No active sessions"

    lines = ["Sessions:"]
    for s in sessions:
        status = s["status"]
        url = s.get("current_url", "about:blank")
        events = s.get("event_count", 0)
        lines.append(f"  - {s['name']} [{status}] ({events} events) - {url}")

    return "\n".join(lines)


@mcp.tool()
async def browser_session_destroy(name: str) -> str:
    """Destroy a browser session and clean up resources.

    Args:
        name: Name of the session to destroy

    Returns:
        Confirmation message
    """
    manager = get_manager()
    destroyed = await manager.destroy_session(name)

    if destroyed:
        return f"Destroyed session '{name}'"
    else:
        return f"Session '{name}' not found"


@mcp.tool()
async def browser_session_escalate(name: str, reason: str) -> str:
    """Escalate a session to allow action tools (click, type, execute).

    WARNING: This enables side effects. Actions will be logged.

    Args:
        name: Name of the session to escalate
        reason: Justification for why actions are needed

    Returns:
        Warning message and confirmation
    """
    manager = get_manager()

    try:
        result = await manager.escalate_session(name, reason)
        return (
            f"Session '{name}' escalated.\n"
            f"Warning: {result['warning']}\n"
            f"Reason logged: {reason}"
        )
    except ValueError as e:
        return f"Error: {e}"


# =============================================================================
# INSPECT Tools (Safe, Encouraged)
# =============================================================================


@mcp.tool()
async def browser_inspect_navigate(session: str, url: str) -> str:
    """Navigate to a URL for observation.

    Navigation is considered an inspect operation because it sets up
    what you want to observe.

    Args:
        session: Name of the browser session
        url: URL to navigate to (https:// added if no protocol specified)

    Returns:
        The page title and final URL after navigation
    """
    manager = get_manager()

    try:
        result = await manager.navigate(session, url)
        return f"Navigated to: {result['url']}\nTitle: {result['title']}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Navigation failed: {e}"


@mcp.tool()
async def browser_inspect_screenshot(session: str, full_page: bool = False) -> str:
    """Take a screenshot of the current page.

    Args:
        session: Name of the browser session
        full_page: If True, capture the entire scrollable page

    Returns:
        Base64-encoded PNG screenshot with data URI prefix
    """
    manager = get_manager()

    try:
        screenshot_bytes = await manager.screenshot(session, full_page)
        b64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64_data}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Screenshot failed: {e}"


@mcp.tool()
async def browser_inspect_dom(session: str, selector: Optional[str] = None) -> str:
    """Get DOM HTML content from the page.

    Args:
        session: Name of the browser session
        selector: Optional CSS selector to get specific element's HTML

    Returns:
        HTML content (truncated if over 100KB)
    """
    manager = get_manager()

    try:
        result = await manager.get_dom(session, selector)
        output = result["html"]
        if result["truncated"]:
            output += f"\n\n[Truncated from {result['original_length']} bytes]"
        return output
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"DOM read failed: {e}"


@mcp.tool()
async def browser_inspect_text(session: str, selector: Optional[str] = None) -> str:
    """Get text content from the page (no HTML tags).

    Args:
        session: Name of the browser session
        selector: Optional CSS selector to get specific element's text

    Returns:
        Text content of the page or element
    """
    manager = get_manager()

    try:
        result = await manager.get_text(session, selector)
        return result["text"]
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Text read failed: {e}"


@mcp.tool()
async def browser_inspect_console(session: str) -> str:
    """Get captured console log messages from the page.

    Args:
        session: Name of the browser session

    Returns:
        JSON array of console entries with level, message, and timestamp
    """
    manager = get_manager()

    try:
        logs = await manager.get_console_logs(session)
        if not logs:
            return "No console messages captured"
        return json.dumps(logs, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Console read failed: {e}"


@mcp.tool()
async def browser_inspect_network(session: str) -> str:
    """Get captured network requests from the page.

    Args:
        session: Name of the browser session

    Returns:
        JSON array of network entries with method, url, status, and timestamp
    """
    manager = get_manager()

    try:
        logs = await manager.get_network_logs(session)
        if not logs:
            return "No network requests captured"
        return json.dumps(logs, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Network read failed: {e}"


@mcp.tool()
async def browser_inspect_events(session: str) -> str:
    """Get the event log for a session.

    The event log is append-only and records all tool calls made to this session.

    Args:
        session: Name of the browser session

    Returns:
        JSON array of all events in chronological order
    """
    manager = get_manager()

    try:
        event_log = manager.get_event_log(session)
        events = event_log.to_list()
        if not events:
            return "No events recorded"

        # Convert datetime objects to strings for JSON
        for event in events:
            if "timestamp" in event:
                event["timestamp"] = str(event["timestamp"])

        return json.dumps(events, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Event log read failed: {e}"


# =============================================================================
# ACT Tools (Dangerous, Require Escalation + Reason)
# =============================================================================


@mcp.tool()
async def browser_act_click(session: str, selector: str, reason: str) -> str:
    """Click an element on the page.

    REQUIRES: Session must be escalated first via browser_session_escalate.

    Args:
        session: Name of the browser session
        selector: CSS selector for the element to click
        reason: Justification for why this click is necessary

    Returns:
        Observed changes after the click (NOT success/failure)
    """
    manager = get_manager()

    try:
        result = await manager.click(session, selector, reason)
        return _format_action_result(result)
    except PermissionError as e:
        return f"Error: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Click failed: {e}"


@mcp.tool()
async def browser_act_type(
    session: str,
    selector: str,
    text: str,
    reason: str,
    clear_first: bool = False,
) -> str:
    """Type text into an input element.

    REQUIRES: Session must be escalated first via browser_session_escalate.

    Args:
        session: Name of the browser session
        selector: CSS selector for the input element
        text: Text to type
        reason: Justification for why this input is necessary
        clear_first: If True, clear the input before typing

    Returns:
        Observed changes after typing (NOT success/failure)
    """
    manager = get_manager()

    try:
        result = await manager.type_text(session, selector, text, reason, clear_first)
        return _format_action_result(result)
    except PermissionError as e:
        return f"Error: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Type failed: {e}"


@mcp.tool()
async def browser_act_execute(session: str, script: str, reason: str) -> str:
    """Execute JavaScript in the browser context.

    REQUIRES: Session must be escalated first via browser_session_escalate.

    Args:
        session: Name of the browser session
        script: JavaScript code to execute
        reason: Justification for why this script is necessary

    Returns:
        Observed changes after execution (NOT success/failure)
    """
    manager = get_manager()

    try:
        result = await manager.execute_script(session, script, reason)
        return _format_action_result(result)
    except PermissionError as e:
        return f"Error: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Execute failed: {e}"


def _format_action_result(result) -> str:
    """Format an ActionResult for display."""
    changes = result.observed_changes
    state = result.state

    lines = [
        f"Action: {result.action}",
        f"Confidence: {result.confidence.value}",
        "",
        "Observed Changes:",
        f"  URL changed: {changes.url_changed}",
        f"  Network requests: {changes.network_requests}",
        f"  Console messages: {changes.console_messages}",
    ]

    if changes.new_url:
        lines.append(f"  New URL: {changes.new_url}")

    lines.extend(
        [
            "",
            "State:",
            f"  Before: {state.pre_url}",
            f"  After: {state.post_url}",
        ]
    )

    if result.notes:
        lines.extend(["", f"Notes: {result.notes}"])

    return "\n".join(lines)


# =============================================================================
# Server Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
