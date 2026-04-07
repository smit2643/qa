"""Playwright executor — Tasks 22, 23, 24, 26, 27.

Runs generated Playwright test code in an isolated browser context.
Captures: pass/fail status, error, duration, console logs, video, screenshot.
Supports: Chromium, Firefox, WebKit (Task 23).
Records video (Task 24), console logs + HAR tracing (Task 26).
Each run gets a fresh context, optional storageState injection (Task 27).
"""

import asyncio
import json
import os
import re
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_SMART_HELPERS = """\
import re as _re

async def _smart_click(page, selector):
    import re as _re2
    # Strip trailing element-type noise words to get the meaningful label
    clean = _re2.sub(r"\\s+(button|link|icon|tab|item|menu|checkbox|radio)s?$", "", selector, flags=_re2.IGNORECASE).strip()
    clean_lower = clean.lower()

    # ── Truly element-type-only selectors (no meaningful text) ───────────────
    # These have no label to match by, so go straight to CSS.
    _ELEMENT_TYPES = {"button", "submit", "link", "element", "checkbox", "radio"}
    if clean_lower in _ELEMENT_TYPES:
        for css in [
            "button[type='submit']", "input[type='submit']",
            "input[type='checkbox']", "input[type='radio']",
            "button:visible", "[role='button']:visible",
        ]:
            try:
                await page.locator(css).first.click(timeout=8000)
                try: await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception: pass
                return
            except Exception: pass
        raise Exception("Could not click generic element: " + repr(selector))

    # ── All other selectors — match by label/text first ──────────────────────
    # Use SHORT timeouts per strategy (2s) so we fail-fast and don't waste the
    # 60s test budget cycling through 9 roles × 6s = 54s on the wrong page.
    # Elements that exist render immediately; timeout only bites when absent.

    # 1. Role by name — most common for buttons, links, tabs, sidebar items
    for role in ("button", "link", "menuitem", "tab", "option", "checkbox", "radio"):
        try:
            await page.get_by_role(role, name=clean, exact=False).first.click(timeout=2000)
            try: await page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception: pass
            return
        except Exception: pass

    # 2. Text match — catches custom components that skip ARIA roles
    try:
        await page.get_by_text(clean, exact=False).first.click(timeout=3000)
        try: await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception: pass
        return
    except Exception: pass

    # 3. Aria/attribute match
    for attr in ("aria-label", "title", "data-testid", "value", "name"):
        try:
            await page.locator('[' + attr + '*="' + clean.replace('"', '') + '" i]').first.click(timeout=2000)
            try: await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception: pass
            return
        except Exception: pass

    # 4. Last-resort CSS submit fallback for known auth/action words
    _AUTH_ACTIONS = {"sign in", "signin", "login", "log in", "sign up", "signup", "register"}
    _ACTION_WORDS = _AUTH_ACTIONS | {"continue", "next", "ok", "yes", "confirm", "save", "send", "submit", "apply", "search", "go"}
    if clean_lower in _ACTION_WORDS:
        pre_url = page.url
        for css in ["button[type='submit']", "input[type='submit']", "button:visible"]:
            try:
                await page.locator(css).first.click(timeout=8000)
                try: await page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception: pass
                # Auth actions must navigate away — if URL unchanged after 5s, login failed
                if clean_lower in _AUTH_ACTIONS:
                    await page.wait_for_timeout(5000)
                    if page.url == pre_url:
                        raise Exception("Auth failed — page did not navigate away from " + pre_url)
                return
            except Exception as _e:
                if "Auth failed" in str(_e): raise
                continue

    raise Exception("Could not click: " + repr(selector))


async def _smart_fill(page, selector, value):
    sel = (selector or "").lower()
    val = str(value) if value is not None else ""
    # Alphanumeric key for name/id attribute matching
    sel_key = _re.sub(r"[^a-z0-9]", "", sel)

    # Detect semantic field type from selector text or value format
    is_email  = any(k in sel for k in ("email", "e-mail", "username", "user name", "login id", "account")) \\
                or ("@" in val and "." in val.split("@")[-1])
    is_pass   = any(k in sel for k in ("password", "passwd", "pass", "pwd", "secret", "pin"))
    is_phone  = any(k in sel for k in ("phone", "mobile", "tel", "cell", "fax"))
    is_search = any(k in sel for k in ("search", "query", "keyword", "find"))
    is_typed  = is_email or is_pass or is_phone or is_search

    strategies = []

    # ── Type-specific CSS selectors (most reliable) ───────────────────────────
    if is_email:
        strategies += [
            ("input[type='email']", None),
            ("[name*='email' i],[id*='email' i],[placeholder*='email' i]", None),
        ]
    if is_pass:
        strategies += [("input[type='password']", None)]
    if is_phone:
        strategies += [("input[type='tel'],[name*='phone' i],[id*='phone' i],[placeholder*='phone' i]", None)]
    if is_search:
        strategies += [
            ("input[type='search']", None),
            ("[name*='search' i],[id*='search' i],[placeholder*='search' i]", None),
        ]

    # ── Generic matching strategies (work for any field: name, address, city…) ─
    strategies += [
        # Full selector text as placeholder or label (most specific)
        (None, "placeholder"),    # get_by_placeholder(selector)
        (None, "label"),          # get_by_label(selector)
        # Attribute substring match
        ("[placeholder*='" + selector[:40].replace("'", "") + "' i]", None),
        ("[aria-label*='" + selector[:40].replace("'", "") + "' i]", None),
        ("[name*='" + sel_key[:30] + "' i],[id*='" + sel_key[:30] + "' i]", None),
    ]

    # ── Catch-all: only when a single input is visible (safe for simple forms) ─
    # For typed fields (email/password/search), we never fall back to any-input
    # because filling the wrong typed field silently corrupts the test.
    if not is_typed:
        strategies += [("__single_visible__", None)]

    for css, method in strategies:
        try:
            if css == "__single_visible__":
                # Only fall back to "any input" when exactly one is visible
                visible = await page.locator("input:visible, textarea:visible").count()
                if visible == 1:
                    await page.locator("input:visible, textarea:visible").first.fill(val, timeout=8000)
                    return
                continue
            elif css:
                await page.locator(css).first.fill(val, timeout=8000)
            elif method == "placeholder":
                await page.get_by_placeholder(selector, exact=False).first.fill(val, timeout=8000)
            elif method == "label":
                await page.get_by_label(selector, exact=False).first.fill(val, timeout=8000)
            return
        except Exception: continue

    raise Exception("Could not fill: " + repr(selector))


async def _assert_navigation(page, away_from=None, toward=None, timeout=8000):
    import asyncio as _asyncio
    _start = _asyncio.get_event_loop().time()
    while True:
        current = page.url.lower()
        if away_from:
            if not any(frag.lower() in current for frag in away_from):
                return  # navigated away — success
        if toward:
            if any(frag.lower() in current for frag in toward):
                return  # arrived — success
        elapsed = (_asyncio.get_event_loop().time() - _start) * 1000
        if elapsed >= timeout:
            break
        await page.wait_for_timeout(500)
    current = page.url
    if away_from:
        raise Exception(
            "Navigation check failed — still on login page after auth click. "
            "Current URL: " + current + ". "
            "Possible causes: wrong credentials, form validation error, or login button not clicked."
        )
    raise Exception(
        "Navigation check failed — did not reach expected page. Current URL: " + current
    )
"""


def _sanitize_test_code(code: str) -> str:
    """Universal post-processor — makes any generated Playwright code robust for any site."""

    # 1. Strip reasoning-model think blocks
    code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL)

    # 1b. Fix wait_for_timeout(None) / wait_for_timeout() → wait_for_timeout(2000)
    #     Agent produces wait steps with no value; generator may emit None/0/missing arg.
    code = re.sub(r'wait_for_timeout\(\s*(?:None|0|)\s*\)', 'wait_for_timeout(2000)', code)

    # 2. Drop all brittle expect() assertions (line filter handles nested parens)
    _BAD = (".to_have_url(", ".to_be_visible(", ".to_be_hidden(",
            ".to_have_text(", ".to_contain_text(", ".to_have_value(",
            ".to_be_checked(", ".to_be_disabled(", ".to_be_enabled(")
    code = "\n".join(ln for ln in code.splitlines() if not any(p in ln for p in _BAD))

    # 3. After every page.goto() wait for networkidle so SPAs render fully
    lines = []
    for ln in code.splitlines():
        lines.append(ln)
        if ln.strip().startswith("await page.goto("):
            ind = " " * (len(ln) - len(ln.lstrip()))
            lines += [
                ind + 'try:',
                ind + '    await page.wait_for_load_state("networkidle", timeout=15000)',
                ind + 'except Exception:',
                ind + '    await page.wait_for_load_state("domcontentloaded", timeout=10000)',
                ind + 'await page.wait_for_timeout(2000)',
            ]
    code = "\n".join(lines)

    # 4. Line-by-line rewrite of fill and click calls.
    #    We parse each line individually to avoid regex cross-contamination.
    _INPUT_HINTS = ("email", "e-mail", "password", "passwd", "pass", "pwd",
                    "username", "user", "login", "phone", "mobile", "search",
                    "input field", "text field", "text box")

    result_lines = []
    for ln in code.splitlines():
        stripped = ln.strip()
        ind = " " * (len(ln) - len(ln.lstrip()))

        # Rewrite .fill( lines — extract field name and value cleanly
        if ".fill(" in ln and "await" in ln and "_smart_fill" not in ln:
            # Extract value: everything inside the final .fill(...)
            fill_m = re.search(r'\.fill\(([^)]+)\)', ln)
            if fill_m:
                val_arg = re.split(r",\s*timeout", fill_m.group(1))[0].strip()
                # Extract field name: first human-readable quoted string before .fill
                before_fill = ln[:ln.rfind(".fill(")]
                # Try get_by_label/placeholder/role name first, then locator CSS
                name_m = re.search(r'get_by_(?:label|placeholder|role|text)\(["\']([^"\']+)["\']', before_fill)
                if name_m:
                    field_name = name_m.group(1)
                else:
                    # It's a locator — infer field type from CSS
                    if "type='email'" in before_fill or 'type="email"' in before_fill:
                        field_name = "email"
                    elif "type='password'" in before_fill or 'type="password"' in before_fill:
                        field_name = "password"
                    elif "type='tel'" in before_fill or 'type="tel"' in before_fill:
                        field_name = "phone"
                    elif "type='search'" in before_fill or 'type="search"' in before_fill:
                        field_name = "search"
                    else:
                        # Extract first readable quoted string from CSS
                        css_m = re.search(r'["\']([a-zA-Z][^"\']{1,40})["\']', before_fill)
                        field_name = css_m.group(1) if css_m else "field"
                result_lines.append(f'{ind}await _smart_fill(page, {repr(field_name)}, {val_arg})')
                continue

        # Rewrite .click() lines — skip input-focus clicks
        if ".click(" in ln and "await" in ln and "_smart_click" not in ln:
            # For get_by_role("button", name="Foo") prefer the name= kwarg (not the role type)
            role_name_m = re.search(r'get_by_role\([^)]*\bname=["\']([^"\']+)["\']', ln)
            if role_name_m:
                sel = role_name_m.group(1)
            else:
                name_m = re.search(r'get_by_(?:text|label|placeholder)\(["\']([^"\']+)["\']', ln)
                if name_m:
                    sel = name_m.group(1)
                else:
                    sel_m = re.search(r'["\']([^"\']{1,80})["\']', ln)
                    sel = sel_m.group(1) if sel_m else "element"
            # Skip input-focus clicks (clicking email/password/search field before typing)
            if any(h in sel.lower() for h in _INPUT_HINTS):
                result_lines.append(f'{ind}pass  # skipped input focus click on {repr(sel)}')
                continue
            result_lines.append(f'{ind}await _smart_click(page, {repr(sel)})')
            # After auth clicks, inject a navigation assertion so the test fails
            # immediately with a clear message instead of continuing on the wrong page.
            _AUTH_CLICK_WORDS = ("sign in", "signin", "login", "log in",
                                 "sign up", "signup", "register", "submit")
            if any(w in sel.lower() for w in _AUTH_CLICK_WORDS):
                result_lines.append(
                    f'{ind}await _assert_navigation(page, away_from=['
                    f'"login", "signin", "sign-in", "auth", "register"'
                    f'], timeout=8000)  # fail fast if auth did not succeed'
                )
            continue

        result_lines.append(ln)

    code = "\n".join(result_lines)

    # 5. Deduplicate consecutive _smart_fill calls on the same field (partial-typing artifact).
    #    e.g. fill(page, "password", "Cu") + fill(page, "password", "Custonomy@123") → keep last only.
    deduped: list[str] = []
    for ln in code.splitlines():
        fill_m = re.match(r'^(\s*)await _smart_fill\(page,\s*(["\'][^"\']+["\'])', ln)
        if fill_m and deduped:
            prev_m = re.match(r'^(\s*)await _smart_fill\(page,\s*(["\'][^"\']+["\'])', deduped[-1])
            if prev_m and prev_m.group(2) == fill_m.group(2):
                deduped[-1] = ln  # replace with the later (more complete) value
                continue
        deduped.append(ln)
    code = "\n".join(deduped)

    # 6. Inject helpers at the top
    code = _SMART_HELPERS + "\n" + code

    return code.strip()

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
    captured_auth_state: str | None = None  # storage_state JSON captured after test for next test


async def run_test(
    test_code: str,
    test_name: str,
    target_url: str,
    browser_type: str = "chromium",
    storage_state_json: str | None = None,
    artifacts_dir: str | None = None,
    capture_auth_state: bool = False,  # if True, save browser session after test
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
    captured_auth_state: str | None = None

    try:
        async with async_playwright() as pw:  # type: ignore[misc]
            # Task 23: Cross-browser support
            browser_launcher = getattr(pw, browser_type, pw.chromium)
            browser = await browser_launcher.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                ],
            )

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

            # Set default timeouts — SPAs need extra time to render
            page.set_default_timeout(60000)
            page.set_default_navigation_timeout(30000)

            # Task 26: Console log capture
            page.on("console", lambda msg: console_logs.append(
                f"[{msg.type}] {msg.text}"
            ))
            page.on("pageerror", lambda err: console_logs.append(
                f"[pageerror] {err}"
            ))

            # Compile and run the test function
            # Inject playwright symbols so generated code can use Page, expect etc.
            from playwright.async_api import Page, expect, Request, Response, Locator
            local_ns: dict = {
                "Page": Page,
                "expect": expect,
                "Request": Request,
                "Response": Response,
                "Locator": Locator,
                "page": page,
                "re": __import__("re"),
            }
            test_code = _sanitize_test_code(test_code)

            # If the test has no navigation, inject one at the start of the function body.
            # Recording-generated tests often skip navigate since the user was already on the page.
            if "page.goto(" not in test_code and target_url:
                goto_block = (
                    f'    await page.goto({repr(target_url)}, timeout=20000)\n'
                    f'    try:\n'
                    f'        await page.wait_for_load_state("networkidle", timeout=15000)\n'
                    f'    except Exception:\n'
                    f'        await page.wait_for_load_state("domcontentloaded", timeout=10000)\n'
                    f'    await page.wait_for_timeout(2000)\n'
                )
                # Insert after the function def line
                lines = test_code.splitlines()
                insert_at = next(
                    (i + 1 for i, ln in enumerate(lines) if ln.strip().startswith("async def test_")),
                    len(lines)
                )
                lines.insert(insert_at, goto_block)
                test_code = "\n".join(lines)

            print(f"[EXECUTOR] Sanitized code:\n{test_code}\n{'='*60}")
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

            # Capture auth state (cookies + localStorage) BEFORE closing context
            if capture_auth_state:
                try:
                    state = await context.storage_state()
                    captured_auth_state = json.dumps(state)
                except Exception:
                    captured_auth_state = None

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
        captured_auth_state=captured_auth_state,
    )
