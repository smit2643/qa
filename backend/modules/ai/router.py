"""AI router — /ai/generate endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from modules.auth.dependencies import get_current_user
from models import User
from . import service as ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateRequest(BaseModel):
    description: str
    suite_id: str
    test_id: str | None = None


class GenerateResponse(BaseModel):
    test_id: str
    code: str
    version: int
    plan: dict


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await ai_service.generate_test(
        db=db,
        user_id=current_user.id,
        description=req.description,
        suite_id=req.suite_id,
        test_id=req.test_id,
    )
    return result
