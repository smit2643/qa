"""Browser module — uses browser-use Agent to autonomously navigate apps and record real actions."""

import json
import os
import tempfile
from typing import Any

from core.config import settings


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
# Main entry point — run browser-use Agent
# ---------------------------------------------------------------------------

async def run_agent(
    task: str,
    target_url: str,
    storage_state_json: str | None = None,
    max_steps: int = 20,
) -> list[dict]:
    """
    Run browser-use Agent to perform `task` starting at `target_url`.
    Returns list of steps in our standard format.

    If storage_state_json is provided, the browser starts authenticated.
    """
    from browser_use import Agent
    from browser_use.browser.profile import BrowserProfile
    from browser_use.browser.session import BrowserSession

    storage_file = None
    try:
        # Build browser profile
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

    else:
        raise ValueError(f"Provider '{provider}' not supported for browser-use Agent. Use 'claude' or 'openai'.")
