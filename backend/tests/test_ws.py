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
        assert msg["data"]["deck_id"] == deck.id
        assert "vision_mode" in msg["data"]
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


def test_ws_e2e_live_generation_stream(client, db_session, monkeypatch):
    """End-to-end multi-chunk generation streamed live over WebSocket."""
    import threading
    from app.models.job import Job
    from app.models.deck import Deck
    from app.services.generator import run_card_generation
    from app.llm.base import LLMClient

    class MockMultiChunkLLM(LLMClient):
        def __init__(self):
            self.calls = 0

        def generate_cards(self, chunk_text: str) -> list[dict]:
            self.calls += 1
            return [
                {
                    "topic": "OS",
                    "question": f"Question {self.calls}",
                    "answer": f"Answer {self.calls}",
                    "distractors": ["Wrong 1", "Wrong 2", "Wrong 3"],
                }
            ]

    llm = MockMultiChunkLLM()
    user_id, token = create_user_and_token(client, "ws_stream@example.com")

    deck = Deck(user_id=user_id, title="Stream Deck", source_filename="stream.txt", file_hash="hash_stream")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user_id, deck_id=deck.id, status="queued", total_chunks=2)
    db_session.add(job)
    db_session.commit()

    with client.websocket_connect(f"/ws/generate/{job.id}?token={token}") as ws:
        # 1. Snapshot
        msg_snap = ws.receive_json()
        assert msg_snap["type"] == "snapshot"
        assert msg_snap["data"]["status"] == "queued"

        # 2. Trigger worker thread
        thread = threading.Thread(
            target=run_card_generation,
            kwargs={
                "job_id": job.id,
                "user_id": user_id,
                "deck_id": deck.id,
                "chunks": ["Chunk 1 notes", "Chunk 2 notes"],
                "llm_client": llm,
                "delay_between_chunks": 0.05,
            },
        )
        thread.start()

        # 3. Receive chunk 0
        msg_c0 = ws.receive_json()
        assert msg_c0["type"] == "chunk_done"
        assert msg_c0["data"]["chunk_index"] == 0
        assert msg_c0["data"]["total_chunks"] == 2
        assert msg_c0["data"]["cards_created"] == 1
        card0 = msg_c0["data"]["new_cards"][0]
        assert "distractors" not in card0
        assert card0["question"] == "Question 1"

        # 4. Receive chunk 1
        msg_c1 = ws.receive_json()
        assert msg_c1["type"] == "chunk_done"
        assert msg_c1["data"]["chunk_index"] == 1
        assert msg_c1["data"]["cards_created"] == 2

        # 5. Receive ready
        msg_ready = ws.receive_json()
        assert msg_ready["type"] == "ready"
        assert msg_ready["data"]["deck_id"] == deck.id
        assert msg_ready["data"]["cards_created"] == 2

        thread.join()


def test_ws_partial_chunk_failure_continues(client, db_session):
    """When a chunk produces no valid cards, chunk_failed is broadcast and job still completes."""
    import threading
    from app.models.job import Job
    from app.models.deck import Deck
    from app.services.generator import run_card_generation
    from app.llm.base import LLMClient

    class MockPartialFailureLLM(LLMClient):
        def __init__(self):
            self.calls = 0

        def generate_cards(self, chunk_text: str) -> list[dict]:
            self.calls += 1
            if self.calls == 1:
                return []  # chunk 0 fails to produce cards
            return [
                {
                    "topic": "Networking",
                    "question": "What is TCP?",
                    "answer": "A reliable connection-oriented transport protocol",
                    "distractors": ["UDP", "IP", "ICMP"],
                }
            ]

    llm = MockPartialFailureLLM()
    user_id, token = create_user_and_token(client, "ws_partial@example.com")

    deck = Deck(user_id=user_id, title="Partial Deck", source_filename="partial.txt", file_hash="hash_partial")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user_id, deck_id=deck.id, status="queued", total_chunks=2)
    db_session.add(job)
    db_session.commit()

    with client.websocket_connect(f"/ws/generate/{job.id}?token={token}") as ws:
        msg_snap = ws.receive_json()
        assert msg_snap["type"] == "snapshot"

        thread = threading.Thread(
            target=run_card_generation,
            kwargs={
                "job_id": job.id,
                "user_id": user_id,
                "deck_id": deck.id,
                "chunks": ["Fail chunk", "Success chunk"],
                "llm_client": llm,
                "delay_between_chunks": 0.05,
            },
        )
        thread.start()

        # Chunk 0 failed
        msg_c0 = ws.receive_json()
        assert msg_c0["type"] == "chunk_failed"
        assert msg_c0["data"]["chunk_index"] == 0

        # Chunk 1 done
        msg_c1 = ws.receive_json()
        assert msg_c1["type"] == "chunk_done"
        assert msg_c1["data"]["chunk_index"] == 1
        assert msg_c1["data"]["cards_created"] == 1
        assert "distractors" not in msg_c1["data"]["new_cards"][0]

        # Ready
        msg_ready = ws.receive_json()
        assert msg_ready["type"] == "ready"
        assert msg_ready["data"]["cards_created"] == 1

        thread.join()


def test_ws_real_background_tasks_upload(client, monkeypatch):
    """Proves the real BackgroundTasks pipeline execution path broadcasts events."""
    from app.llm.base import LLMClient

    class MockLLM(LLMClient):
        def generate_cards(self, chunk_text: str) -> list[dict]:
            return [
                {
                    "topic": "Algorithms",
                    "question": "What is Dijkstra's algorithm?",
                    "answer": "Single-source shortest path algorithm on non-negative weighted graphs",
                    "distractors": ["DFS", "BFS", "Kruskal's"],
                }
            ]

    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLM())
    _, token = create_user_and_token(client, "ws_bg_tasks@example.com")

    content = ("Shortest path algorithms in computer science graph theory.\n\n" * 8).encode("utf-8")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("dijkstra.txt", content, "text/plain")},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    deck_id = res.json()["deck_id"]

    # Connect to the finished job -> proves snapshot + replay
    with client.websocket_connect(f"/ws/generate/{job_id}?token={token}") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "snapshot"
        assert msg1["data"]["status"] == "ready"

        msg2 = ws.receive_json()
        assert msg2["type"] == "ready"
        assert msg2["data"]["deck_id"] == deck_id
        assert msg2["data"]["cards_created"] >= 1


def test_job_status_and_snapshot_include_deck_id_and_vision_mode(client, db_session):
    """Verifies that GET /api/jobs/{id} and websocket snapshot include deck_id and vision_mode."""
    from app.models.deck import Deck
    from app.models.job import Job
    user_id, token = create_user_and_token(client, "snapshot_keys@example.com")
    deck = Deck(user_id=user_id, title="Test Deck", source_filename="test.txt", file_hash="hash_snap_test")
    db_session.add(deck)
    db_session.flush()

    job = Job(
        user_id=user_id,
        deck_id=deck.id,
        status="ready",
        total_chunks=3,
        done_chunks=3,
        cards_created=10,
        is_vision=True,
    )
    db_session.add(job)
    db_session.commit()

    # REST check: GET /api/jobs/{id}
    res = client.get(f"/api/jobs/{job.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["deck_id"] == deck.id
    assert data["vision_mode"] is True
    assert data["is_vision"] is True

    # WebSocket check: initial snapshot
    with client.websocket_connect(f"/ws/generate/{job.id}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["data"]["deck_id"] == deck.id
        assert msg["data"]["vision_mode"] is True
        assert msg["data"]["is_vision"] is True



