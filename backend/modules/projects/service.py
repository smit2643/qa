import secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Project, Role
from modules.organizations.service import require_role
from modules.projects.schemas import ProjectCreate, ProjectUpdate


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _check_project_access(db: Session, user_id: str, project: Project, minimum_role: Role = Role.viewer) -> None:
    require_role(db, user_id, project.organization_id, minimum_role)


def create_project(db: Session, user_id: str, data: ProjectCreate) -> Project:
    require_role(db, user_id, data.organization_id, Role.member)
    project = Project(
        organization_id=data.organization_id,
        name=data.name,
        target_url=str(data.target_url),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, user_id: str, org_id: str) -> list[Project]:
    require_role(db, user_id, org_id, Role.viewer)
    return db.query(Project).filter(Project.organization_id == org_id).all()


def get_project(db: Session, user_id: str, project_id: str) -> Project:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.viewer)
    return project


def update_project(db: Session, user_id: str, project_id: str, data: ProjectUpdate) -> Project:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.admin)
    if data.name is not None:
        project.name = data.name
    if data.target_url is not None:
        project.target_url = data.target_url
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, user_id: str, project_id: str) -> None:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.owner)
    db.delete(project)
    db.commit()


def rotate_api_key(db: Session, user_id: str, project_id: str) -> Project:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.admin)
    project.api_key = secrets.token_hex(32)
    db.commit()
    db.refresh(project)
    return project


def upload_storage_state(db: Session, user_id: str, project_id: str, json_content: str) -> Project:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.admin)
    project.storage_state_json = json_content
    db.commit()
    db.refresh(project)
    return project


def delete_storage_state(db: Session, user_id: str, project_id: str) -> Project:
    project = _get_project_or_404(db, project_id)
    _check_project_access(db, user_id, project, Role.admin)
    project.storage_state_json = None
    db.commit()
    db.refresh(project)
    return project
