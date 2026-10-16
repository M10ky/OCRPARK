"""Routes CRUD pour plaques autorisées."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.allowed_plate import AllowedPlate
from app.models.user import User
from app.schemas.plates import AllowedPlateCreate, AllowedPlateRead, AllowedPlateUpdate
from app.services.ocr_client import normalize_plate

router = APIRouter(prefix="/api/plates", tags=["plates"])


@router.get("", response_model=list[AllowedPlateRead])
async def list_plates(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    active: bool | None = None,
) -> list[AllowedPlateRead]:
    stmt = select(AllowedPlate).order_by(AllowedPlate.created_at.desc())
    if active is not None:
        stmt = select(AllowedPlate).where(AllowedPlate.active == active).order_by(AllowedPlate.created_at.desc())
    result = await session.execute(stmt)
    items = result.scalars().all()
    return [AllowedPlateRead.model_validate(i) for i in items]


@router.post("", response_model=AllowedPlateRead, status_code=status.HTTP_201_CREATED)
async def create_plate(
    plate_in: AllowedPlateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AllowedPlateRead:
    norm = normalize_plate(plate_in.plate)
    if not norm:
        raise HTTPException(status_code=400, detail="Plaque invalide")
    plate = AllowedPlate(
        plate=norm,
        description=plate_in.description,
        active=plate_in.active,
    )
    session.add(plate)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Plaque déjà existante")
    await session.refresh(plate)
    return AllowedPlateRead.model_validate(plate)


@router.get("/{plate}", response_model=AllowedPlateRead)
async def get_plate(
    plate: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AllowedPlateRead:
    norm = normalize_plate(plate)
    stmt = select(AllowedPlate).where(AllowedPlate.plate == norm)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaque introuvable")
    return AllowedPlateRead.model_validate(item)


@router.put("/{plate_id}", response_model=AllowedPlateRead)
async def update_plate(
    plate_id: UUID,
    plate_in: AllowedPlateUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AllowedPlateRead:
    stmt = select(AllowedPlate).where(AllowedPlate.id == plate_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaque introuvable")
    if plate_in.plate is not None:
        norm = normalize_plate(plate_in.plate)
        if not norm:
            raise HTTPException(status_code=400, detail="Plaque invalide")
        item.plate = norm
    if plate_in.description is not None:
        item.description = plate_in.description
    if plate_in.active is not None:
        item.active = plate_in.active
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Plaque déjà existante")
    await session.refresh(item)
    return AllowedPlateRead.model_validate(item)


@router.delete("/{plate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plate(
    plate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    stmt = select(AllowedPlate).where(AllowedPlate.id == plate_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaque introuvable")
    await session.delete(item)
    await session.commit()
