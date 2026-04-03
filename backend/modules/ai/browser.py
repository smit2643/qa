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

MAX_CONSECUTIVE_FAILURES = 3


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

async def _execute_action(page: Any, action: dict) -> tuple[bool, str | None]:
    """
    Execute a single LLM-decided action in the Playwright page.
    Returns (success, error_message).
    """
    from playwright.async_api import expect as pw_expect

    act = action.get("action", "")
    selector = action.get("selector")  # keep None as None
    value = action.get("value") or ""

    try:
        if act == "navigate":
            await page.goto(value, timeout=15000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        elif act == "click":
            if not selector:
                raise Exception("click action requires a selector")
            clicked = False
            for role in ("button", "link", "menuitem", "tab"):
                try:
                    await page.get_by_role(role, name=selector).click(timeout=5000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                await page.get_by_text(selector).first.click(timeout=5000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        elif act == "type":
            if not selector:
                raise Exception("type action requires a selector")
            filled = False
            try:
                await page.get_by_label(selector).fill(value, timeout=5000)
                filled = True
            except Exception:
                pass
            if not filled:
                try:
                    await page.get_by_placeholder(selector).fill(value, timeout=5000)
                    filled = True
                except Exception:
                    pass
            if not filled:
                try:
                    await page.get_by_role("textbox", name=selector).fill(value, timeout=5000)
                    filled = True
                except Exception:
                    pass
            if not filled:
                raise Exception(f"Could not find input field: {selector!r}")

        elif act == "assert":
            await pw_expect(page.get_by_text(value)).to_be_visible(timeout=5000)

        elif act == "wait":
            ms = int(value) if value and str(value).isdigit() else 1000
            await page.wait_for_timeout(ms)

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

_AGENT_SYSTEM = (
    "You are a browser automation agent. Look at the screenshot and decide "
    "the next single action to complete the task. "
    "Valid actions: click, type, navigate, assert, wait, done. "
    "Use 'done' when the task is complete or impossible to complete. "
    "Respond with a single JSON object only — no explanation, no markdown fences, no extra text."
)


_KNOWN_ACTIONS = {"click", "type", "navigate", "assert", "wait", "done"}


async def _run_custom_agent(
    task: str,
    target_url: str,
    page: Any,
    max_steps: int = 25,
) -> list[dict]:
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

    # Navigate to start URL first
    try:
        await page.goto(target_url, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        step_history.append({
            "order": order,
            "action": "navigate",
            "selector": None,
            "value": target_url,
            "description": f"Navigate to {target_url}",
        })
        order += 1
    except Exception as exc:
        return [{"order": 0, "action": "navigate", "selector": None, "value": target_url,
                 "description": f"Navigate to {target_url} (failed: {exc})"}]

    last_error: str | None = None

    for _ in range(max_steps):
        # Take screenshot — JPEG quality=60 to reduce payload vs PNG
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60, timeout=10000)
        except Exception as exc:
            logger.warning("Screenshot failed during agent loop: %s", exc)
            break

        img_b64 = base64.standard_b64encode(screenshot_bytes).decode()
        current_url = page.url

        # Build history summary (last 5 steps to keep context short)
        history_summary = json.dumps([
            {"action": s["action"], "selector": s.get("selector"), "description": s["description"]}
            for s in step_history[-5:]
        ])

        error_note = f"\nLast action failed: {last_error}\nTry a different selector or approach." if last_error else ""

        user_text = (
            f"Task: {task}\n"
            f"Current URL: {current_url}\n"
            f"Steps completed so far: {history_summary}{error_note}\n\n"
            'What is the next action? Respond ONLY with this JSON:\n'
            '{\n'
            '  "action": "click|type|navigate|assert|wait|done",\n'
            '  "selector": "visible text or label of the element (null if not needed)",\n'
            '  "value": "URL to navigate to or text to type (null if not needed)",\n'
            '  "description": "what you are doing"\n'
            '}\n'
            'Use action="done" when the task is fully complete or impossible to complete.'
        )

        # image_url content blocks are converted to Ollama's `images` array by _complete_ollama
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": user_text},
            ],
        }]

        # Ask LLM — retry once on JSON parse failure
        action: dict = {}
        for attempt in range(2):
            try:
                raw = await llm.complete(messages, system=_AGENT_SYSTEM)
                raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
                raw = re.sub(r"\n?```$", "", raw.rstrip())
                action = json.loads(raw)
                break
            except Exception:
                if attempt == 0:
                    messages[-1]["content"][-1]["text"] += "\n\nYour last response was not valid JSON. Respond with JSON only."
                else:
                    action = {"action": "done", "selector": None, "value": None, "description": "LLM parse failed"}

        # Stop if done
        if action.get("action") == "done":
            break

        # Guard: skip unknown actions without resetting consecutive_failures
        if action.get("action") not in _KNOWN_ACTIONS:
            consecutive_failures += 1
            last_error = f"Unknown action: {action.get('action')!r}"
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

    return normalize_steps(step_history)


# ---------------------------------------------------------------------------
# Main entry point — run browser agent (dispatches by provider)
# ---------------------------------------------------------------------------

async def run_agent(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 25,
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
    max_steps: int = 25,
) -> list[dict]:
    """Launch Playwright, apply auth state, run custom vision agent."""
    from playwright.async_api import async_playwright

    storage_file = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)

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

            steps = await _run_custom_agent(
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
