"""Routes d'orchestration OCR→décision→barrière."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.orchestrate import OrchestrateResult
from app.services.ocr_client import OCRClient
from app.services.orchestrator import decide_and_act

router = APIRouter(prefix="/api/orchestrate", tags=["orchestrate"])
ocr_client = OCRClient()


@router.post("/upload", response_model=OrchestrateResult)
async def orchestrate_upload(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
) -> OrchestrateResult:
    content = await file.read()
    ocr_res = await ocr_client.upload(content, file.filename)
    res = await decide_and_act(session, ocr_res, source="orchestrator:upload")
    return OrchestrateResult(**res)


@router.post("/scan", response_model=OrchestrateResult)
async def orchestrate_scan(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrchestrateResult:
    ocr_res = await ocr_client.scan_camera()
    res = await decide_and_act(session, ocr_res, source="orchestrator:scan")
    return OrchestrateResult(**res)
