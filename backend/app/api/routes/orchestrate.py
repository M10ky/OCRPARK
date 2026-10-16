"""Routes d'orchestration OCR→décision→barrière."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.orchestrate import OrchestrateResult
from app.services.ocr_client import OCRClient
from app.services.orchestrator import decide_and_act

router = APIRouter(prefix="/api/orchestrate", tags=["orchestrate"])
ocr_client = OCRClient()

Gate = Literal["entry", "exit"]


@router.post("/upload", response_model=OrchestrateResult)
async def orchestrate_upload(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
    gate: Annotated[Gate, Query(description="Barrière visée : entry (entrée) ou exit (sortie).")] = "entry",
) -> OrchestrateResult:
    content = await file.read()
    ocr_res = await ocr_client.upload(content, file.filename)
    res = await decide_and_act(session, ocr_res, source="orchestrator:upload", gate=gate)
    return OrchestrateResult(**res)


@router.post("/scan", response_model=OrchestrateResult)
async def orchestrate_scan(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gate: Annotated[Gate, Query(description="Barrière visée : entry (entrée) ou exit (sortie).")] = "entry",
) -> OrchestrateResult:
    ocr_res = await ocr_client.scan_camera()
    res = await decide_and_act(session, ocr_res, source="orchestrator:scan", gate=gate)
    return OrchestrateResult(**res)
