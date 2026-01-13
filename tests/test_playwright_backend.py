import pytest

from browser_instrumentation_mcp.backends.playwright_backend import PlaywrightBackend


@pytest.mark.asyncio
@pytest.mark.integration
async def test_playwright_backend_basic() -> None:
    backend = PlaywrightBackend()
    try:
        await backend.initialize()
    except Exception as exc:
        pytest.skip(f"Playwright not available: {exc}")

    try:
        name = await backend.create_session("integration")
        assert name == "integration"

        sessions = await backend.list_sessions()
        assert any(session["name"] == "integration" for session in sessions)

        dom = await backend.get_dom("integration")
        assert "html" in dom

        screenshot = await backend.screenshot("integration")
        assert isinstance(screenshot, bytes)
    finally:
        await backend.shutdown()
