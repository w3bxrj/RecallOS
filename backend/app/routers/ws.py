import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import app.core.db as db_core
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User
from app.models.job import Job
from app.ws.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/generate/{job_id}")
async def ws_generate(websocket: WebSocket, job_id: int) -> None:
    """Live generation WebSocket endpoint.

    - Validates Origin against ALLOWED_ORIGINS (closes with 4403 on mismatch).
    - Authenticates via ?token= query param BEFORE accept (closes with 4401 on failure).
    - Checks job ownership with a short DB session (closes with 4404 on failure).
    - Registers socket into room FIRST, then delivers snapshot.
    - Replays terminal event (ready or failed) if job already finished.
    - Sends keepalive ping every 25s and handles client disconnects cleanly.
    """
    # 0. Validate Origin header against allowed_origins_list
    origin = websocket.headers.get("origin")
    allowed_origins = settings.allowed_origins_list
    if origin and allowed_origins:
        cleaned_origin = origin.strip().rstrip("/")
        if cleaned_origin not in allowed_origins and "*" not in allowed_origins:
            logger.warning("WS connection rejected: origin '%s' not in allowed origins", origin)
            await websocket.close(code=4403)
            return

    # 1. Authenticate with JWT from ?token= BEFORE accepting
    token = websocket.query_params.get("token")
    if not token:
        logger.debug("WS connection rejected: missing token query param")
        await websocket.close(code=4401)
        return


    try:
        user_id = decode_access_token(token)
    except Exception:
        logger.debug("WS connection rejected: invalid or expired token")
        await websocket.close(code=4401)
        return

    # 2. Check user & job ownership with SHORT DB session
    # Do NOT keep session open across socket lifetime (protects connection pool)
    db = db_core.SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            await websocket.close(code=4401)
            return

        job = db.get(Job, job_id)
        if not job or job.user_id != user.id:
            logger.debug("WS connection rejected: job %d not found or not owned by user %d", job_id, user_id)
            await websocket.close(code=4404)
            return

        snapshot_data = {
            "status": job.status,
            "deck_id": job.deck_id,
            "done_chunks": job.done_chunks,
            "total_chunks": job.total_chunks,
            "cards_created": job.cards_created,
            "error_message": job.error_message,
            "notice": job.notice,
            "is_vision": job.is_vision,
            "vision_mode": job.is_vision,
        }
        job_status = job.status
        deck_id = job.deck_id
        cards_created = job.cards_created
        error_message = job.error_message
    finally:
        db.close()

    # 3. Accept websocket connection
    await websocket.accept()

    # 4. Register socket in room FIRST (so no events are lost)
    room_id = f"job:{job_id}"
    await connection_manager.connect(room_id, websocket)

    # 5. Send snapshot message immediately
    await connection_manager.send_to(
        websocket,
        room_id,
        {"type": "snapshot", "data": snapshot_data},
    )

    # 6. If already ready or failed, replay final event
    if job_status == "ready":
        await connection_manager.send_to(
            websocket,
            room_id,
            {"type": "ready", "data": {"deck_id": deck_id, "cards_created": cards_created}},
        )
    elif job_status == "failed":
        await connection_manager.send_to(
            websocket,
            room_id,
            {"type": "failed", "data": {"message": error_message or "Job failed"}},
        )

    # 7. Start keepalive ping task (every 25s) & client receive loop
    async def keepalive_ping():
        try:
            while True:
                await asyncio.sleep(25.0)
                sent = await connection_manager.send_to(websocket, room_id, {"type": "ping"})
                if not sent:
                    break
        except asyncio.CancelledError:
            pass

    ping_task = asyncio.create_task(keepalive_ping())

    try:
        while True:
            # Ignore client messages; cleanly detect disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WebSocket client disconnected or encountered error: %s", exc)
    finally:
        ping_task.cancel()
        connection_manager.disconnect(room_id, websocket)
