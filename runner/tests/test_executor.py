"""Unit tests for the Playwright executor — Tasks 22–27."""

import asyncio
import sys
import os

# Allow importing runner modules without the full backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# ExecutionResult shape
# ---------------------------------------------------------------------------

def test_execution_result_defaults():
    from runner.executor.playwright_executor import ExecutionResult
    r = ExecutionResult(status="passed")
    assert r.status == "passed"
    assert r.error_message is None
    assert r.duration_ms == 0
    assert r.console_logs == []
    assert r.video_path is None
    assert r.screenshot_path is None


# ---------------------------------------------------------------------------
# Executor — passed test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_test_passed():
    """Passing test returns status=passed with populated fields."""
    from runner.executor.playwright_executor import run_test

    test_code = "async def test_example(page):\n    pass\n"

    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.screenshot = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.tracing = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_browser_launcher = AsyncMock()
    mock_browser_launcher.launch = AsyncMock(return_value=mock_browser)

    mock_pw = MagicMock()
    mock_pw.chromium = mock_browser_launcher
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)

    with patch("runner.executor.playwright_executor.async_playwright", return_value=mock_pw):
        result = await run_test(
            test_code=test_code,
            test_name="test_example",
            target_url="https://example.com",
            browser_type="chromium",
        )

    assert result.status == "passed"
    assert result.error_message is None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_run_test_failed():
    """Test that raises an exception returns status=failed with error_message."""
    from runner.executor.playwright_executor import run_test

    test_code = (
        "async def test_fail(page):\n"
        "    raise AssertionError('element not found')\n"
    )

    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.screenshot = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.tracing = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_browser_launcher = AsyncMock()
    mock_browser_launcher.launch = AsyncMock(return_value=mock_browser)

    mock_pw = MagicMock()
    mock_pw.chromium = mock_browser_launcher
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)

    with patch("runner.executor.playwright_executor.async_playwright", return_value=mock_pw):
        result = await run_test(
            test_code=test_code,
            test_name="test_fail",
            target_url="https://example.com",
        )

    assert result.status == "failed"
    assert "AssertionError" in result.error_message
    assert "element not found" in result.error_message


@pytest.mark.asyncio
async def test_run_test_no_function_returns_failed():
    """Code with no test_ function returns status=failed."""
    from runner.executor.playwright_executor import run_test

    mock_page = AsyncMock()
    mock_page.on = MagicMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.tracing = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_browser_launcher = AsyncMock()
    mock_browser_launcher.launch = AsyncMock(return_value=mock_browser)

    mock_pw = MagicMock()
    mock_pw.chromium = mock_browser_launcher
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)

    with patch("runner.executor.playwright_executor.async_playwright", return_value=mock_pw):
        result = await run_test(
            test_code="x = 1  # no test function",
            test_name="empty",
            target_url="https://example.com",
        )

    assert result.status == "failed"
    assert "No test function found" in result.error_message


# ---------------------------------------------------------------------------
# Cross-browser (Task 23)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_test_uses_specified_browser():
    """Browser type is passed to Playwright correctly."""
    from runner.executor.playwright_executor import run_test

    test_code = "async def test_x(page):\n    pass\n"

    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.screenshot = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.tracing = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_firefox = AsyncMock()
    mock_firefox.launch = AsyncMock(return_value=mock_browser)

    mock_pw = MagicMock()
    mock_pw.firefox = mock_firefox
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)

    with patch("runner.executor.playwright_executor.async_playwright", return_value=mock_pw):
        result = await run_test(
            test_code=test_code,
            test_name="test_x",
            target_url="https://example.com",
            browser_type="firefox",
        )

    mock_firefox.launch.assert_called_once_with(headless=True)
    assert result.status == "passed"


# ---------------------------------------------------------------------------
# Visual diff (Task 25)
# ---------------------------------------------------------------------------

def test_diff_screenshots_identical_images():
    from runner.executor.recorder import diff_screenshots
    import io
    from PIL import Image

    # Create two identical 10x10 red images
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    result = diff_screenshots(png_bytes, png_bytes)
    assert result.diff_percentage == 0.0
    assert result.diff_pixel_count == 0


def test_diff_screenshots_different_images():
    from runner.executor.recorder import diff_screenshots
    import io
    from PIL import Image

    # Red image vs blue image — all pixels differ
    img_a = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    img_b = Image.new("RGBA", (10, 10), (0, 0, 255, 255))

    buf_a = io.BytesIO()
    img_a.save(buf_a, format="PNG")
    buf_b = io.BytesIO()
    img_b.save(buf_b, format="PNG")

    result = diff_screenshots(buf_a.getvalue(), buf_b.getvalue())
    assert result.diff_percentage > 0
    assert result.diff_pixel_count > 0
    assert len(result.diff_image_bytes) > 0


# ---------------------------------------------------------------------------
# Artifact uploader (Task 29) — mock boto3
# ---------------------------------------------------------------------------

def test_upload_run_artifacts_skips_missing_files():
    from runner.storage.artifact_uploader import upload_run_artifacts

    # With no real files, upload should not crash and return None URLs
    with patch("runner.storage.artifact_uploader.get_s3_client") as mock_s3:
        urls = upload_run_artifacts(
            run_id="run-123",
            result_id="result-456",
            video_path="/nonexistent/video.webm",
            screenshot_path=None,
            trace_path=None,
            console_logs=None,
        )

    # Missing file — no upload, URL is None
    assert urls["video_url"] is None
    mock_s3.assert_not_called()


def test_upload_bytes_returns_url():
    from runner.storage.artifact_uploader import upload_bytes

    mock_s3 = MagicMock()
    mock_s3.upload_fileobj = MagicMock()
    mock_s3.head_bucket = MagicMock()

    with patch("runner.storage.artifact_uploader.get_s3_client", return_value=mock_s3):
        url = upload_bytes(
            b"hello logs",
            "runs/r1/console.log",
            "text/plain",
            bucket="bug0-artifacts",
        )

    assert "runs/r1/console.log" in url
    mock_s3.upload_fileobj.assert_called_once()
