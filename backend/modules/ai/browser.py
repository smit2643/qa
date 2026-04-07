"""Browser module — uses browser-use Agent to autonomously navigate apps and record real actions."""

import base64
import json
import logging
import os
import re
import tempfile
from typing import Any

from core.config import settings
from modules.ai.llm import LLMProvider

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 5


# ---------------------------------------------------------------------------
# Step extraction from browser-use AgentHistoryList
# ---------------------------------------------------------------------------

def extract_steps_from_history(history: Any) -> list[dict]:
    """
    Convert browser-use AgentHistoryList into our standard step format:
    [{"order": int, "action": str, "selector": str|None, "value": str|None, "description": str}]

    browser-use action names map to our actions:
      go_to_url / open_tab     → navigate
      click_element            → click
      input_text               → type
      scroll                   → wait (ignored in most cases)
      extract_content          → assert
      done                     → skipped
    """
    steps = []
    order = 0

    for action_dict in history.model_actions():
        action_dict = dict(action_dict)
        action_dict.pop("interacted_element", None)

        if not action_dict:
            continue

        action_name = list(action_dict.keys())[0]
        action_params = action_dict.get(action_name) or {}

        step = _map_action(action_name, action_params, order)
        if step:
            steps.append(step)
            order += 1

    from modules.extraction.normalizer import normalize_steps
    return normalize_steps(steps)


def _map_action(action_name: str, params: dict, order: int) -> dict | None:
    """Map a single browser-use action to our step format."""

    if action_name in ("go_to_url", "open_tab"):
        url = params.get("url") or params.get("url_or_text", "")
        return {
            "order": order,
            "action": "navigate",
            "selector": None,
            "value": str(url),
            "description": f"Navigate to {url}",
        }

    elif action_name in ("click_element", "click_element_by_index", "click"):
        selector = _extract_selector(params)
        return {
            "order": order,
            "action": "click",
            "selector": selector,
            "value": None,
            "description": f"Click {selector or 'element'}",
        }

    elif action_name in ("input_text", "type", "fill"):
        selector = _extract_selector(params)
        value = params.get("text") or params.get("value") or params.get("input_text", "")
        return {
            "order": order,
            "action": "type",
            "selector": selector,
            "value": str(value),
            "description": f"Type '{value}' into {selector or 'field'}",
        }

    elif action_name in ("extract_content", "get_text"):
        selector = _extract_selector(params)
        return {
            "order": order,
            "action": "assert",
            "selector": selector,
            "value": params.get("goal") or params.get("content", ""),
            "description": f"Assert {selector or 'content'} is visible",
        }

    elif action_name in ("wait", "sleep"):
        ms = int(params.get("seconds", 1) * 1000) if params.get("seconds") else 1000
        return {
            "order": order,
            "action": "wait",
            "selector": None,
            "value": str(ms),
            "description": f"Wait {ms}ms",
        }

    elif action_name == "done":
        return None  # terminal action, skip

    else:
        # Unknown action — include as a generic step so nothing is lost
        return {
            "order": order,
            "action": "wait",
            "selector": None,
            "value": "500",
            "description": f"{action_name}: {json.dumps(params)[:100]}",
        }


def _extract_selector(params: dict) -> str | None:
    """Extract the best human-readable selector from action params."""
    for key in ("element_description", "selector", "xpath", "css", "text", "label", "name"):
        val = params.get(key)
        if val:
            return str(val)

    # browser-use passes interacted_element separately — already stripped
    # Try index as last resort
    idx = params.get("index")
    if idx is not None:
        return f"element[{idx}]"

    return None


# ---------------------------------------------------------------------------
# Custom agent — action executor
# ---------------------------------------------------------------------------

def _normalize_selector(selector: str | None) -> str | None:
    """
    Strip Playwright/CSS selector prefixes the LLM sometimes generates.
    e.g. "text=Learn more" → "Learn more", "css=.btn" → ".btn"
    """
    if not selector:
        return selector
    for prefix in ("text=", "css=", "xpath=", "id=", "role=", "label=", "placeholder=", "testid="):
        if selector.startswith(prefix):
            return selector[len(prefix):]
    return selector


async def _execute_action(page: Any, action: dict) -> tuple[bool, str | None]:
    """
    Execute a single LLM-decided action in the Playwright page.
    Returns (success, error_message).
    """
    from playwright.async_api import expect as pw_expect

    act = action.get("action", "")
    raw_selector = action.get("selector")        # original from LLM
    selector = _normalize_selector(raw_selector) # stripped of prefix
    value = action.get("value") or ""

    try:
        if act == "navigate":
            await page.goto(value, timeout=15000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        elif act == "click":
            if not selector:
                raise Exception("click action requires a selector")
            initial_url = page.url
            clicked = False
            # 1. Try semantic roles with normalized text
            for role in ("link", "button", "menuitem", "tab"):
                try:
                    await page.get_by_role(role, name=selector, exact=False).first.click(timeout=3000)
                    clicked = True
                    break
                except Exception:
                    # Even if timed-out, the click may have already fired (navigation started)
                    if page.url != initial_url:
                        clicked = True
                        break
                    continue
            # 2. Try get_by_text with normalized selector
            if not clicked:
                try:
                    await page.get_by_text(selector, exact=False).first.click(timeout=3000)
                    clicked = True
                except Exception:
                    if page.url != initial_url:
                        clicked = True
            # 3. Try raw Playwright locator (handles "text=...", "css=..." if LLM included the prefix)
            if not clicked and raw_selector and raw_selector != selector:
                try:
                    await page.locator(raw_selector).first.click(timeout=3000)
                    clicked = True
                except Exception:
                    if page.url != initial_url:
                        clicked = True
            # 4. Try the selector as a direct CSS/XPath locator (e.g. input[placeholder='...'])
            if not clicked:
                try:
                    await page.locator(selector).first.click(timeout=3000)
                    clicked = True
                except Exception:
                    if page.url != initial_url:
                        clicked = True
            # 5. Final fallback: check if navigation already happened despite reported failure
            if not clicked and page.url != initial_url:
                clicked = True
            if not clicked:
                raise Exception(f"Could not find clickable element: {selector!r}")
            # Wait for page to settle after click/navigation
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=8000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass  # page may already be stable

        elif act == "type":
            if not selector:
                raise Exception("type action requires a selector")
            filled = False

            # Detect semantic input type from selector/value hints
            sel_lower = (selector or "").lower()
            val_lower = (value or "").lower()
            is_email_field = any(k in sel_lower for k in ("email", "e-mail", "username", "user", "login", "account"))
            is_password_field = any(k in sel_lower for k in ("password", "passwd", "pass", "pwd", "secret"))
            # Also infer from value format
            if not is_email_field and "@" in value and "." in value.split("@")[-1]:
                is_email_field = True

            # Build ordered list of locator strategies
            locator_fns: list = []

            # Semantic type-based locators first (most reliable)
            if is_email_field:
                locator_fns += [
                    lambda: page.locator("input[type='email']").first.fill(value, timeout=3000),
                    lambda: page.locator("input[name*='email'], input[id*='email'], input[placeholder*='email' i]").first.fill(value, timeout=3000),
                ]
            if is_password_field:
                locator_fns += [
                    lambda: page.locator("input[type='password']").first.fill(value, timeout=3000),
                ]

            # Generic strategies using selector text
            locator_fns += [
                lambda: page.get_by_label(selector, exact=False).fill(value, timeout=3000),
                lambda: page.get_by_placeholder(selector, exact=False).fill(value, timeout=3000),
                lambda: page.get_by_role("textbox", name=selector, exact=False).fill(value, timeout=3000),
                lambda: page.locator(f"input[name*='{selector}' i], input[id*='{selector}' i]").first.fill(value, timeout=3000),
                lambda: page.locator("input:visible, textarea:visible").first.fill(value, timeout=3000),
            ]

            for attempt_fn in locator_fns:
                try:
                    await attempt_fn()
                    filled = True
                    break
                except Exception:
                    continue
            if not filled:
                raise Exception(f"Could not find input field: {selector!r}")

        elif act == "assert":
            check = value or selector or ""
            await pw_expect(page.get_by_text(check, exact=False)).to_be_visible(timeout=5000)

        elif act == "wait":
            ms = int(value) if value and str(value).isdigit() else 1000
            await page.wait_for_timeout(ms)

        elif act == "scroll":
            direction = str(value).lower().strip() if value else "down"
            delta = 600 if direction == "down" else -600
            await page.evaluate(f"window.scrollBy(0, {delta})")
            await page.wait_for_timeout(500)

        elif act == "done":
            pass  # terminal — caller handles break

        else:
            pass  # unknown action — skip silently

        return True, None

    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Custom agent — main loop (Ollama vision)
# ---------------------------------------------------------------------------

_AGENT_SYSTEM = """You are a browser automation agent. Complete every numbered step in the task EXACTLY ONCE, then stop.

STRICT RULES — violations cause test failures:
1. NEVER repeat a step you already completed. Each step happens once.
2. NEVER revisit a page you already visited unless the task explicitly says to go back.
3. NEVER re-fill a field you already filled successfully.
4. The moment you confirm the LAST step is done on screen, return {"action":"done"} immediately.
5. For login: type email → type password → click submit. That is 3 actions total, then move on.
6. For search: type directly into the search field (action="type"). Do NOT click the field first.
7. For sidebar/menu navigation: click the menu item TEXT as it appears on screen.
8. After clicking a button that submits/navigates, wait for the new page before acting again.
9. If the same action+selector has failed 2 times, use a different selector — do NOT keep retrying the same one.

JSON format (respond with ONE object only — no markdown, no <think> tags):
{"action": "click|type|navigate|assert|wait|done", "selector": "...", "value": "...", "description": "..."}

Action rules:
- "type": selector = field label/placeholder text, value = the COMPLETE text to enter. Use for ALL inputs.
- "click": selector = the EXACT visible text of the button, link, or menu item on screen.
- "navigate": value = full URL. Only when going to a URL directly.
- "wait": value = milliseconds (max 2000). Use after heavy page loads only.
- "scroll": value = "down" or "up". Use ONLY this action when the task says to scroll. Do NOT click random sections (Social Media, Consents, etc.) to simulate scrolling.
- "done": return this as soon as the final step is visibly complete on screen.

IMPORTANT: If the task has N steps, you should complete exactly those N steps and stop. Count your completed steps."""


_KNOWN_ACTIONS = {"click", "type", "navigate", "assert", "wait", "scroll", "done"}


async def _run_custom_agent(
    task: str,
    target_url: str,
    page: Any,
    max_steps: int = 15,
) -> tuple[list[dict], bool]:
    """Returns (steps, task_completed)."""
    """
    Custom vision-based agent loop for Ollama.
    Takes screenshots, asks the LLM what to do, executes actions.
    Returns steps in our standard format.
    """
    from modules.extraction.normalizer import normalize_steps

    llm = LLMProvider()
    step_history: list[dict] = []
    consecutive_failures = 0
    order = 0
    task_completed = False

    # Navigate to start URL first — record the final URL after any redirects
    try:
        await page.goto(target_url, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        # Extra wait for JS-heavy SPAs to render their forms
        await page.wait_for_timeout(2000)
        final_url = page.url  # may differ from target_url if redirected (e.g. /login)
        step_history.append({
            "order": order,
            "action": "navigate",
            "selector": None,
            "value": final_url,
            "description": f"Navigate to {final_url}",
        })
        order += 1
        logger.info("Navigated to %s (final: %s)", target_url, final_url)
    except Exception as exc:
        return [{"order": 0, "action": "navigate", "selector": None, "value": target_url,
                 "description": f"Navigate to {target_url} (failed: {exc})"}]

    last_error: str | None = None

    for _ in range(max_steps):
        # Take screenshot — JPEG q55 gives readable text without excessive payload
        try:
            screenshot_bytes = await page.screenshot(
                type="jpeg", quality=70,
                clip={"x": 0, "y": 0, "width": 1280, "height": 800},
                timeout=10000,
            )
        except Exception:
            try:
                screenshot_bytes = await page.screenshot(type="jpeg", quality=70, timeout=10000)
            except Exception as exc:
                logger.warning("Screenshot failed during agent loop: %s", exc)
                break

        img_b64 = base64.standard_b64encode(screenshot_bytes).decode()
        current_url = page.url

        # Last 3 steps only — enough context without bloating the prompt
        history_summary = json.dumps([
            {"action": s["action"], "selector": s.get("selector"), "description": s["description"]}
            for s in step_history[-3:]
        ], separators=(",", ":"))

        error_note = f"\nLast action FAILED: {last_error}. Try a different selector or approach." if last_error else ""

        steps_done = len(step_history)
        user_text = (
            f"TASK:\n{task}\n\n"
            f"Current URL: {current_url}\n"
            f"Actions completed so far ({steps_done}): {history_summary}{error_note}\n\n"
            f"Look at the screenshot carefully. Identify what the current page shows. "
            f"Then decide the SINGLE NEXT action needed to make progress toward completing the full task.\n"
            f"Do NOT say done unless every step in the task above is fully completed and visible on screen.\n"
            "Respond with ONE JSON object:"
        )

        # image_url content blocks are converted to Ollama's `images` array by _complete_ollama
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": user_text},
            ],
        }]

        # Ask LLM — retry once on JSON parse / HTTP failure
        action: dict = {}
        llm_failed = False
        for attempt in range(2):
            try:
                raw = await llm.complete(messages, system=_AGENT_SYSTEM)
                # Strip <think>...</think> blocks (qwen/deepseek reasoning models)
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
                # Strip code fences
                raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
                raw = re.sub(r"\n?```$", "", raw.rstrip())
                raw = raw.strip()
                # Handle bare "null" response
                if raw == "null" or not raw:
                    raise ValueError("LLM returned null/empty")
                # Extract first JSON object if extra text surrounds it
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    raw = json_match.group(0)
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError(f"Expected JSON object, got: {type(parsed)}")
                action = parsed
                print(f"[AGENT] step={order} action={action}")
                llm_failed = False
                break
            except Exception as exc:
                print(f"[AGENT] LLM call/parse failed attempt={attempt} err={exc}")
                if attempt == 0:
                    messages[-1]["content"][-1]["text"] += "\n\nRespond with a single JSON object ONLY. No extra text."
                else:
                    llm_failed = True

        # If LLM failed both attempts, count as consecutive failure but keep looping
        if llm_failed:
            consecutive_failures += 1
            last_error = "LLM call failed — retrying"
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[AGENT] Too many LLM failures, stopping. steps={len(step_history)}")
                break
            continue

        # Stop if agent explicitly signals done
        if action.get("action") == "done":
            print(f"[AGENT] Done signalled after {len(step_history)} steps")
            task_completed = True
            break

        # Guard: skip unknown actions without resetting consecutive_failures
        if action.get("action") not in _KNOWN_ACTIONS:
            consecutive_failures += 1
            last_error = f"Unknown action: {action.get('action')!r}"
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                break
            continue

        # Stuck detection — if same action+selector repeated 3 times, force error so agent changes approach
        recent = step_history[-3:] if len(step_history) >= 3 else []
        same_key = f"{action.get('action')}::{action.get('selector')}"
        recent_keys = [f"{s['action']}::{s.get('selector')}" for s in recent]
        if recent_keys.count(same_key) >= 3:
            consecutive_failures += 1
            last_error = f"Stuck: same action '{action.get('action')}' on '{action.get('selector')}' repeated 3 times. Try a different approach."
            print(f"[AGENT] Stuck detected — {same_key}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                break
            continue

        # Execute action
        success, error = await _execute_action(page, action)

        if success:
            consecutive_failures = 0
            last_error = None
            step = {
                "order": order,
                "action": action.get("action", "wait"),
                "selector": action.get("selector"),
                "value": action.get("value"),
                "description": action.get("description", ""),
            }
            step_history.append(step)
            order += 1
        else:
            consecutive_failures += 1
            last_error = error
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                break  # Stop gracefully

    # Post-process step_history:
    # 1. Remove "click to focus" steps — a click on an input field immediately
    #    before a type on the same/similar selector is just a focus event, not a test step.
    # 2. Deduplicate consecutive type steps — keep only the last (most complete value).
    cleaned: list[dict] = []
    for i, step in enumerate(step_history):
        # Check if this is a click-to-focus: click action where next step is type on same selector
        if step["action"] == "click":
            next_step = step_history[i + 1] if i + 1 < len(step_history) else None
            sel = (step.get("selector") or "").lower()
            # Skip if clicking on an input field name (email, password, etc.)
            _INPUT_HINTS = ("email", "password", "passwd", "username", "user", "input", "field", "phone", "search", "text box", "pwd")
            is_input_focus = any(h in sel for h in _INPUT_HINTS)
            # Skip if next step is type on same/similar selector
            next_is_type = next_step and next_step["action"] == "type"
            if is_input_focus or next_is_type:
                continue  # drop this click-to-focus step
        # Deduplicate consecutive type steps on same selector — keep last (most complete value)
        if (
            step["action"] == "type"
            and cleaned
            and cleaned[-1]["action"] == "type"
            and cleaned[-1].get("selector") == step.get("selector")
        ):
            cleaned[-1] = step
        else:
            cleaned.append(step)

    # Pass 2: Remove non-consecutive duplicate type steps on same selector.
    # e.g. agent typed "vedant" in search, got confused, typed "vedant" again later → keep last.
    deduped: list[dict] = []
    for i, step in enumerate(cleaned):
        if step["action"] == "type":
            sel = (step.get("selector") or "").strip().lower()
            if sel:
                # Skip if a later step also types into the same selector
                has_later = any(
                    cleaned[j].get("action") == "type"
                    and (cleaned[j].get("selector") or "").strip().lower() == sel
                    for j in range(i + 1, len(cleaned))
                )
                if has_later:
                    continue
        # Remove intermediate navigate-back-to-same-URL (agent reset and retried)
        if step["action"] == "navigate" and i > 0:
            url = str(step.get("value") or "").strip()
            if url:
                has_later = any(
                    cleaned[j].get("action") == "navigate"
                    and str(cleaned[j].get("value") or "").strip() == url
                    for j in range(i + 1, len(cleaned))
                )
                if has_later:
                    continue
        # Collapse consecutive wait steps — keep only the last one (agent spams waits on slow pages)
        if step["action"] == "wait":
            next_step = cleaned[i + 1] if i + 1 < len(cleaned) else None
            if next_step and next_step["action"] == "wait":
                continue
        deduped.append(step)

    # Re-number orders
    for i, step in enumerate(deduped):
        step["order"] = i

    return normalize_steps(deduped), task_completed


# ---------------------------------------------------------------------------
# Main entry point — run browser agent (dispatches by provider)
# ---------------------------------------------------------------------------

async def run_agent(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 15,
) -> list[dict]:
    """
    Run the browser agent to perform `task` starting at `target_url`.
    - For ollama: uses custom Playwright vision loop (_run_custom_agent)
    - For claude/openai: uses browser_use.Agent
    Returns list of steps in our standard format.
    """
    provider = settings.llm_provider

    if provider == "ollama":
        return await _run_agent_ollama(task, target_url, storage_state_json, max_steps)
    else:
        return await _run_agent_browser_use(task, target_url, storage_state_json, max_steps)


async def _run_agent_ollama(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 15,
) -> list[dict]:
    """Launch Playwright, apply auth state, run custom vision agent."""
    from playwright.async_api import async_playwright

    storage_file = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            context_opts: dict = {}
            if storage_state_json:
                storage_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                )
                storage_file.write(storage_state_json)
                storage_file.close()
                context_opts["storage_state"] = storage_file.name

            context = await browser.new_context(**context_opts)
            page = await context.new_page()

            steps, _ = await _run_custom_agent(
                task=task,
                target_url=target_url,
                page=page,
                max_steps=max_steps,
            )

            await context.close()
            await browser.close()
            return steps

    finally:
        if storage_file and os.path.exists(storage_file.name):
            os.unlink(storage_file.name)


async def _run_agent_browser_use(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 25,
) -> list[dict]:
    """Original browser_use.Agent path — for claude and openai providers."""
    from browser_use import Agent
    from browser_use.browser.profile import BrowserProfile
    from browser_use.browser.session import BrowserSession

    storage_file = None
    try:
        profile_kwargs: dict = {"headless": True}

        if storage_state_json:
            storage_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            storage_file.write(storage_state_json)
            storage_file.close()
            profile_kwargs["storage_state"] = storage_file.name

        profile = BrowserProfile(**profile_kwargs)
        session = BrowserSession(browser_profile=profile)
        llm = _get_browser_use_llm()

        agent = Agent(
            task=f"{task}\n\nStart at: {target_url}",
            llm=llm,
            browser_session=session,
            max_actions_per_step=5,
            use_vision=True,
        )

        history = await agent.run(max_steps=max_steps)
        return extract_steps_from_history(history)

    finally:
        if storage_file and os.path.exists(storage_file.name):
            os.unlink(storage_file.name)


async def run_agent_for_test(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 30,
    artifacts_dir: str | None = None,
) -> dict:
    """
    Execute a test using the Ollama vision agent.
    Unlike run_agent (which is for test generation), this:
      - Tracks whether the task was fully completed (agent said "done")
      - Captures browser storage state after the test (for auth sharing)
      - Returns {passed, error_message, captured_storage_state}

    Called by the Celery runner for test execution.
    """
    from playwright.async_api import async_playwright

    from pathlib import Path

    storage_file = None
    captured_state: str | None = None
    console_logs: list[str] = []
    video_path: str | None = None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            context_opts: dict = {}
            if storage_state_json:
                storage_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                )
                storage_file.write(storage_state_json)
                storage_file.close()
                context_opts["storage_state"] = storage_file.name

            # Record video if artifacts_dir provided
            video_dir: Path | None = None
            if artifacts_dir:
                video_dir = Path(artifacts_dir) / "video"
                video_dir.mkdir(parents=True, exist_ok=True)
                context_opts["record_video_dir"] = str(video_dir)

            context = await browser.new_context(**context_opts)
            page = await context.new_page()

            # Capture console output as logs
            page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

            steps, completed = await _run_custom_agent(
                task=task,
                target_url=target_url,
                page=page,
                max_steps=max_steps,
            )

            # Capture auth session for the next test
            try:
                state = await context.storage_state()
                captured_state = json.dumps(state)
            except Exception:
                pass

            await context.close()
            await browser.close()

            # Collect recorded video
            if video_dir and video_dir.exists():
                webm_files = list(video_dir.glob("*.webm"))
                if webm_files:
                    video_path = str(webm_files[0])

        if completed:
            return {
                "passed": True,
                "error_message": None,
                "captured_storage_state": captured_state,
                "console_logs": console_logs,
                "video_path": video_path,
            }
        else:
            return {
                "passed": False,
                "error_message": f"Agent did not complete all task steps within {max_steps} actions.",
                "captured_storage_state": captured_state,
                "console_logs": console_logs,
                "video_path": video_path,
            }

    except Exception as exc:
        logger.exception("run_agent_for_test failed")
        return {
            "passed": False,
            "error_message": str(exc),
            "captured_storage_state": captured_state,
            "console_logs": console_logs,
            "video_path": video_path,
        }
    finally:
        if storage_file and os.path.exists(storage_file.name):
            os.unlink(storage_file.name)


def _get_browser_use_llm():
    """Return the LLM instance that browser-use Agent expects (langchain-style BaseChatModel)."""
    provider = settings.llm_provider

    if provider == "claude":
        from anthropic import AsyncAnthropic
        from browser_use.llm.base import BaseChatModel

        # browser-use v0.12.5 works with its own BaseChatModel wrapper
        # Use the anthropic-based one it ships with
        try:
            from browser_use.llm import ChatAnthropic
            return ChatAnthropic(
                model="claude-sonnet-4-6",
                api_key=settings.anthropic_api_key,
            )
        except ImportError:
            # Fallback: try langchain_anthropic
            from langchain_anthropic import ChatAnthropic as LCChatAnthropic
            return LCChatAnthropic(
                model="claude-sonnet-4-6",
                anthropic_api_key=settings.anthropic_api_key,
            )

    elif provider == "openai":
        try:
            from browser_use.llm import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
            )
        except ImportError:
            from langchain_openai import ChatOpenAI as LCChatOpenAI
            return LCChatOpenAI(
                model="gpt-4o",
                openai_api_key=settings.openai_api_key,
            )

    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
            from pydantic import Field as PydanticField

            class _ChatOllamaWithProvider(ChatOllama):
                provider: str = PydanticField(default="openai")
                model_name: str = PydanticField(default="")

                def model_post_init(self, __context: object) -> None:
                    if not self.model_name:
                        object.__setattr__(self, "model_name", self.model)

                def __setattr__(self, name: str, value: object) -> None:
                    try:
                        super().__setattr__(name, value)
                    except (ValueError, AttributeError):
                        object.__setattr__(self, name, value)

                def __getattr__(self, name: str) -> object:
                    if name == "model_name":
                        return self.model
                    raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

            return _ChatOllamaWithProvider(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                client_kwargs={"headers": {"Authorization": f"Bearer {settings.ollama_api_key}"}},
                provider="openai",
                model_name=settings.ollama_model,
            )
        except ImportError:
            raise ImportError("Install langchain-ollama: pip install langchain-ollama")

    else:
        raise ValueError(f"Provider '{provider}' not supported for browser-use Agent. Use 'claude', 'openai', or 'ollama'.")
