from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from core.database import get_db
from modules.auth.dependencies import get_current_user
from modules.tests import service
from modules.tests.schemas import TestCaseCreate, TestCaseUpdate, TestCaseResponse
from models import User

router = APIRouter(tags=["tests"])


@router.post("/tests", response_model=TestCaseResponse)
def create_test(
    body: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_test(db, current_user.id, body)


@router.get("/suites/{suite_id}/tests", response_model=list[TestCaseResponse])
def list_tests(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_tests(db, current_user.id, suite_id)


@router.get("/tests/{test_id}", response_model=TestCaseResponse)
def get_test(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_test(db, current_user.id, test_id)


@router.patch("/tests/{test_id}", response_model=TestCaseResponse)
def update_test(
    test_id: str,
    body: TestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_test(db, current_user.id, test_id, body)


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_test(db, current_user.id, test_id)
