from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.test_step import TestStep
from models.test_case import TestCase
from models.test_suite import TestSuite
from models.project import Project
from models import Role
from modules.organizations.service import require_role
from modules.steps.schemas import StepCreate, StepUpdate


def _get_org_id_for_test(db: Session, test_id: str) -> str:
    test = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test case not found")
    suite = db.query(TestSuite).filter(TestSuite.id == test.suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    project = db.query(Project).filter(Project.id == suite.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.organization_id


def _get_step_or_404(db: Session, step_id: str) -> TestStep:
    step = db.query(TestStep).filter(TestStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


def create_step(db: Session, user_id: str, data: StepCreate) -> TestStep:
    org_id = _get_org_id_for_test(db, data.test_id)
    require_role(db, user_id, org_id, Role.member)
    step = TestStep(
        test_id=data.test_id,
        order=data.order,
        action=data.action.value,
        selector=data.selector,
        value=data.value,
        description=data.description,
        is_assertion=data.is_assertion,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def list_steps(db: Session, user_id: str, test_id: str) -> list[TestStep]:
    org_id = _get_org_id_for_test(db, test_id)
    require_role(db, user_id, org_id, Role.viewer)
    return db.query(TestStep).filter(TestStep.test_id == test_id).order_by(TestStep.order).all()


def get_step(db: Session, user_id: str, step_id: str) -> TestStep:
    step = _get_step_or_404(db, step_id)
    org_id = _get_org_id_for_test(db, step.test_id)
    require_role(db, user_id, org_id, Role.viewer)
    return step


def update_step(db: Session, user_id: str, step_id: str, data: StepUpdate) -> TestStep:
    step = _get_step_or_404(db, step_id)
    org_id = _get_org_id_for_test(db, step.test_id)
    require_role(db, user_id, org_id, Role.member)
    if data.order is not None:
        step.order = data.order
    if data.action is not None:
        step.action = data.action.value
    if data.selector is not None:
        step.selector = data.selector
    if data.value is not None:
        step.value = data.value
    if data.description is not None:
        step.description = data.description
    if data.is_assertion is not None:
        step.is_assertion = data.is_assertion
    db.commit()
    db.refresh(step)
    return step


def delete_step(db: Session, user_id: str, step_id: str) -> None:
    step = _get_step_or_404(db, step_id)
    org_id = _get_org_id_for_test(db, step.test_id)
    require_role(db, user_id, org_id, Role.member)
    db.delete(step)
    db.commit()


def reorder_steps(db: Session, user_id: str, test_id: str, step_ids: list[str]) -> list[TestStep]:
    org_id = _get_org_id_for_test(db, test_id)
    require_role(db, user_id, org_id, Role.member)

    # Verify all step_ids belong to this test
    steps_by_id: dict[str, TestStep] = {}
    for step_id in step_ids:
        step = db.query(TestStep).filter(TestStep.id == step_id, TestStep.test_id == test_id).first()
        if not step:
            raise HTTPException(
                status_code=400,
                detail=f"Step {step_id} does not belong to test {test_id}",
            )
        steps_by_id[step_id] = step

    # Reassign order (0-indexed)
    for index, step_id in enumerate(step_ids):
        steps_by_id[step_id].order = index

    db.commit()

    # Return steps in new order
    for step in steps_by_id.values():
        db.refresh(step)

    return [steps_by_id[step_id] for step_id in step_ids]
