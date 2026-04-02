"""Playwright executor — Tasks 22, 23, 24, 26, 27.

Runs generated Playwright test code in an isolated browser context.
Captures: pass/fail status, error, duration, console logs, video, screenshot.
Supports: Chromium, Firefox, WebKit (Task 23).
Records video (Task 24), console logs + HAR tracing (Task 26).
Each run gets a fresh context, optional storageState injection (Task 27).
"""

import asyncio
import os
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from playwright.async_api import async_playwright
except ImportError:  # playwright not installed in test env
    async_playwright = None  # type: ignore[assignment]


@dataclass
class ExecutionResult:
    status: str           # "passed" | "failed"
    error_message: str | None = None
    duration_ms: int = 0
    console_logs: list[str] = field(default_factory=list)
    video_path: str | None = None        # local path to .webm video
    screenshot_path: str | None = None  # local path to final PNG screenshot
    trace_path: str | None = None        # local path to playwright trace.zip


async def run_test(
    test_code: str,
    test_name: str,
    target_url: str,
    browser_type: str = "chromium",
    storage_state_json: str | None = None,
    artifacts_dir: str | None = None,
) -> ExecutionResult:
    """
    Execute test_code in an isolated Playwright browser context.

    test_code must define an async function whose name starts with 'test_'.
    Example:
        async def test_login(page):
            await page.goto('https://example.com')
            await page.get_by_role('button', name='Login').click()
    """
    if artifacts_dir is None:
        artifacts_dir = tempfile.mkdtemp(prefix="bug0_run_")

    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)

    # Write storageState to temp file if provided (Task 27)
    storage_file = None
    if storage_state_json:
        storage_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=artifacts_dir
        )
        storage_file.write(storage_state_json)
        storage_file.close()

    console_logs: list[str] = []
    video_path: str | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None

    try:
        async with async_playwright() as pw:  # type: ignore[misc]
            # Task 23: Cross-browser support
            browser_launcher = getattr(pw, browser_type, pw.chromium)
            browser = await browser_launcher.launch(headless=True)

            # Task 24: Video recording + Task 27: Fresh context per run
            context_opts: dict[str, Any] = {
                "record_video_dir": str(artifacts_path / "video"),
            }
            if storage_file:
                context_opts["storage_state"] = storage_file.name

            context = await browser.new_context(**context_opts)

            # Task 26: Playwright tracing (screenshots + snapshots)
            await context.tracing.start(screenshots=True, snapshots=True)

            page = await context.new_page()

            # Task 26: Console log capture
            page.on("console", lambda msg: console_logs.append(
                f"[{msg.type}] {msg.text}"
            ))
            page.on("pageerror", lambda err: console_logs.append(
                f"[pageerror] {err}"
            ))

            # Compile and run the test function
            local_ns: dict = {}
            exec(compile(test_code, "<test>", "exec"), local_ns)  # noqa: S102

            test_fn = None
            for name, obj in local_ns.items():
                if callable(obj) and name.startswith("test_"):
                    test_fn = obj
                    break

            if test_fn is None:
                return ExecutionResult(
                    status="failed",
                    error_message="No test function found. Function must start with 'test_'.",
                )

            start = time.monotonic()
            try:
                await test_fn(page)
                status = "passed"
                error_message = None
            except Exception as exc:
                status = "failed"
                error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            finally:
                duration_ms = int((time.monotonic() - start) * 1000)

            # Capture final screenshot
            try:
                screenshot_path = str(artifacts_path / "screenshot.png")
                await page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                screenshot_path = None

            # Save trace (Task 26)
            try:
                trace_path = str(artifacts_path / "trace.zip")
                await context.tracing.stop(path=trace_path)
            except Exception:
                trace_path = None

            await context.close()

            # Video is finalized on context.close() (Task 24)
            video_dir = artifacts_path / "video"
            if video_dir.exists():
                webm_files = list(video_dir.glob("*.webm"))
                if webm_files:
                    video_path = str(webm_files[0])

            await browser.close()

    except Exception as exc:
        return ExecutionResult(
            status="failed",
            error_message=f"Executor error: {exc}\n{traceback.format_exc()}",
            console_logs=console_logs,
        )
    finally:
        if storage_file and os.path.exists(storage_file.name):
            os.unlink(storage_file.name)

    return ExecutionResult(
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
        console_logs=console_logs,
        video_path=video_path,
        screenshot_path=screenshot_path,
        trace_path=trace_path,
    )
