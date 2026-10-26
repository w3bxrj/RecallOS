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


@pytest.mark.anyio
async def test_publisher_sanitizes_distractors():
    from app.ws.publisher import WebSocketJobEventPublisher

    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect("job:10", ws)

    loop = asyncio.get_running_loop()
    publisher = WebSocketJobEventPublisher(manager=manager)
    publisher.set_event_loop(loop)

    raw_cards = [
        {
            "id": 1,
            "topic": "OS",
            "question": "What is a kernel?",
            "answer": "Core of the OS",
            "distractors": ["Hardware", "A browser", "A compiler"],
        }
    ]

    publisher.chunk_done(
        job_id=10,
        chunk_index=0,
        total_chunks=1,
        new_cards=raw_cards,
        cards_created=1,
    )

    # Let the scheduled coroutine run on loop
    await asyncio.sleep(0.05)

    ws.send_json.assert_awaited_once()
    call_arg = ws.send_json.call_args[0][0]
    assert call_arg["type"] == "chunk_done"
    sent_card = call_arg["data"]["new_cards"][0]
    assert "distractors" not in sent_card
    assert sent_card["topic"] == "OS"
    assert sent_card["question"] == "What is a kernel?"
    assert sent_card["answer"] == "Core of the OS"


@pytest.mark.anyio
async def test_publisher_no_loop_graceful_noop():
    from app.ws.publisher import WebSocketJobEventPublisher

    publisher = WebSocketJobEventPublisher()
    # No loop set; should execute without error
    publisher.chunk_done(1, 0, 1, [], 0)
    publisher.chunk_failed(1, 0, "error")
    publisher.ready(1, 1, 1)
    publisher.failed(1, "failed")


@pytest.mark.anyio
async def test_publisher_thread_safe_cross_thread():
    from app.ws.publisher import WebSocketJobEventPublisher
    import threading

    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect("job:99", ws)

    loop = asyncio.get_running_loop()
    publisher = WebSocketJobEventPublisher(manager=manager)
    publisher.set_event_loop(loop)

    def worker_thread():
        publisher.chunk_failed(99, 1, "test error from thread")

    thread = threading.Thread(target=worker_thread)
    thread.start()
    thread.join()

    await asyncio.sleep(0.05)
    ws.send_json.assert_awaited_once_with({
        "type": "chunk_failed",
        "data": {
            "chunk_index": 1,
            "reason": "test error from thread",
        },
    })

