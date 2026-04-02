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

    # Determine which tests to run
    if data.test_ids:
        tests = db.query(TestCase).filter(
            TestCase.id.in_(data.test_ids),
            TestCase.suite_id == data.suite_id,
        ).all()
    else:
        tests = db.query(TestCase).filter(TestCase.suite_id == data.suite_id).all()

    if not tests:
        raise HTTPException(status_code=422, detail="No test cases found to run")

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
    _dispatch_tasks(run, results, suite)

    return run


def _dispatch_tasks(run: TestRun, results: list, suite: TestSuite) -> None:
    """Dispatch one Celery task per (test, result) pair."""
    from runner.celery_app import celery_app

    target_url: str = suite.project.target_url
    storage_state: str | None = getattr(suite.project, "storage_state_json", None)

    for test, result in results:
        celery_app.send_task(
            "runner.run_test",
            kwargs={
                "run_id": run.id,
                "result_id": result.id,
                "test_code": test.code or "",
                "test_name": test.name,
                "target_url": target_url,
                "browser": run.browser.value,
                "storage_state_json": storage_state,
            },
        )

    # Transition run to running now that tasks are dispatched
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
    """If all results are resolved (not pending), mark the run passed/failed."""
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
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

    run.status = RunStatus.failed if failed > 0 else RunStatus.passed
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
