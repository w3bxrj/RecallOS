import asyncio
import pytest
from unittest.mock import AsyncMock

from app.ws.connection_manager import ConnectionManager


@pytest.mark.anyio
async def test_connection_manager_connect_and_disconnect():
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect("job:1", ws1)
    await manager.connect("job:1", ws2)

    assert "job:1" in manager._rooms
    assert len(manager._rooms["job:1"]) == 2
    assert ws1 in manager._locks
    assert ws2 in manager._locks

    manager.disconnect("job:1", ws1)
    assert len(manager._rooms["job:1"]) == 1
    assert ws1 not in manager._locks

    manager.disconnect("job:1", ws2)
    # Room deleted when empty
    assert "job:1" not in manager._rooms
    assert ws2 not in manager._locks


@pytest.mark.anyio
async def test_connection_manager_send_to_timeout():
    manager = ConnectionManager(send_timeout=0.1)
    ws = AsyncMock()

    async def slow_send(msg):
        await asyncio.sleep(0.5)

    ws.send_json.side_effect = slow_send
    await manager.connect("job:2", ws)

    success = await manager.send_to(ws, "job:2", {"type": "ping"})
    assert success is False
    # Dead socket should be pruned
    assert "job:2" not in manager._rooms
    assert ws not in manager._locks


@pytest.mark.anyio
async def test_connection_manager_broadcast_resilience():
    manager = ConnectionManager()
    good_ws = AsyncMock()
    bad_ws = AsyncMock()

    bad_ws.send_json.side_effect = RuntimeError("Socket broken")

    await manager.connect("job:3", good_ws)
    await manager.connect("job:3", bad_ws)

    await manager.broadcast("job:3", {"type": "test"})

    good_ws.send_json.assert_awaited_once_with({"type": "test"})
    # bad_ws removed from room
    assert bad_ws not in manager._rooms.get("job:3", set())
    assert good_ws in manager._rooms["job:3"]
