# Browser Instrumentation MCP Server

## Tool Usage Guidance

**Prefer `browser_inspect_*` tools.**

Use `browser_act_*` tools only when observation is insufficient.

Always explain why action is necessary before escalating.

## Tool Categories

### INSPECT Tools (Default, Safe)

These tools observe without side effects. Use freely:

- `browser_session_create` - Start a session
- `browser_session_list` - Check session status
- `browser_inspect_navigate` - Go to a URL
- `browser_inspect_screenshot` - Capture what you see
- `browser_inspect_dom` - Read HTML structure
- `browser_inspect_text` - Read text content
- `browser_inspect_console` - Check for errors
- `browser_inspect_network` - See what loaded
- `browser_inspect_events` - Audit session history

### ACT Tools (Require Justification)

These tools cause side effects. Before using:

1. Exhaust observation options first
2. Escalate the session with `browser_session_escalate`
3. Provide a clear reason for each action

ACT tools:
- `browser_act_click` - Click element
- `browser_act_type` - Type into input
- `browser_act_execute` - Run JavaScript

## Workflow Pattern

```
1. Create session (observation-only)
2. Navigate to target
3. Observe: screenshot, text, DOM, network
4. If action needed:
   a. Escalate with reason
   b. Perform action with reason
   c. Observe result (NOT success/failure)
5. Check event log for audit
6. Destroy session
```

## Important Behaviors

### Actions Don't Return Success

ACT tools return **observed changes**, not success/failure:

```
Confidence: medium
Observed Changes:
  URL changed: true
  Network requests: 3
```

This is intentional. Browsers are non-deterministic.

### Sessions Start Locked

New sessions cannot use ACT tools. You must:
1. Call `browser_session_escalate` with a reason
2. The reason is logged permanently

### Everything is Logged

All tool calls are recorded in the session event log.
Use `browser_inspect_events` to see what happened.

## When to Avoid Browser Tools

- Form filling for real accounts
- Login automation
- Payment flows
- Anything requiring reliability

For these, the user should use Playwright directly.
