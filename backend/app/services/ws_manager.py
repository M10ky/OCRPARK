"""Gestionnaire WebSocket pour événements temps réel."""
import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self.active_connections)
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                try:
                    await connection.close()
                except Exception:
                    pass
                async with self._lock:
                    if connection in self.active_connections:
                        self.active_connections.remove(connection)


manager = ConnectionManager()
