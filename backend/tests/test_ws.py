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


def create_user_and_token(client, email: str) -> tuple[int, str]:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": "WS User"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    return reg.json()["id"], login.json()["access_token"]


def test_ws_endpoint_invalid_token(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    # Missing token -> 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/generate/1"):
            pass
    assert exc.value.code == 4401

    # Invalid token -> 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/generate/1?token=badtoken"):
            pass
    assert exc.value.code == 4401


def test_ws_endpoint_ownership_check_4404(client, db_session):
    from starlette.websockets import WebSocketDisconnect
    from app.models.job import Job
    from app.models.deck import Deck

    user_a_id, token_a = create_user_and_token(client, "ws_a@example.com")
    user_b_id, token_b = create_user_and_token(client, "ws_b@example.com")

    deck = Deck(user_id=user_a_id, title="Deck A", source_filename="a.txt", file_hash="hash_a")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user_a_id, deck_id=deck.id, status="queued")
    db_session.add(job)
    db_session.commit()

    # User B tries to connect to User A's job -> 4404
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/generate/{job.id}?token={token_b}"):
            pass
    assert exc.value.code == 4404

    # Non-existent job -> 4404
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/generate/999999?token={token_a}"):
            pass
    assert exc.value.code == 4404


def test_ws_endpoint_snapshot_and_terminal_events(client, db_session):
    from app.models.job import Job
    from app.models.deck import Deck

    user_id, token = create_user_and_token(client, "ws_snapshot@example.com")

    # 1. Queued job gives snapshot
    deck = Deck(user_id=user_id, title="Deck Q", source_filename="q.txt", file_hash="hash_q")
    db_session.add(deck)
    db_session.flush()

    job_q = Job(user_id=user_id, deck_id=deck.id, status="queued", total_chunks=5, done_chunks=1, cards_created=3)
    db_session.add(job_q)
    db_session.commit()

    with client.websocket_connect(f"/ws/generate/{job_q.id}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["data"]["status"] == "queued"
        assert msg["data"]["done_chunks"] == 1
        assert msg["data"]["total_chunks"] == 5
        assert msg["data"]["cards_created"] == 3

    # 2. Ready job gives snapshot + ready
    job_ready = Job(user_id=user_id, deck_id=deck.id, status="ready", total_chunks=2, done_chunks=2, cards_created=6)
    db_session.add(job_ready)
    db_session.commit()

    with client.websocket_connect(f"/ws/generate/{job_ready.id}?token={token}") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "snapshot"
        assert msg1["data"]["status"] == "ready"

        msg2 = ws.receive_json()
        assert msg2["type"] == "ready"
        assert msg2["data"]["deck_id"] == deck.id
        assert msg2["data"]["cards_created"] == 6

    # 3. Failed job gives snapshot + failed
    job_failed = Job(user_id=user_id, deck_id=deck.id, status="failed", error_message="Extraction error")
    db_session.add(job_failed)
    db_session.commit()

    with client.websocket_connect(f"/ws/generate/{job_failed.id}?token={token}") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "snapshot"
        assert msg1["data"]["status"] == "failed"

        msg2 = ws.receive_json()
        assert msg2["type"] == "failed"
        assert msg2["data"]["message"] == "Extraction error"


