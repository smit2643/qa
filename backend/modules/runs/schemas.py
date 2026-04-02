"""Schemas for the runs module — Task 30: Jobs API."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RunCreate(BaseModel):
    suite_id: str
    browser: str = "chromium"       # chromium | firefox | webkit
    test_ids: list[str] | None = None  # None = run all tests in suite
    branch: str | None = None
    commit_sha: str | None = None


class ResultResponse(BaseModel):
    id: str
    run_id: str
    test_id: str | None
    status: str
    error_message: str | None
    video_url: str | None
    trace_url: str | None
    log_url: str | None
    duration_ms: int | None
    browser: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RunResponse(BaseModel):
    id: str
    suite_id: str
    status: str
    trigger: str
    browser: str
    branch: str | None
    commit_sha: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    results: list[ResultResponse] = []
    model_config = ConfigDict(from_attributes=True)


class ResultUpdate(BaseModel):
    """Payload sent by the Celery worker via PATCH /runs/{run_id}/results/{result_id}."""
    status: str
    error_message: str | None = None
    duration_ms: int | None = None
    video_url: str | None = None
    log_url: str | None = None
    trace_url: str | None = None


class RunFinish(BaseModel):
    """Payload sent by the Celery worker via PATCH /runs/{run_id}/finish."""
    status: str  # passed | failed | cancelled
