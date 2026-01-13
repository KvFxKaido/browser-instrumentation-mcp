# Browser Instrumentation MCP Server

A Model Context Protocol (MCP) server for browser **instrumentation** using Playwright. Prioritizes observation over action.

> **This server does not attempt to make browser automation reliable.**
> Browsers are non-deterministic systems. This server prioritizes visibility over convenience.

## Philosophy

This server is designed around one principle: **observation first, action second**.

- **INSPECT tools** (7 tools) - Safe, encouraged, no side effects
- **ACT tools** (3 tools) - Dangerous, require escalation and justification, logged

Actions don't return success/failure. They return **what was observed** with a confidence level.

## When NOT to Use This

- Form filling
- Login automation
- Payment flows
- Anything you wouldn't trust a flaky intern to do
- Any scenario requiring reliable, repeatable automation

If you need reliable automation, use Playwright directly with proper test infrastructure.

## Installation

### Prerequisites

- Python 3.11 or later
- Playwright browsers installed

### Install from source

```bash
git clone https://github.com/yourusername/browser-instrumentation-mcp.git
cd browser-instrumentation-mcp
pip install -e .
playwright install chromium
```

## Configuration

### Claude Desktop

Add to your Claude Desktop configuration:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "browser": {
      "command": "python",
      "args": ["-m", "browser_instrumentation_mcp.server"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add browser -- python -m browser_instrumentation_mcp.server
```

## Available Tools

### Session Management

| Tool | Description |
|------|-------------|
| `browser_session_create` | Create a new session (observation-only mode) |
| `browser_session_list` | List sessions with status and event count |
| `browser_session_destroy` | Clean up session |
| `browser_session_escalate` | Enable actions (requires reason) |

### INSPECT Tools (Safe)

| Tool | Description |
|------|-------------|
| `browser_inspect_navigate` | Navigate to URL |
| `browser_inspect_screenshot` | Capture page screenshot |
| `browser_inspect_dom` | Get HTML content |
| `browser_inspect_text` | Get text content (no HTML) |
| `browser_inspect_console` | Get console log messages |
| `browser_inspect_network` | Get network requests |
| `browser_inspect_events` | Get session event log |

### ACT Tools (Require Escalation)

| Tool | Description |
|------|-------------|
| `browser_act_click` | Click element (requires reason) |
| `browser_act_type` | Type into input (requires reason) |
| `browser_act_execute` | Execute JavaScript (requires reason) |

## Usage Examples

### Observation workflow (typical)

```
1. browser_session_create(name="research")
2. browser_inspect_navigate(session="research", url="example.com")
3. browser_inspect_screenshot(session="research")
4. browser_inspect_text(session="research")
5. browser_inspect_events(session="research")  # audit what happened
6. browser_session_destroy(name="research")
```

### Action workflow (when observation isn't enough)

```
1. browser_session_create(name="test")
2. browser_inspect_navigate(session="test", url="example.com")
3. browser_session_escalate(name="test", reason="need to test form submission")
4. browser_act_click(session="test", selector="button", reason="testing submit button")
   # Returns observed changes, NOT success/failure
5. browser_inspect_events(session="test")  # see what was logged
6. browser_session_destroy(name="test")
```

### Action result format

ACT tools return observed changes, not success/failure:

```
Action: click
Confidence: medium

Observed Changes:
  URL changed: true
  Network requests: 3
  Console messages: 0
  New URL: https://example.com/submitted

State:
  Before: https://example.com/form
  After: https://example.com/submitted
```

## Event Log

Every session maintains an append-only event log. Use `browser_inspect_events` to audit what happened:

```json
[
  {"event_type": "session_created", "timestamp": "...", "details": {...}},
  {"event_type": "navigate", "timestamp": "...", "details": {"url": "..."}},
  {"event_type": "session_escalated", "reason": "testing form", ...},
  {"event_type": "click", "reason": "submit button", "details": {...}}
]
```

## Architecture

```
browser_instrumentation_mcp/
├── server.py           # FastMCP server with INSPECT/ACT tools
├── browser_manager.py  # Session lifecycle management
├── models.py           # Pydantic models (EventLog, ActionResult, etc.)
├── backends/
│   ├── base.py         # Abstract backend interface
│   └── playwright_backend.py  # Playwright implementation
```

## Development

```bash
git clone https://github.com/yourusername/browser-instrumentation-mcp.git
cd browser-instrumentation-mcp
pip install -e .
playwright install chromium

# Run directly
python -m browser_instrumentation_mcp.server
```

## License

MIT
