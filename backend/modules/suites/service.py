from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import TestSuite, Project, Role
from modules.organizations.service import require_role
from modules.suites.schemas import SuiteCreate, SuiteUpdate


def _get_suite_or_404(db: Session, suite_id: str) -> TestSuite:
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _check_suite_access(db: Session, user_id: str, suite: TestSuite, minimum_role: Role = Role.viewer) -> None:
    require_role(db, user_id, suite.project.organization_id, minimum_role)


def create_suite(db: Session, user_id: str, data: SuiteCreate) -> TestSuite:
    project = _get_project_or_404(db, data.project_id)
    require_role(db, user_id, project.organization_id, Role.member)
    suite = TestSuite(
        project_id=data.project_id,
        name=data.name,
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


def list_suites(db: Session, user_id: str, project_id: str) -> list[TestSuite]:
    project = _get_project_or_404(db, project_id)
    require_role(db, user_id, project.organization_id, Role.viewer)
    return db.query(TestSuite).filter(TestSuite.project_id == project_id).all()


def get_suite(db: Session, user_id: str, suite_id: str) -> TestSuite:
    suite = _get_suite_or_404(db, suite_id)
    _check_suite_access(db, user_id, suite, Role.viewer)
    return suite


def update_suite(db: Session, user_id: str, suite_id: str, data: SuiteUpdate) -> TestSuite:
    suite = _get_suite_or_404(db, suite_id)
    _check_suite_access(db, user_id, suite, Role.member)
    if data.name is not None:
        suite.name = data.name
    db.commit()
    db.refresh(suite)
    return suite


def delete_suite(db: Session, user_id: str, suite_id: str) -> None:
    suite = _get_suite_or_404(db, suite_id)
    _check_suite_access(db, user_id, suite, Role.admin)
    db.delete(suite)
    db.commit()
