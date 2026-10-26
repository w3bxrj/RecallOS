import asyncio
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped into rooms.

    Generic implementation reusable across live card generation (rooms "job:{job_id}")
    and quiz duels (rooms "duel:{room_code}").
    Guarantees per-socket send concurrency lock and timeout protection.
    """

    def __init__(self, send_timeout: float = 5.0) -> None:
        self.send_timeout = send_timeout
        self._rooms: Dict[str, Set[WebSocket]] = {}
        self._locks: Dict[WebSocket, asyncio.Lock] = {}

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        """Registers a websocket in a room and initializes its per-socket lock."""
        if room_id not in self._rooms:
            self._rooms[room_id] = set()
        self._rooms[room_id].add(websocket)
        if websocket not in self._locks:
            self._locks[websocket] = asyncio.Lock()
        logger.debug("Socket connected to room %s. Room count: %d", room_id, len(self._rooms[room_id]))

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        """Removes a websocket from a room, cleans up its lock, and prunes empty rooms."""
        if room_id in self._rooms:
            self._rooms[room_id].discard(websocket)
            if not self._rooms[room_id]:
                del self._rooms[room_id]
                logger.debug("Room %s pruned (empty)", room_id)

        # If websocket is in no other rooms, remove its lock
        still_in_use = any(websocket in sockets for sockets in self._rooms.values())
        if not still_in_use and websocket in self._locks:
            del self._locks[websocket]

    async def send_to(self, websocket: WebSocket, room_id: Optional[str], message: Dict[str, Any]) -> bool:
        """Sends a JSON message to a specific socket with per-socket lock and timeout safety.

        Prunes the socket from the room if sending fails or times out.
        """
        lock = self._locks.get(websocket)
        if not lock:
            lock = asyncio.Lock()
            self._locks[websocket] = lock

        try:
            async with lock:
                await asyncio.wait_for(
                    websocket.send_json(message),
                    timeout=self.send_timeout,
                )
            return True
        except asyncio.TimeoutError:
            logger.warning("Send to websocket in room %s timed out after %.1fs", room_id, self.send_timeout)
            if room_id:
                self.disconnect(room_id, websocket)
            return False
        except Exception as exc:
            logger.warning("Failed to send message to websocket in room %s: %s", room_id, exc)
            if room_id:
                self.disconnect(room_id, websocket)
            return False

    async def broadcast(self, room_id: str, message: Dict[str, Any]) -> None:
        """Broadcasts a JSON message to all sockets in a room.

        Never lets one broken or stalled socket break the broadcast to others.
        """
        if room_id not in self._rooms:
            return

        # Shallow copy to avoid mutation during iteration
        sockets = list(self._rooms[room_id])
        for ws in sockets:
            await self.send_to(ws, room_id, message)


connection_manager = ConnectionManager()
