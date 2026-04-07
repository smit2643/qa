"""Runs service — Task 30: Jobs API business logic."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import (
    TestCase, TestResult, TestRun, TestSuite, Role,
    BrowserType, ResultStatus, RunStatus, TriggerType,
)
from modules.organizations.service import require_role
from .schemas import RunCreate, ResultUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_suite_or_404(db: Session, suite_id: str) -> TestSuite:
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


def _get_run_or_404(db: Session, run_id: str) -> TestRun:
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _get_result_or_404(db: Session, result_id: str) -> TestResult:
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


def _org_id_for_suite(suite: TestSuite) -> str:
    return suite.project.organization_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_run(
    db: Session,
    user_id: str,
    data: RunCreate,
    trigger: TriggerType = TriggerType.manual,
) -> TestRun:
    """
    Create a TestRun + one TestResult per test case, then dispatch Celery tasks.
    Returns the TestRun immediately (status = queued).
    """
    suite = _get_suite_or_404(db, data.suite_id)
    require_role(db, user_id, _org_id_for_suite(suite), Role.member)

    # Validate browser
    try:
        browser = BrowserType(data.browser)
    except ValueError:
        browser = BrowserType.chromium

    run = TestRun(
        suite_id=data.suite_id,
        status=RunStatus.queued,
        trigger=trigger,
        browser=browser,
        branch=data.branch,
        commit_sha=data.commit_sha,
    )
    db.add(run)
    db.flush()

    # Determine which tests to run — only include tests that have generated code
    if data.test_ids:
        tests = db.query(TestCase).filter(
            TestCase.id.in_(data.test_ids),
            TestCase.suite_id == data.suite_id,
        ).all()
    else:
        tests = db.query(TestCase).filter(TestCase.suite_id == data.suite_id).all()

    # Filter out tests with no code — these are recordings/imports that haven't been generated yet
    tests = [t for t in tests if t.code and t.code.strip()]

    if not tests:
        raise HTTPException(
            status_code=422,
            detail="No runnable tests found. Generate code for your tests first using the Generate button.",
        )

    results = []
    for test in tests:
        result = TestResult(
            run_id=run.id,
            test_id=test.id,
            status=ResultStatus.pending,
            browser=browser,
        )
        db.add(result)
        results.append((test, result))

    db.commit()
    db.refresh(run)

    # Dispatch Celery tasks (after commit so IDs are stable)
    _dispatch_tasks(run, results, suite, use_playwright_code=data.use_playwright_code)

    return run


def _dispatch_tasks(run: TestRun, results: list, suite: TestSuite, use_playwright_code: bool = False) -> None:
    """
    Dispatch one sequential Celery task for the whole suite.

    Tests run one after another; each test's browser session (cookies,
    localStorage) is captured and injected into the next test so repeated
    logins are eliminated.  A single-test run uses the same task but with
    a one-item list.
    """
    import sys
    from pathlib import Path
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from runner.celery_app import celery_app

    target_url: str = suite.project.target_url

    # Suite-level auth takes priority over project-level storage state
    initial_storage_state: str | None = (
        getattr(suite, "storage_state_json", None)
        or getattr(suite.project, "storage_state_json", None)
    )
    login_url: str | None = getattr(suite, "login_url", None)
    login_email: str | None = getattr(suite, "login_email", None)
    login_password: str | None = getattr(suite, "login_password", None)

    # Build ordered list for the worker
    tests_payload = [
        {
            "result_id": result.id,
            "test_name": test.name,
            "test_description": test.description or "",
            # Always include both code and steps — worker chooses based on use_playwright_code flag
            "test_code": test.code or "",
            "steps": [
                {
                    "order": s.order,
                    "action": s.action,
                    "selector": s.selector or "",
                    "value": s.value or "",
                    "description": s.description or "",
                }
                for s in sorted(test.steps, key=lambda x: x.order)
            ],
        }
        for test, result in results
    ]

    celery_app.send_task(
        "runner.run_suite_sequential",
        kwargs={
            "run_id": run.id,
            "suite_id": suite.id,
            "tests": tests_payload,
            "target_url": target_url,
            "browser": run.browser.value,
            "initial_storage_state": initial_storage_state,
            "login_url": login_url,
            "login_email": login_email,
            "login_password": login_password,
            "use_playwright_code": use_playwright_code,
        },
    )

    # Transition run to running now that task is dispatched
    from core.database import SessionLocal
    with SessionLocal() as db2:
        r = db2.query(TestRun).filter(TestRun.id == run.id).first()
        if r:
            r.status = RunStatus.running
            r.started_at = datetime.now(timezone.utc)
            db2.commit()


def get_run(db: Session, user_id: str, run_id: str) -> TestRun:
    run = _get_run_or_404(db, run_id)
    suite = _get_suite_or_404(db, run.suite_id)
    require_role(db, user_id, _org_id_for_suite(suite), Role.viewer)
    return run


def list_suite_runs(db: Session, user_id: str, suite_id: str) -> list[TestRun]:
    suite = _get_suite_or_404(db, suite_id)
    require_role(db, user_id, _org_id_for_suite(suite), Role.viewer)
    return (
        db.query(TestRun)
        .filter(TestRun.suite_id == suite_id)
        .order_by(TestRun.created_at.desc())
        .all()
    )


def update_result(
    db: Session,
    run_id: str,
    result_id: str,
    data: ResultUpdate,
) -> TestResult:
    """Called by the Celery worker to report result. No auth — internal callback."""
    result = _get_result_or_404(db, result_id)
    if result.run_id != run_id:
        raise HTTPException(status_code=400, detail="Result does not belong to this run")

    try:
        result.status = ResultStatus(data.status)
    except ValueError:
        result.status = ResultStatus.failed

    if data.error_message is not None:
        result.error_message = data.error_message
    if data.duration_ms is not None:
        result.duration_ms = data.duration_ms
    if data.video_url is not None:
        result.video_url = data.video_url
    if data.log_url is not None:
        result.log_url = data.log_url
    if data.trace_url is not None:
        result.trace_url = data.trace_url

    db.commit()
    db.refresh(result)

    # Auto-finish run if all results are resolved
    _maybe_finish_run(db, run_id)
    return result


def finish_run(db: Session, run_id: str, status: str) -> TestRun:
    """Explicitly mark a run finished. Called by worker or internal logic."""
    run = _get_run_or_404(db, run_id)
    try:
        run.status = RunStatus(status)
    except ValueError:
        run.status = RunStatus.failed
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def _maybe_finish_run(db: Session, run_id: str) -> None:
    """If all results are resolved (not pending), mark the run passed/failed.

    Uses SELECT FOR UPDATE to prevent two concurrent worker callbacks from
    both seeing 0 pending results and both publishing run_passed.
    """
    # Lock the run row so only one concurrent callback can evaluate completion
    run = (
        db.query(TestRun)
        .filter(TestRun.id == run_id)
        .with_for_update()
        .first()
    )
    if not run or run.status not in (RunStatus.running, RunStatus.queued):
        return

    pending = db.query(TestResult).filter(
        TestResult.run_id == run_id,
        TestResult.status == ResultStatus.pending,
    ).count()

    if pending > 0:
        return  # Still waiting

    failed = db.query(TestResult).filter(
        TestResult.run_id == run_id,
        TestResult.status == ResultStatus.failed,
    ).count()

    final_status = RunStatus.failed if failed > 0 else RunStatus.passed
    run.status = final_status
    run.finished_at = datetime.now(timezone.utc)
    db.commit()

    # Publish run-level completion event so the WebSocket stream closes cleanly
    _publish_run_event(run_id, final_status.value)


def _publish_run_event(run_id: str, status: str) -> None:
    """Publish run_passed / run_failed to Redis so the WebSocket stream closes."""
    try:
        import redis as redis_lib
        from core.config import settings
        r = redis_lib.from_url(settings.redis_url)
        import json
        event = "run_passed" if status == "passed" else "run_failed"
        r.publish(f"run:{run_id}:logs", json.dumps({"event": event, "status": status}))
    except Exception:
        pass  # Never crash the API over a publish failure
