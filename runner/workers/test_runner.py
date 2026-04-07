"""Celery tasks — run tests with Playwright, suite-level auth sharing.

Flow:
  1. If suite has login config and no cached session → headless login once → save session
  2. Each test runs via Playwright with the shared session injected → no login steps needed
  3. Auth state is captured after each test and passed to the next
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
from runner.executor.playwright_executor import run_test as run_playwright_test
from runner.storage.artifact_uploader import upload_run_artifacts

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
REDIS_URL = os.getenv("REDIS_URL", "redis://:bug0redis@localhost:6380/0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _publish(run_id: str, event: dict) -> None:
    try:
        r = redis_lib.from_url(REDIS_URL)
        r.publish(f"run:{run_id}:logs", json.dumps(event))
    except Exception:
        pass


def _patch_result(run_id: str, result_id: str, payload: dict) -> None:
    url = f"{BACKEND_URL}/api/v1/runs/{run_id}/results/{result_id}"
    try:
        with httpx.Client(timeout=30) as client:
            client.patch(url, json=payload)
    except Exception as exc:
        logger.error("Failed to PATCH result %s: %s", result_id, exc)


def _save_suite_auth_state(suite_id: str, state_json: str) -> None:
    """Persist captured auth state to suite so future runs skip login."""
    url = f"{BACKEND_URL}/api/v1/suites/{suite_id}/auth-state"
    try:
        with httpx.Client(timeout=15) as client:
            client.post(url, json={"state_json": state_json})
        logger.info("Saved auth state to suite %s", suite_id)
    except Exception as exc:
        logger.error("Failed to save suite auth state: %s", exc)


async def _run_login_flow(login_url: str, login_email: str, login_password: str) -> str | None:
    """
    Open a headless browser, fill login form, capture and return
    Playwright storage state JSON. Returns None on failure.
    """
    from playwright.async_api import async_playwright

    logger.info("Running login flow for %s", login_url)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(login_url, timeout=30000)

            # Fill email/username
            for sel in ['input[type="email"]', 'input[name="email"]',
                        'input[name="username"]', 'input[placeholder*="email" i]',
                        'input[placeholder*="user" i]']:
                try:
                    await page.fill(sel, login_email, timeout=2000)
                    break
                except Exception:
                    continue
            else:
                logger.warning("Login: could not find email/username field")
                await browser.close()
                return None

            await page.fill('input[type="password"]', login_password, timeout=5000)

            for sel in ['button[type="submit"]', 'input[type="submit"]',
                        'button:has-text("sign in")', 'button:has-text("log in")',
                        'button:has-text("login")', 'button:has-text("continue")']:
                try:
                    await page.click(sel, timeout=2000)
                    break
                except Exception:
                    continue

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                await page.wait_for_timeout(3000)

            state = await context.storage_state()
            await browser.close()

            state_json = json.dumps(state)
            logger.info("Login succeeded — %d cookies captured", len(state.get("cookies", [])))
            return state_json

    except Exception as exc:
        logger.error("Login flow failed: %s", exc)
        return None


def _run_single_test(
    *,
    run_id: str,
    result_id: str,
    test_name: str,
    test_code: str,
    target_url: str,
    browser: str,
    storage_state_json: str | None,
    artifacts_dir: str,
) -> tuple[str | None, bool]:
    """
    Run one test via Playwright executor.
    Returns (captured_auth_state, passed).
    """
    _publish(run_id, {"event": "started", "result_id": result_id, "test_name": test_name})
    logger.info("Running '%s' via Playwright", test_name)

    if not test_code or not test_code.strip():
        _patch_result(run_id, result_id, {
            "status": "failed",
            "error_message": "No test code — click 'Generate & Run' to generate Playwright code first.",
        })
        _publish(run_id, {"event": "finished", "result_id": result_id, "status": "failed"})
        return None, False

    try:
        result = asyncio.run(run_playwright_test(
            test_code=test_code,
            test_name=test_name,
            target_url=target_url,
            browser_type=browser,
            storage_state_json=storage_state_json,
            artifacts_dir=artifacts_dir,
            capture_auth_state=True,
        ))

        try:
            artifact_urls = upload_run_artifacts(
                run_id=run_id,
                result_id=result_id,
                video_path=result.video_path,
                screenshot_path=result.screenshot_path,
                trace_path=result.trace_path,
                console_logs=result.console_logs,
            )
        except Exception as exc:
            logger.error("Artifact upload failed: %s", exc)
            artifact_urls = {}

        for line in result.console_logs:
            _publish(run_id, {"event": "log", "result_id": result_id, "line": line})

        _patch_result(run_id, result_id, {
            "status": result.status,
            "error_message": result.error_message,
            "duration_ms": result.duration_ms,
            "video_url": artifact_urls.get("video_url"),
            "log_url": artifact_urls.get("log_url"),
            "trace_url": artifact_urls.get("trace_url"),
        })
        _publish(run_id, {"event": "finished", "result_id": result_id, "status": result.status})
        logger.info("'%s' → %s (%dms)", test_name, result.status, result.duration_ms)

        return result.captured_auth_state, result.status == "passed"

    except Exception as exc:
        logger.exception("Unexpected error running '%s'", test_name)
        _patch_result(run_id, result_id, {
            "status": "failed",
            "error_message": f"Worker error: {exc}",
        })
        _publish(run_id, {"event": "error", "result_id": result_id, "message": str(exc)})
        return None, False


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="runner.run_test", bind=True, max_retries=0, acks_late=True)
def run_test_task(
    self,
    run_id: str,
    result_id: str,
    test_code: str,
    test_name: str,
    target_url: str,
    browser: str = "chromium",
    storage_state_json: str | None = None,
    **kwargs,  # absorb any legacy params
):
    """Run a single test in isolation."""
    artifacts_dir = tempfile.mkdtemp(prefix=f"bug0_{run_id[:8]}_")
    try:
        _run_single_test(
            run_id=run_id,
            result_id=result_id,
            test_name=test_name,
            test_code=test_code,
            target_url=target_url,
            browser=browser,
            storage_state_json=storage_state_json,
            artifacts_dir=artifacts_dir,
        )
    finally:
        shutil.rmtree(artifacts_dir, ignore_errors=True)


@celery_app.task(name="runner.run_suite_sequential", bind=True, max_retries=0, acks_late=True)
def run_suite_sequential(
    self,
    run_id: str,
    suite_id: str,
    tests: list[dict],
    target_url: str,
    browser: str = "chromium",
    initial_storage_state: str | None = None,
    login_url: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    **kwargs,  # absorb any legacy params
):
    """
    Run all suite tests sequentially via Playwright, sharing auth state.

    If the suite has login config and no cached session, logs in once
    before the first test and saves the session. All tests start
    already authenticated — no login steps needed in individual tests.
    """
    logger.info("Suite run %s — %d tests (suite=%s)", run_id, len(tests), suite_id)

    current_auth_state: str | None = initial_storage_state
    any_failed = False

    # ── Step 1: Ensure auth session ──────────────────────────────────────────
    if current_auth_state is None and login_url and login_email and login_password:
        _publish(run_id, {
            "event": "log",
            "line": f"[info] Logging in to {login_url} before running tests…",
        })
        login_state = asyncio.run(_run_login_flow(login_url, login_email, login_password))
        if login_state:
            current_auth_state = login_state
            if suite_id:
                _save_suite_auth_state(suite_id, login_state)
            _publish(run_id, {"event": "log", "line": "[info] Login successful — session shared across all tests"})
        else:
            _publish(run_id, {"event": "log", "line": "[warning] Login failed — tests will run without auth"})

    # ── Step 2: Run tests sequentially ───────────────────────────────────────
    for i, test in enumerate(tests):
        result_id = test["result_id"]
        test_name = test["test_name"]
        test_code = test.get("test_code", "")

        artifacts_dir = tempfile.mkdtemp(prefix=f"bug0_{run_id[:8]}_t{i}_")
        try:
            _publish(run_id, {
                "event": "test_start",
                "result_id": result_id,
                "test_name": test_name,
                "test_index": i,
                "test_count": len(tests),
                "has_auth": current_auth_state is not None,
            })

            captured, passed = _run_single_test(
                run_id=run_id,
                result_id=result_id,
                test_name=test_name,
                test_code=test_code,
                target_url=target_url,
                browser=browser,
                storage_state_json=current_auth_state,
                artifacts_dir=artifacts_dir,
            )

            if not passed:
                any_failed = True

            # Pass auth state forward to next test
            if captured:
                current_auth_state = captured
                logger.info("Auth state captured after '%s'", test_name)

        except Exception as exc:
            any_failed = True
            logger.exception("Suite error on test '%s': %s", test_name, exc)
        finally:
            shutil.rmtree(artifacts_dir, ignore_errors=True)

    final_status = "failed" if any_failed else "passed"
    _publish(run_id, {"event": "run_finished", "status": final_status})
    logger.info("Suite run %s complete — %s", run_id, final_status)
