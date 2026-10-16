"""Routes pour historique des passages."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.passage import Passage
from app.models.user import User
from app.schemas.passages import PassageRead, PassageStats

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
) -> list[PassageRead]:
    stmt = select(Passage).order_by(Passage.created_at.desc()).offset(offset).limit(limit)
    if plate:
        from app.services.ocr_client import normalize_plate

        stmt = select(Passage).where(Passage.plate == normalize_plate(plate)).order_by(Passage.created_at.desc()).offset(offset).limit(limit)
    if source:
        stmt = select(Passage).where(Passage.source == source).order_by(Passage.created_at.desc()).offset(offset).limit(limit)
    if allowed is not None:
        stmt = select(Passage).where(Passage.allowed == allowed).order_by(Passage.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return [PassageRead.model_validate(i) for i in items]


@router.get("/stats", response_model=PassageStats)
async def stats_passages(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PassageStats:
    total = (await session.execute(select(func.count(Passage.id)))).scalar_one()
    authorized = (await session.execute(select(func.count(Passage.id)).where(Passage.allowed.is_(True)))).scalar_one()
    denied = (await session.execute(select(func.count(Passage.id)).where(Passage.allowed.is_(False)))).scalar_one()
    recognized = (await session.execute(select(func.count(Passage.id)).where(Passage.recognized.is_(True)))).scalar_one()
    unrecognized = (await session.execute(select(func.count(Passage.id)).where(Passage.recognized.is_(False)))).scalar_one()
    return PassageStats(
        total=total or 0,
        authorized=authorized or 0,
        denied=denied or 0,
        recognized=recognized or 0,
        unrecognized=unrecognized or 0,
    )
