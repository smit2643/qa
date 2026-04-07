from fastapi import APIRouter, Depends, status, Body
from sqlalchemy.orm import Session
from core.database import get_db
from modules.auth.dependencies import get_current_user
from modules.suites import service
from modules.suites.schemas import SuiteCreate, SuiteUpdate, SuiteResponse, SuiteLoginConfig
from models import User

router = APIRouter(tags=["suites"])


def _suite_response(suite) -> SuiteResponse:
    return SuiteResponse.from_orm_with_auth(suite)


@router.post("/suites", response_model=SuiteResponse)
def create_suite(
    body: SuiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _suite_response(service.create_suite(db, current_user.id, body))


@router.get("/projects/{project_id}/suites", response_model=list[SuiteResponse])
def list_suites(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [_suite_response(s) for s in service.list_suites(db, current_user.id, project_id)]


@router.get("/suites/{suite_id}", response_model=SuiteResponse)
def get_suite(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _suite_response(service.get_suite(db, current_user.id, suite_id))


@router.patch("/suites/{suite_id}", response_model=SuiteResponse)
def update_suite(
    suite_id: str,
    body: SuiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _suite_response(service.update_suite(db, current_user.id, suite_id, body))


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_suite(db, current_user.id, suite_id)


@router.put("/suites/{suite_id}/login-config", response_model=SuiteResponse)
def set_login_config(
    suite_id: str,
    body: SuiteLoginConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set login credentials for this suite. All tests run with a shared authenticated session."""
    return _suite_response(service.set_login_config(db, current_user.id, suite_id, body))


@router.delete("/suites/{suite_id}/login-config", response_model=SuiteResponse)
def clear_login_config(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove login config and cached session from this suite."""
    return _suite_response(service.clear_login_config(db, current_user.id, suite_id))


@router.delete("/suites/{suite_id}/auth-state", response_model=SuiteResponse)
def clear_auth_state(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear the cached session — keeps credentials, forces re-login on next run."""
    return _suite_response(service.clear_auth_state(db, current_user.id, suite_id))


@router.post("/suites/{suite_id}/auth-state", status_code=status.HTTP_204_NO_CONTENT)
def save_auth_state(
    suite_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """Internal endpoint — called by the runner to persist the captured auth state.
    No user authentication required (runner has no JWT)."""
    state_json = body.get("state_json", "")
    if state_json:
        service.save_auth_state_internal(db, suite_id, state_json)
