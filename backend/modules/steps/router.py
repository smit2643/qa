from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from modules.auth.dependencies import get_current_user
from modules.steps import service
from modules.steps.schemas import StepCreate, StepUpdate, StepResponse
from models import User

router = APIRouter(tags=["steps"])


class ReorderRequest(BaseModel):
    step_ids: list[str]


@router.post("/steps", response_model=StepResponse)
def create_step(
    body: StepCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_step(db, current_user.id, body)


@router.get("/tests/{test_id}/steps", response_model=list[StepResponse])
def list_steps(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_steps(db, current_user.id, test_id)


@router.get("/steps/{step_id}", response_model=StepResponse)
def get_step(
    step_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_step(db, current_user.id, step_id)


@router.patch("/steps/{step_id}", response_model=StepResponse)
def update_step(
    step_id: str,
    body: StepUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_step(db, current_user.id, step_id, body)


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(
    step_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_step(db, current_user.id, step_id)


@router.post("/tests/{test_id}/steps/reorder", response_model=list[StepResponse])
def reorder_steps(
    test_id: str,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.reorder_steps(db, current_user.id, test_id, body.step_ids)
