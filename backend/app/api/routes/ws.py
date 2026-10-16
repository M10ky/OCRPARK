"""Route WebSocket pour événements temps réel."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    # Authentification optionnelle via token query (simple pour intégration)
    if token:
        username = decode_access_token(token)
        if not username:
            await websocket.close(code=4401)
            return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
