"""Routes pour l'occupation des places de parking."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.parking_slot import ParkingSlot
from app.models.user import User
from app.schemas.slots import ParkingSlotRead, ParkingSlotsSummary

router = APIRouter(prefix="/api/slots", tags=["slots"])


@router.get("", response_model=ParkingSlotsSummary)
async def list_slots(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ParkingSlotsSummary:
    rows = (
        await session.execute(select(ParkingSlot).order_by(ParkingSlot.id))
    ).scalars().all()
    slots = [ParkingSlotRead.model_validate(s) for s in rows]
    occupied = sum(1 for s in slots if s.occupied)
    return ParkingSlotsSummary(
        slots=slots,
        total=len(slots),
        occupied=occupied,
        free=len(slots) - occupied,
    )
