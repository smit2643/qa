from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.test_case import TestCase, InputMethod
from models.test_suite import TestSuite
from models.project import Project
from models import Role
from modules.organizations.service import require_role
from modules.tests.schemas import TestCaseCreate, TestCaseUpdate


def _get_org_id_for_suite(db: Session, suite_id: str) -> str:
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    project = db.query(Project).filter(Project.id == suite.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.organization_id


def _get_test_or_404(db: Session, test_id: str) -> TestCase:
    test = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test


def create_test(db: Session, user_id: str, data: TestCaseCreate) -> TestCase:
    org_id = _get_org_id_for_suite(db, data.suite_id)
    require_role(db, user_id, org_id, Role.member)
    test = TestCase(
        suite_id=data.suite_id,
        name=data.name,
        description=data.description,
        input_method=data.input_method,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


def list_tests(db: Session, user_id: str, suite_id: str) -> list[TestCase]:
    org_id = _get_org_id_for_suite(db, suite_id)
    require_role(db, user_id, org_id, Role.viewer)
    return db.query(TestCase).filter(TestCase.suite_id == suite_id).all()


def get_test(db: Session, user_id: str, test_id: str) -> TestCase:
    test = _get_test_or_404(db, test_id)
    org_id = _get_org_id_for_suite(db, test.suite_id)
    require_role(db, user_id, org_id, Role.viewer)
    return test


def update_test(db: Session, user_id: str, test_id: str, data: TestCaseUpdate) -> TestCase:
    test = _get_test_or_404(db, test_id)
    org_id = _get_org_id_for_suite(db, test.suite_id)
    require_role(db, user_id, org_id, Role.member)
    if data.name is not None:
        test.name = data.name
    if data.description is not None:
        test.description = data.description
    if data.code is not None:
        test.code = data.code
        test.version += 1
    db.commit()
    db.refresh(test)
    return test


def delete_test(db: Session, user_id: str, test_id: str) -> None:
    test = _get_test_or_404(db, test_id)
    org_id = _get_org_id_for_suite(db, test.suite_id)
    require_role(db, user_id, org_id, Role.admin)
    db.delete(test)
    db.commit()
