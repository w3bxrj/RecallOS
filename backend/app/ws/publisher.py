import asyncio
import logging
from typing import List, Dict, Any, Optional

from app.services.events import JobEventPublisher
from app.ws.connection_manager import ConnectionManager, connection_manager

logger = logging.getLogger(__name__)


class WebSocketJobEventPublisher(JobEventPublisher):
    """Thread-safe event publisher broadcasting generation updates over WebSockets.

    Dispatches coroutines from worker threads onto the captured main event loop.
    Guarantees:
    - Never throws an exception to caller (protecting background jobs).
    - Strips distractors from card payloads (security).
    """

    def __init__(self, manager: Optional[ConnectionManager] = None) -> None:
        self.manager = manager or connection_manager
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Captures the running asyncio event loop, called during app lifespan startup."""
        self.loop = loop
        logger.info("WebSocketJobEventPublisher bound to event loop: %s", loop)

    def _broadcast_threadsafe(self, job_id: int, message: Dict[str, Any]) -> None:
        """Schedules broadcast on the main event loop from any thread."""
        try:
            if self.loop is None or self.loop.is_closed():
                logger.debug("No active event loop bound to publisher; dropping event for job %d", job_id)
                return

            room_id = f"job:{job_id}"
            coro = self.manager.broadcast(room_id, message)
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        except Exception as exc:
            logger.warning("Error scheduling WebSocket broadcast for job %d: %s", job_id, exc)

    def chunk_done(
        self,
        job_id: int,
        chunk_index: int,
        total_chunks: int,
        new_cards: List[Dict[str, Any]],
        cards_created: int,
        page_range: Optional[str] = None,
    ) -> None:
        """Broadcasts chunk_done event with sanitized cards (NO distractors)."""
        try:
            sanitized_cards = []
            for c in new_cards:
                card_data = {
                    "id": c.get("id"),
                    "topic": c.get("topic", ""),
                    "question": c.get("question", ""),
                    "answer": c.get("answer", ""),
                }
                sanitized_cards.append(card_data)

            payload_data: Dict[str, Any] = {
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "new_cards": sanitized_cards,
                "cards_created": cards_created,
            }
            if page_range:
                payload_data["page_range"] = page_range

            payload = {
                "type": "chunk_done",
                "data": payload_data,
            }
            self._broadcast_threadsafe(job_id, payload)
        except Exception as exc:
            logger.warning("Failed in chunk_done publisher for job %d: %s", job_id, exc)

    def chunk_failed(
        self,
        job_id: int,
        chunk_index: int,
        reason: str,
    ) -> None:
        """Broadcasts chunk_failed event."""
        try:
            payload = {
                "type": "chunk_failed",
                "data": {
                    "chunk_index": chunk_index,
                    "reason": reason,
                },
            }
            self._broadcast_threadsafe(job_id, payload)
        except Exception as exc:
            logger.warning("Failed in chunk_failed publisher for job %d: %s", job_id, exc)

    def ready(
        self,
        job_id: int,
        deck_id: int,
        cards_created: int,
    ) -> None:
        """Broadcasts ready event."""
        try:
            payload = {
                "type": "ready",
                "data": {
                    "deck_id": deck_id,
                    "cards_created": cards_created,
                },
            }
            self._broadcast_threadsafe(job_id, payload)
        except Exception as exc:
            logger.warning("Failed in ready publisher for job %d: %s", job_id, exc)

    def failed(
        self,
        job_id: int,
        message: str,
    ) -> None:
        """Broadcasts failed event."""
        try:
            payload = {
                "type": "failed",
                "data": {
                    "message": message,
                },
            }
            self._broadcast_threadsafe(job_id, payload)
        except Exception as exc:
            logger.warning("Failed in failed publisher for job %d: %s", job_id, exc)


ws_publisher = WebSocketJobEventPublisher()
