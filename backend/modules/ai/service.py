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


def _build_task_prompt(
    description: str,
    already_logged_in: bool = False,
    login_email: str | None = None,
    login_password: str | None = None,
) -> tuple[str, int]:
    """
    Parse a natural-language description into a numbered task list and compute
    the appropriate max_steps budget.

    Splits on common transition words (then, after that, next, also, finally).
    Multi-step flows get more steps per sub-task; simple flows use the default.
    """
    import re

    # Split on transition keywords that signal a new sub-task
    parts = re.split(
        r'\b(?:then|and then|after that|next,?\s|also,?\s|finally,?\s|afterwards)\b',
        description,
        flags=re.IGNORECASE,
    )
    parts = [p.strip().rstrip(',') for p in parts if p.strip()]

    if already_logged_in:
        auth_note = (
            "NOTE: You are already logged in — the browser session has valid auth cookies. "
            "Do NOT navigate to the login page or enter credentials. Start directly on the target feature.\n\n"
        )
    elif login_email and login_password:
        auth_note = (
            f"NOTE: If you encounter a login page, use EXACTLY these credentials — do NOT guess or use placeholders:\n"
            f"  Email/Username: {login_email}\n"
            f"  Password: {login_password}\n"
            f"After logging in successfully, continue with the main task.\n\n"
        )
    else:
        auth_note = ""

    if len(parts) <= 1:
        # Simple single-flow task
        task = (
            f"{auth_note}"
            f"{description}. "
            f"Complete EVERY step. "
            f"For any form (login, signup, search): fill ALL input fields with complete values, "
            f"then click the submit/confirm button. "
            f"Only say done after the full task is confirmed complete on screen."
        )
        max_steps = 15
    else:
        # Multi-step flow — number each sub-task explicitly
        numbered = "\n".join(f"Step {i + 1}: {p}" for i, p in enumerate(parts))
        task = (
            f"{auth_note}"
            f"Complete ALL of the following steps in order. Do NOT skip any step.\n\n"
            f"{numbered}\n\n"
            f"RULES:\n"
            f"- Work through each step sequentially — do not skip ahead.\n"
            f"- For any form (login, search box, etc.): fill ALL fields with their complete values, "
            f"then click the submit/search/confirm button.\n"
            f"- After clicking a button that triggers navigation, wait for the new page to load "
            f"before proceeding to the next step.\n"
            f"- Only say done after ALL {len(parts)} steps are fully completed and confirmed on screen."
        )
        # Budget: 8 actions per sub-task (fill + click + wait per field, then navigation)
        max_steps = max(20, len(parts) * 8)

    return task, max_steps


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
    # Suite-level auth state takes priority (already logged in from a previous run)
    storage_state_json: str | None = (
        getattr(suite, "storage_state_json", None)
        or getattr(project, "storage_state_json", None)
    )

    # If suite already has auth state, skip login in the task description
    has_auth = bool(storage_state_json)
    suite_login_email: str | None = getattr(suite, "login_email", None)
    suite_login_password: str | None = getattr(suite, "login_password", None)

    # 2 + 3. browser-use Agent navigates app, returns real steps
    task, max_steps = _build_task_prompt(
        description,
        already_logged_in=has_auth,
        login_email=suite_login_email if not has_auth else None,
        login_password=suite_login_password if not has_auth else None,
    )
    steps = await browser.run_agent(
        task=task,
        target_url=target_url,
        storage_state_json=storage_state_json,
        max_steps=max_steps,
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
    Steps come in already extracted — normalize them, then run the Generator Agent.
    """
    suite = _get_suite_or_404(db, suite_id)
    project = suite.project
    require_role(db, user_id, project.organization_id, Role.member)

    # Normalize steps before code generation (handles edits from visual editor)
    from modules.extraction.normalizer import normalize_steps
    steps = normalize_steps(steps)

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
