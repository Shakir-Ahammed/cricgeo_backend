"""
WebSocket ConnectionManager for CricGeo backend.
Manages room-based broadcasting for live match scoring.

Room naming convention:
  match:{match_id}   — live scoring clients (authenticated or anonymous)
  obs:{match_id}     — OBS overlay clients (token-authenticated, no JWT)
"""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Room-based WebSocket connection manager.

    All mutations to `rooms` are protected by an asyncio.Lock to prevent
    race conditions when multiple coroutines connect/disconnect concurrently.

    Usage:
        # Connect
        await manager.connect(ws, room="match:42")

        # Broadcast to all clients in a room
        await manager.broadcast("match:42", {"event": "ball_scored", ...})

        # Disconnect on client leave
        await manager.disconnect(ws, room="match:42")
    """

    def __init__(self) -> None:
        # room_id → set of active WebSocket connections
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, room: str) -> None:
        """
        Accept the WebSocket handshake and register it in the given room.
        Must be called before any send/broadcast on this connection.
        """
        await ws.accept()
        async with self._lock:
            self.rooms[room].add(ws)
        logger.debug("WS connected: room=%s total=%d", room, len(self.rooms[room]))

    async def disconnect(self, ws: WebSocket, room: str) -> None:
        """
        Remove a WebSocket from the given room.
        Safe to call even if the connection is not in the room (no-op).
        Does NOT close the underlying connection — caller is responsible.
        """
        async with self._lock:
            self.rooms[room].discard(ws)
            # Clean up empty room entries to avoid unbounded dict growth
            if not self.rooms[room]:
                del self.rooms[room]
        logger.debug("WS disconnected: room=%s", room)

    async def broadcast(self, room: str, payload: dict) -> None:
        """
        Send a JSON payload to every active connection in the room.
        Dead connections (already closed) are silently removed from the room.
        Never raises — failed sends are logged at debug level.
        """
        async with self._lock:
            connections = set(self.rooms.get(room, set()))

        dead: list[WebSocket] = []

        for ws in connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(payload)
                else:
                    dead.append(ws)
            except WebSocketDisconnect:
                dead.append(ws)
            except RuntimeError:
                # send_json on a closed socket raises RuntimeError in some ASGI servers
                dead.append(ws)
            except Exception as exc:
                logger.debug("WS broadcast error (room=%s): %s", room, exc)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self.rooms[room].discard(ws)
                if room in self.rooms and not self.rooms[room]:
                    del self.rooms[room]

    async def send_personal(self, ws: WebSocket, payload: dict) -> None:
        """
        Send a JSON payload to a single WebSocket connection.
        Raises WebSocketDisconnect if the connection is already closed.
        """
        await ws.send_json(payload)

    def room_size(self, room: str) -> int:
        """Return the number of active connections in a room."""
        return len(self.rooms.get(room, set()))


# Module-level singleton — import this everywhere, never instantiate a new one
manager = ConnectionManager()
