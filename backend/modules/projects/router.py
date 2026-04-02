from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from core.database import get_db
from modules.auth.dependencies import get_current_user
from modules.projects import service
from modules.projects.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from models import User

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_project(db, current_user.id, body)


@router.get("/organizations/{org_id}/projects", response_model=list[ProjectResponse])
def list_projects(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_projects(db, current_user.id, org_id)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_project(db, current_user.id, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_project(db, current_user.id, project_id, body)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_project(db, current_user.id, project_id)


@router.post("/projects/{project_id}/rotate-api-key", response_model=ProjectResponse)
def rotate_api_key(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.rotate_api_key(db, current_user.id, project_id)
