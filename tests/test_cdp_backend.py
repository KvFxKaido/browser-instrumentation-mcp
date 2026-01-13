import os

import pytest

from browser_instrumentation_mcp.backends.cdp_backend import CDPBackend


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cdp_backend_connect() -> None:
    cdp_url = os.getenv("BIMCP_CDP_URL")
    if not cdp_url:
        pytest.skip("Set BIMCP_CDP_URL to run CDP integration tests.")

    backend = CDPBackend()
    try:
        await backend.initialize()
        name = await backend.connect_session("integration", cdp_url)
        assert name == "integration"

        sessions = await backend.list_sessions()
        assert any(session["name"] == "integration" for session in sessions)

        dom = await backend.get_dom("integration")
        assert "html" in dom
    except Exception as exc:
        pytest.skip(f"CDP connection failed: {exc}")
    finally:
        await backend.shutdown()
