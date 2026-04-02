"""Celery task — run a single TestCase and report results back to the API.

Full lifecycle (Tasks 21–29):
  1. Receive job from Redis queue
  2. Execute test in isolated Playwright context (video + trace)
  3. Upload artifacts to MinIO
  4. PATCH backend API with results
  5. Publish log events to Redis pub/sub for WebSocket streaming (Task 28)
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile

import httpx
import redis as redis_lib

from runner.celery_app import celery_app
from runner.executor.playwright_executor import run_test
from runner.storage.artifact_uploader import upload_run_artifacts

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
REDIS_URL = os.getenv("REDIS_URL", "redis://:bug0redis@localhost:6379/0")


def _publish(run_id: str, event: dict) -> None:
    """Publish a log event to the Redis pub/sub channel for this run (Task 28)."""
    try:
        r = redis_lib.from_url(REDIS_URL)
        r.publish(f"run:{run_id}:logs", json.dumps(event))
    except Exception:
        pass  # Never crash the worker over a log publish failure


def _patch_result(run_id: str, result_id: str, payload: dict) -> None:
    """PATCH /runs/{run_id}/results/{result_id} — update status in backend DB."""
    url = f"{BACKEND_URL}/api/v1/runs/{run_id}/results/{result_id}"
    try:
        with httpx.Client(timeout=30) as client:
            client.patch(url, json=payload)
    except Exception as exc:
        logger.error("Failed to PATCH result %s: %s", result_id, exc)


def _finish_run(run_id: str, status: str) -> None:
    """PATCH /runs/{run_id} to mark the whole run done."""
    url = f"{BACKEND_URL}/api/v1/runs/{run_id}/finish"
    try:
        with httpx.Client(timeout=30) as client:
            client.patch(url, json={"status": status})
    except Exception as exc:
        logger.error("Failed to finish run %s: %s", run_id, exc)


@celery_app.task(
    name="runner.run_test",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def run_test_task(
    self,
    run_id: str,
    result_id: str,
    test_code: str,
    test_name: str,
    target_url: str,
    browser: str = "chromium",
    storage_state_json: str | None = None,
):
    """
    Celery task — execute one test case and report back.

    Parameters match what the backend dispatches in service.create_run().
    """
    _publish(run_id, {"event": "started", "result_id": result_id, "test_name": test_name})
    logger.info("Running test '%s' (result=%s, browser=%s)", test_name, result_id, browser)

    artifacts_dir = tempfile.mkdtemp(prefix=f"bug0_{run_id[:8]}_")

    try:
        result = asyncio.run(run_test(
            test_code=test_code,
            test_name=test_name,
            target_url=target_url,
            browser_type=browser,
            storage_state_json=storage_state_json,
            artifacts_dir=artifacts_dir,
        ))

        # Upload artifacts to MinIO (Task 29)
        artifact_urls = upload_run_artifacts(
            run_id=run_id,
            result_id=result_id,
            video_path=result.video_path,
            screenshot_path=result.screenshot_path,
            trace_path=result.trace_path,
            console_logs=result.console_logs,
        )

        # Stream log lines to WebSocket clients (Task 28)
        for line in result.console_logs:
            _publish(run_id, {"event": "log", "result_id": result_id, "line": line})

        # Report back to backend
        payload = {
            "status": result.status,
            "error_message": result.error_message,
            "duration_ms": result.duration_ms,
            "video_url": artifact_urls.get("video_url"),
            "log_url": artifact_urls.get("log_url"),
            "trace_url": artifact_urls.get("trace_url"),
        }
        _patch_result(run_id, result_id, payload)

        _publish(run_id, {
            "event": "finished",
            "result_id": result_id,
            "status": result.status,
        })
        logger.info("Test '%s' finished: %s (%dms)", test_name, result.status, result.duration_ms)

    except Exception as exc:
        logger.exception("Unexpected error running test '%s'", test_name)
        _patch_result(run_id, result_id, {
            "status": "failed",
            "error_message": f"Worker error: {exc}",
        })
        _publish(run_id, {"event": "error", "result_id": result_id, "message": str(exc)})
    finally:
        shutil.rmtree(artifacts_dir, ignore_errors=True)
