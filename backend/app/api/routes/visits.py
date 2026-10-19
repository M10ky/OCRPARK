"""Routes pour les visites (entrée/sortie) du parking."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.models.visit import VISIT_STATUS_INSIDE, Visit
from app.schemas.visits import VisitRead
from app.services.ocr_client import normalize_plate

router = APIRouter(prefix="/api/visits", tags=["visits"])


@router.get("", response_model=list[VisitRead])
async def list_visits(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None, description="`inside` ou `closed`."),
    plate: str | None = None,
    date_from: datetime | None = Query(
        default=None, description="Bornes inclusives sur entry_at (ISO 8601)."
    ),
    date_to: datetime | None = Query(
        default=None, description="Borne haute inclusive sur entry_at (ISO 8601)."
    ),
) -> list[VisitRead]:
    # Filtres cumulatifs (AND), puis tri/pagination.
    stmt = select(Visit)
    if status:
        stmt = stmt.where(Visit.status == status)
    if plate:
        stmt = stmt.where(Visit.plate == normalize_plate(plate))
    if date_from is not None:
        stmt = stmt.where(Visit.entry_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Visit.entry_at <= date_to)
    stmt = stmt.order_by(Visit.entry_at.desc()).offset(offset).limit(limit)

    items = (await session.execute(stmt)).scalars().all()
    return [VisitRead.model_validate(v) for v in items]


@router.get("/current", response_model=list[VisitRead])
async def list_current_visits(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VisitRead]:
    stmt = (
        select(Visit)
        .where(Visit.status == VISIT_STATUS_INSIDE)
        .order_by(Visit.entry_at)
    )
    items = (await session.execute(stmt)).scalars().all()
    return [VisitRead.model_validate(v) for v in items]
