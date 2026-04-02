"""AI service — orchestrates browser, planner, and generator agents."""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import TestSuite, TestCase, TestStep, Role, InputMethod
from modules.organizations.service import require_role
from . import browser, planner, generator
from .llm import LLMProvider


def _get_suite_or_404(db: Session, suite_id: str) -> TestSuite:
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


def _get_test_or_404(db: Session, test_id: str) -> TestCase:
    test = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


async def generate_test(
    db: Session,
    user_id: str,
    description: str,
    suite_id: str,
    test_id: str | None = None,
) -> dict:
    """
    Full AI pipeline:
    1. Verify access via suite → project → org RBAC
    2. Fetch target_url and optional storage_state_json from project
    3. Get accessibility tree via browser module
    4. Plan the test via planner agent
    5. Generate Playwright code via generator agent
    6. Persist: create or update TestCase, recreate TestSteps
    7. Return {"test_id", "code", "plan", "version"}
    """
    # 1. Verify membership
    suite = _get_suite_or_404(db, suite_id)
    project = suite.project
    require_role(db, user_id, project.organization_id, Role.member)

    # 2. Target URL and optional storage state
    target_url: str = project.target_url
    storage_state_json: str | None = getattr(project, "storage_state_json", None)

    # 3. Get accessibility tree
    tree_text = await browser.get_accessibility_tree(target_url, storage_state_json)

    # 4. Plan
    llm = LLMProvider()
    plan = await planner.plan_test(
        description=description,
        accessibility_tree=tree_text,
        target_url=target_url,
        llm=llm,
    )

    # 5. Generate code
    code = await generator.generate_code(plan=plan, llm=llm)

    # 6. Persist test case
    if test_id:
        test_case = _get_test_or_404(db, test_id)
        # Verify the test belongs to the same suite for safety
        if test_case.suite_id != suite_id:
            raise HTTPException(status_code=403, detail="Test does not belong to this suite")
        test_case.code = code
        test_case.version = (test_case.version or 1) + 1
        test_case.description = plan.get("description", description)
        # Remove old steps
        for step in list(test_case.steps):
            db.delete(step)
        db.flush()
    else:
        test_case = TestCase(
            suite_id=suite_id,
            name=plan.get("test_name", description[:200]),
            description=plan.get("description", description),
            code=code,
            version=1,
            input_method=InputMethod.text,
        )
        db.add(test_case)
        db.flush()  # get ID before adding steps

    # Create steps from plan
    for step_data in plan.get("steps", []):
        step = TestStep(
            test_id=test_case.id,
            order=step_data.get("order", 0),
            action=step_data.get("action", ""),
            selector=step_data.get("selector"),
            value=step_data.get("value"),
            description=step_data.get("description", ""),
            is_assertion=step_data.get("action") == "assert",
        )
        db.add(step)

    db.commit()
    db.refresh(test_case)

    return {
        "test_id": test_case.id,
        "code": test_case.code,
        "version": test_case.version,
        "plan": plan,
    }
