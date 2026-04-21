"""Tests for WebSocket ConnectionManager."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.presentation.api.ws_manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


def _mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_accepts_websocket(manager):
    ws = _mock_ws()
    await manager.connect(1, ws)
    ws.accept.assert_awaited_once()
    assert manager.has_connections(1)


@pytest.mark.asyncio
async def test_disconnect_removes_websocket(manager):
    ws = _mock_ws()
    await manager.connect(1, ws)
    manager.disconnect(1, ws)
    assert not manager.has_connections(1)


@pytest.mark.asyncio
async def test_disconnect_unknown_user(manager):
    ws = _mock_ws()
    manager.disconnect(999, ws)  # should not raise
    assert not manager.has_connections(999)


@pytest.mark.asyncio
async def test_send_to_user(manager):
    ws = _mock_ws()
    await manager.connect(1, ws)
    await manager.send_to_user(1, {"type": "test"})
    ws.send_json.assert_awaited_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_send_to_user_no_connections(manager):
    await manager.send_to_user(999, {"type": "test"})  # should not raise


@pytest.mark.asyncio
async def test_send_removes_dead_connections(manager):
    ws_alive = _mock_ws()
    ws_dead = _mock_ws()
    ws_dead.send_json.side_effect = Exception("connection closed")

    await manager.connect(1, ws_alive)
    await manager.connect(1, ws_dead)

    await manager.send_to_user(1, {"msg": "hi"})

    ws_alive.send_json.assert_awaited_once()
    assert manager.has_connections(1)


@pytest.mark.asyncio
async def test_multiple_users(manager):
    ws1 = _mock_ws()
    ws2 = _mock_ws()
    await manager.connect(1, ws1)
    await manager.connect(2, ws2)

    await manager.send_to_user(1, {"for": "user1"})
    ws1.send_json.assert_awaited_once_with({"for": "user1"})
    ws2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_has_connections_false_initially(manager):
    assert not manager.has_connections(1)


@pytest.mark.asyncio
async def test_all_dead_connections_cleanup(manager):
    ws = _mock_ws()
    ws.send_json.side_effect = Exception("dead")
    await manager.connect(1, ws)

    await manager.send_to_user(1, {"msg": "hi"})
    assert not manager.has_connections(1)
