# Phase 4: ConnectionManager & Live Generation WebSocket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the generic `ConnectionManager` and the live generation WebSocket endpoint (`/ws/generate/{job_id}`) with cross-thread event publishing, per-socket concurrency safety, short-lived DB sessions, and comprehensive tests.

**Architecture:** A generic in-memory `ConnectionManager` manages rooms and connections with per-socket `asyncio.Lock` and timeout guards. A `WebSocketJobEventPublisher` bridges background worker threads to the async event loop using `asyncio.run_coroutine_threadsafe`. The WebSocket endpoint authenticates tokens, checks job ownership, registers sockets before sending snapshots, runs keepalive pings, and closes DB sessions before the receive loop.

**Tech Stack:** FastAPI / Starlette WebSockets, Python `asyncio`, SQLAlchemy 2.0, PyJWT, Pytest.

**Spec:** PRD Section 5 & 9.1, and approved Phase 4 design notes.

## Global Constraints

- Never hold database sessions open across the lifetime of a WebSocket. Open short sessions, execute queries, and close them before entering long-running receive loops.
- Use per-socket `asyncio.Lock` and `asyncio.wait_for(..., timeout=5)` for every send. Dead or timed-out sockets must be pruned without failing other room participants.
- In `chunk_done` payloads, strip distractors completely: `new_cards` must contain only `id`, `topic`, `question`, and `answer`.
- The generation pipeline runs safely even with 0 connected sockets; database remains the single source of truth.
- Token query parameter must never be leaked to server logs.
- Conventional commits per task; pytest suite must stay 100% green.

## Review Focus

1. **Dead socket during broadcast:** A broken or stalled client socket in a room does not block other sockets or crash the background task.
2. **Snapshot vs Live Event Race:** Registering before snapshot delivery ensures no live events are dropped, and frontend handles potential duplicates idempotently.
3. **Cross-Thread Dispatch:** Worker thread in `BackgroundTasks` safely schedules broadcasts onto the main asyncio loop via `run_coroutine_threadsafe`.
4. **Distractor Leak Prevention:** Verified by tests that no distractor text ever appears in any WebSocket frame.
5. **Connection Leak on Client Disconnect:** Socket disconnects cleanly release locks and remove empty rooms from the manager.

---

### Task 1: ConnectionManager with Per-Socket Lock & Timeout

**Files:**
- Create: `backend/app/ws/connection_manager.py`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: `ConnectionManager` class with `connect`, `disconnect`, `send_to`, `broadcast`, and global singleton `connection_manager`.

- [ ] **Step 1: Write unit tests for ConnectionManager in `backend/tests/test_ws.py`**
  - Test room creation on connect and deletion on empty.
  - Test `send_to` acquires per-socket lock and times out after 5s if stalled.
  - Test `broadcast` delivers to multiple sockets and automatically prunes failed/dead sockets.

- [ ] **Step 2: Run test to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_connection_manager" -v`
  Expected: FAIL (module not found).

- [ ] **Step 3: Implement `ConnectionManager` in `backend/app/ws/connection_manager.py`**
  - Room dictionary: `_rooms: dict[str, set[WebSocket]] = {}`.
  - Lock dictionary: `_locks: dict[WebSocket, asyncio.Lock] = {}`.
  - Wrap `send_json` with `asyncio.wait_for(..., timeout=5)`.
  - Clean up socket locks and prune empty rooms on disconnect.

- [ ] **Step 4: Run test to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_connection_manager" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git commit -m "feat(ws): implement ConnectionManager with per-socket lock and timeout safety"`

---

### Task 2: Thread-Safe WebSocketJobEventPublisher

**Files:**
- Create: `backend/app/ws/publisher.py`
- Modify: `backend/app/services/events.py`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: `WebSocketJobEventPublisher(JobEventPublisher)` with `set_event_loop(loop)` and thread-safe methods (`chunk_done`, `chunk_failed`, `ready`, `failed`).

- [ ] **Step 1: Write unit tests for WebSocketJobEventPublisher**
  - Test that calling methods from a separate worker thread schedules broadcasts onto the captured loop.
  - Test that `new_cards` in `chunk_done` strips distractors.
  - Test that exceptions during broadcast are caught and logged without raising.

- [ ] **Step 2: Run test to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_publisher" -v`
  Expected: FAIL.

- [ ] **Step 3: Implement `WebSocketJobEventPublisher` in `backend/app/ws/publisher.py`**
  - Capture loop in `set_event_loop`.
  - Format messages as `{"type": str, "data": dict}`.
  - Use `asyncio.run_coroutine_threadsafe(manager.broadcast(f"job:{job_id}", message), self.loop)`.
  - Filter `new_cards` keys to only `{"id", "topic", "question", "answer"}`.

- [ ] **Step 4: Run test to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_publisher" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git commit -m "feat(ws): implement thread-safe WebSocketJobEventPublisher with sanitized cards"`

---

### Task 3: WebSocket Endpoint `/ws/generate/{job_id}`

**Files:**
- Create: `backend/app/routers/ws.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: Endpoint `GET /ws/generate/{job_id}?token=...`.

- [ ] **Step 1: Write integration tests for endpoint connection & auth**
  - Test missing or invalid token closes with code 4401.
  - Test another user's job or non-existent job closes with code 4404.
  - Test snapshot is delivered first upon connection.
  - Test already-ready or already-failed jobs deliver snapshot + final event.

- [ ] **Step 2: Run tests to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_endpoint_auth" -v`
  Expected: FAIL.

- [ ] **Step 3: Implement router in `backend/app/routers/ws.py` and register in `backend/app/main.py`**
  - Query token auth before accept; 4401 on failure.
  - Ownership check; 4404 on mismatch.
  - Open short DB session, read job/user, close session.
  - Register in room FIRST, then send snapshot.
  - Send terminal event if already finished.
  - Run ping loop (every 25s) and ignore client frames.
  - In `finally`, disconnect socket.

- [ ] **Step 4: Run tests to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_endpoint_auth" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git commit -m "feat(ws): implement /ws/generate/{job_id} endpoint with snapshot and auth"`

---

### Task 4: Lifespan Loop Capture & Production Pipeline Wiring

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/generator.py`
- Modify: `backend/app/routers/uploads.py`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Wire `ws_publisher` as active publisher in `main.py` and `uploads.py`.
- Capture running event loop during `lifespan` startup.

- [ ] **Step 1: Write test for end-to-end background task with real BackgroundTasks**
  - Upload document, connect websocket, receive snapshot, `chunk_done`, and `ready` events.
  - Verify card generation completes and distractors never appear in any frame.

- [ ] **Step 2: Run test to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_e2e_live_generation" -v`
  Expected: FAIL.

- [ ] **Step 3: Update `main.py` lifespan and default publisher wiring**
  - In `lifespan`: `ws_publisher.set_event_loop(asyncio.get_running_loop())`.
  - In `generator.py` / `uploads.py`: pass `ws_publisher` to `process_upload_pipeline`.

- [ ] **Step 4: Run test to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_ws.py -k "test_e2e_live_generation" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git commit -m "feat(ws): wire websocket event publisher into generation pipeline and lifespan"`

---

### Task 5: Manual Watcher Script `scripts/ws_watch.py`

**Files:**
- Create: `backend/scripts/ws_watch.py`

- [ ] **Step 1: Implement terminal CLI watcher tool**
  - Accept `job_id`, `--token`, and `--base-url` (or `--email`/`--password` for auto-login).
  - Connect to WebSocket `/ws/generate/{job_id}?token=...`.
  - Format and pretty-print `snapshot`, `chunk_done`, `chunk_failed`, `ready`, and `failed`.
  - Exit gracefully on ready/failed or Ctrl+C.

- [ ] **Step 2: Test script help output**
  Run: `venv\Scripts\python backend/scripts/ws_watch.py --help`
  Expected: Prints clean argument usage.

- [ ] **Step 3: Commit**
  `git commit -m "chore(scripts): add live generation websocket terminal watcher"`

---

### Task 6: Architectural Decisions Log & Query Param Log Security

**Files:**
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Document ADR-011 and ADR-012 in `docs/DECISIONS.md`**
  - ADR-011: Database as Single Source of Truth & WebSockets as Ephemeral Transport.
  - ADR-012: Cross-Thread Broadcasting, Send Safety, and Query Parameter Token Privacy.

- [ ] **Step 2: Commit**
  `git commit -m "docs(decisions): document ADR-011 and ADR-012 for websocket live generation"`

---

### Task 7: Full Suite Verification & Final Check

- [ ] **Step 1: Run complete test suite**
  Run: `venv\Scripts\pytest -v`
  Expected: All 67 existing tests + new Phase 4 tests pass with 0 errors.

- [ ] **Step 2: Verify git status and log**
  Run: `git status` (clean working tree) and `git log -n 10 --oneline`.
