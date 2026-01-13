import pytest


@pytest.mark.asyncio
async def test_create_and_destroy_session(manager, fake_storage) -> None:
    name = await manager.create_session("alpha")
    assert name == "alpha"
    assert fake_storage.saved

    destroyed = await manager.destroy_session("alpha")
    assert destroyed is True
    assert "alpha" in fake_storage.deleted


@pytest.mark.asyncio
async def test_connect_session_routes_to_cdp(manager) -> None:
    name = await manager.connect_session("remote", "ws://localhost:9222")
    assert name == "remote"
    assert manager.get_event_log("remote").session == "remote"


@pytest.mark.asyncio
async def test_escalation_and_actions(manager) -> None:
    await manager.create_session("alpha")

    escalated = await manager.escalate_session("alpha", "need to click")
    assert escalated["escalated"] is True
    assert await manager.is_escalated("alpha") is True

    result = await manager.click("alpha", "#btn", reason="testing")
    assert result.action == "click"


@pytest.mark.asyncio
async def test_list_sessions_tracks_backends(manager, fake_backend, fake_cdp_backend) -> None:
    await fake_backend.create_session("local")
    await fake_cdp_backend.create_session("remote")
    manager._cdp_initialized = True

    sessions = await manager.list_sessions()
    names = {session["name"] for session in sessions}
    assert names == {"local", "remote"}


@pytest.mark.asyncio
async def test_resolve_backend_missing(manager) -> None:
    with pytest.raises(ValueError):
        await manager.is_escalated("missing")
