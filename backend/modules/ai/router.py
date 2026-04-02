"""AI router — /ai/generate and /ai/generate-from-steps endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from modules.auth.dependencies import get_current_user
from models import User, InputMethod
from . import service as ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class StepSchema(BaseModel):
    order: int
    action: str
    selector: str | None = None
    value: str | None = None
    description: str = ""


class GenerateRequest(BaseModel):
    description: str
    suite_id: str
    test_id: str | None = None


class GenerateFromStepsRequest(BaseModel):
    suite_id: str
    test_name: str
    steps: list[StepSchema]
    test_id: str | None = None
    input_method: str = "text"  # text | recording | video


class GenerateResponse(BaseModel):
    test_id: str
    code: str
    version: int
    steps: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a Playwright test from a plain English description.
    browser-use Agent navigates your app and records real actions.
    Expect 15-40 seconds.
    """
    result = await ai_service.generate_test(
        db=db,
        user_id=current_user.id,
        description=req.description,
        suite_id=req.suite_id,
        test_id=req.test_id,
    )
    return result


@router.post("/generate-from-steps", response_model=GenerateResponse)
async def generate_from_steps(
    req: GenerateFromStepsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate Playwright code from pre-built steps.
    Used by screen recording and video upload pipelines.
    """
    try:
        input_method = InputMethod(req.input_method)
    except ValueError:
        input_method = InputMethod.text

    steps = [s.model_dump() for s in req.steps]

    result = await ai_service.generate_from_steps(
        db=db,
        user_id=current_user.id,
        suite_id=req.suite_id,
        test_name=req.test_name,
        steps=steps,
        test_id=req.test_id,
        input_method=input_method,
    )
    return result
