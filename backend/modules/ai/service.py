"""AI service — orchestrates browser-use Agent and Generator."""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import TestSuite, TestCase, TestStep, Role, InputMethod
from modules.organizations.service import require_role
from . import browser, generator
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


def _save_test(
    db: Session,
    suite_id: str,
    steps: list[dict],
    code: str,
    name: str,
    description: str,
    test_id: str | None,
    input_method: InputMethod = InputMethod.text,
) -> TestCase:
    """Create or update a TestCase and its steps."""
    if test_id:
        test_case = _get_test_or_404(db, test_id)
        if test_case.suite_id != suite_id:
            raise HTTPException(status_code=403, detail="Test does not belong to this suite")
        test_case.code = code
        test_case.version = (test_case.version or 1) + 1
        test_case.description = description
        for step in list(test_case.steps):
            db.delete(step)
        db.flush()
    else:
        test_case = TestCase(
            suite_id=suite_id,
            name=name[:200],
            description=description,
            code=code,
            version=1,
            input_method=input_method,
        )
        db.add(test_case)
        db.flush()

    for step_data in steps:
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
    return test_case


async def generate_test(
    db: Session,
    user_id: str,
    description: str,
    suite_id: str,
    test_id: str | None = None,
) -> dict:
    """
    Full AI pipeline — text description input:
    1. Verify access (suite → project → org RBAC)
    2. Run browser-use Agent: navigates target_url, performs the described flow, records real actions
    3. Convert Agent history → structured steps
    4. Generator Agent: steps → Playwright Python code
    5. Save TestCase + TestSteps to DB
    6. Return {test_id, code, version, steps}
    """
    # 1. Verify membership
    suite = _get_suite_or_404(db, suite_id)
    project = suite.project
    require_role(db, user_id, project.organization_id, Role.member)

    target_url: str = project.target_url
    storage_state_json: str | None = getattr(project, "storage_state_json", None)

    # 2 + 3. browser-use Agent navigates app, returns real steps
    task = (
        f"Perform the following user flow on the web application: {description}. "
        f"Navigate through the app, interact with all necessary elements, "
        f"and complete the flow end to end."
    )
    steps = await browser.run_agent(
        task=task,
        target_url=target_url,
        storage_state_json=storage_state_json,
        max_steps=25,
    )

    # 4. Generate Playwright code from real steps
    llm = LLMProvider()
    code = await generator.generate_code(steps=steps, llm=llm)

    # 5. Save to DB
    test_name = description[:100] if len(description) <= 100 else description[:97] + "..."
    test_case = _save_test(
        db=db,
        suite_id=suite_id,
        steps=steps,
        code=code,
        name=test_name,
        description=description,
        test_id=test_id,
        input_method=InputMethod.text,
    )

    return {
        "test_id": test_case.id,
        "code": test_case.code,
        "version": test_case.version,
        "steps": steps,
    }


async def generate_from_steps(
    db: Session,
    user_id: str,
    suite_id: str,
    test_name: str,
    steps: list[dict],
    test_id: str | None = None,
    input_method: InputMethod = InputMethod.text,
) -> dict:
    """
    Generate Playwright code from pre-built steps (screen recording or video upload).
    Steps come in already extracted — we just run the Generator Agent.
    """
    suite = _get_suite_or_404(db, suite_id)
    project = suite.project
    require_role(db, user_id, project.organization_id, Role.member)

    llm = LLMProvider()
    code = await generator.generate_code(steps=steps, llm=llm)

    test_case = _save_test(
        db=db,
        suite_id=suite_id,
        steps=steps,
        code=code,
        name=test_name[:200],
        description=f"Generated from {input_method.value} input",
        test_id=test_id,
        input_method=input_method,
    )

    return {
        "test_id": test_case.id,
        "code": test_case.code,
        "version": test_case.version,
        "steps": steps,
    }
