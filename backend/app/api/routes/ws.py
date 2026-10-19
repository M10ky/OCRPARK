"""Route WebSocket pour événements temps réel."""
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])
settings = get_settings()


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Événements temps réel (passages, état barrière/MQTT).

    Authentification : un token (`?token=<JWT>`) est vérifié s'il est fourni.
    S'il est absent, la connexion est acceptée uniquement si
    `WS_REQUIRE_AUTH=false` (défaut dev). En production, positionner
    `WS_REQUIRE_AUTH=true` pour exiger un token valide.
    """
    # Fermer AVANT accept() déclenche un refus HTTP 403 (pas de close frame) ;
    # on accepte donc brièvement pour pouvoir renvoyer le code applicatif 4401.
    if token:
        username = decode_access_token(token)
        if not username:
            await websocket.accept()
            await websocket.close(code=4401)
            return
    elif settings.WS_REQUIRE_AUTH:
        await websocket.accept()
        await websocket.close(code=4401)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
