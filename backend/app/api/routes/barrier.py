"""Route d'état de la barrière (dernier état + dernière commande)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.barrier_command import BarrierCommand
from app.models.user import User
from app.schemas.barrier import BarrierCommandRead, BarrierState, BarrierStatus
from app.services import mqtt_handlers

router = APIRouter(prefix="/api/barrier", tags=["barrier"])


@router.get("/state", response_model=BarrierStatus)
async def barrier_state(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BarrierStatus:
    last_command = (
        await session.execute(
            select(BarrierCommand)
            .order_by(BarrierCommand.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    state = None
    if mqtt_handlers.last_barrier_state is not None:
        state = BarrierState(**mqtt_handlers.last_barrier_state)

    return BarrierStatus(
        state=state,
        last_command=BarrierCommandRead.model_validate(last_command)
        if last_command
        else None,
    )
