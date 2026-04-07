"""Recordings service — process WebM uploads and extract test steps via Claude Vision."""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import TestSuite, TestCase, TestStep, Role, InputMethod
from modules.organizations.service import require_role
from modules.recordings import extractor
from modules.ai.llm import LLMProvider


def _get_suite_or_404(db: Session, suite_id: str) -> TestSuite:
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


async def process_recording(
    db: Session,
    user_id: str,
    suite_id: str,
    test_name: str,
    video_bytes: bytes,
    filename: str,
) -> dict:
    """
    1. RBAC: verify member+ in suite's org.
    2. Get project target_url.
    3. Extract steps from video via Claude Vision.
    4. Create TestCase with InputMethod.recording (no code yet — user reviews steps first).
    5. Create TestSteps from extracted steps.
    6. Return {test_id, suite_id, test_name, steps, message}.
    """
    # 1. RBAC
    suite = _get_suite_or_404(db, suite_id)
    project = suite.project
    require_role(db, user_id, project.organization_id, Role.member)

    # 2. Target URL
    target_url: str = project.target_url

    # 3. Extract steps — pass suite login so extractor prepends login if video doesn't show it
    llm = LLMProvider()
    steps = await extractor.extract_steps_from_video(
        video_bytes=video_bytes,
        target_url=target_url,
        llm=llm,
        login_email=getattr(suite, "login_email", None),
        login_password=getattr(suite, "login_password", None),
        login_url=getattr(suite, "login_url", None),
    )

    # 4. Create TestCase (no code — user will review and then trigger code generation)
    test_case = TestCase(
        suite_id=suite_id,
        name=test_name[:200],
        description=f"Extracted from screen recording: {filename}",
        code="",
        version=1,
        input_method=InputMethod.recording,
    )
    db.add(test_case)
    db.flush()

    # 5. Create TestSteps
    for step_data in steps:
        step = TestStep(
            test_id=test_case.id,
            order=step_data.get("order", 0),
            action=step_data.get("action", "wait"),
            selector=step_data.get("selector"),
            value=step_data.get("value"),
            description=step_data.get("description", ""),
            is_assertion=step_data.get("action") == "assert",
        )
        db.add(step)

    db.commit()
    db.refresh(test_case)

    step_count = len(steps)
    return {
        "test_id": test_case.id,
        "suite_id": suite_id,
        "test_name": test_name,
        "steps": list(test_case.steps),
        "message": f"{step_count} step{'s' if step_count != 1 else ''} extracted. Review and edit before generating code.",
    }
