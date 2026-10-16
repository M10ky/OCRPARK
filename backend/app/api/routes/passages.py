"""Routes pour historique des passages."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.passage import Passage
from app.models.user import User
from app.schemas.passages import PassageRead, PassageStats
from app.services.ocr_client import normalize_plate

router = APIRouter(prefix="/api/passages", tags=["passages"])


@router.get("", response_model=list[PassageRead])
async def list_passages(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    plate: str | None = None,
    source: str | None = None,
    allowed: bool | None = None,
    date_from: datetime | None = Query(
        default=None, description="Bornes inclusives sur created_at (ISO 8601)."
    ),
    date_to: datetime | None = Query(
        default=None, description="Borne haute inclusive sur created_at (ISO 8601)."
    ),
) -> list[PassageRead]:
    # Une seule construction : les filtres se CUMULENT (AND), puis tri/pagination.
    stmt = select(Passage)
    if plate:
        stmt = stmt.where(Passage.plate == normalize_plate(plate))
    if source:
        stmt = stmt.where(Passage.source == source)
    if allowed is not None:
        stmt = stmt.where(Passage.allowed == allowed)
    if date_from is not None:
        stmt = stmt.where(Passage.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Passage.created_at <= date_to)
    stmt = stmt.order_by(Passage.created_at.desc()).offset(offset).limit(limit)

    result = await session.execute(stmt)
    items = result.scalars().all()
    return [PassageRead.model_validate(i) for i in items]


@router.get("/stats", response_model=PassageStats)
async def stats_passages(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PassageStats:
    # Une seule requête avec agrégats conditionnels (COUNT FILTER).
    stmt = select(
        func.count(Passage.id),
        func.count(Passage.id).filter(Passage.allowed.is_(True)),
        func.count(Passage.id).filter(Passage.allowed.is_(False)),
        func.count(Passage.id).filter(Passage.recognized.is_(True)),
        func.count(Passage.id).filter(Passage.recognized.is_(False)),
    )
    total, authorized, denied, recognized, unrecognized = (await session.execute(stmt)).one()
    return PassageStats(
        total=total or 0,
        authorized=authorized or 0,
        denied=denied or 0,
        recognized=recognized or 0,
        unrecognized=unrecognized or 0,
    )
