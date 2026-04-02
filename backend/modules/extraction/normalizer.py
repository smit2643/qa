"""Unified step normalizer — runs after every input method (text, recording, video).

All three pipelines produce steps in our standard dict format:
    {order: int, action: str, selector: str|None, value: str|None, description: str}

This module validates, deduplicates, and re-sequences those steps so downstream
consumers (code generator, DB persistence) always receive clean, ordered input.
"""

from typing import Any

VALID_ACTIONS = {"navigate", "click", "type", "assert", "wait"}

_DEFAULT_DESCRIPTIONS = {
    "navigate": "Navigate to URL",
    "click": "Click element",
    "type": "Enter text",
    "assert": "Assert element",
    "wait": "Wait",
}


def normalize_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize a raw steps list into clean, sequential steps.

    Operations applied in order:
    1. Coerce unknown actions to 'wait'.
    2. Fill missing / empty descriptions with a sensible default.
    3. Remove consecutive duplicate steps (same action + selector + value).
    4. Re-sequence `order` fields starting from 0.

    Returns a new list — the input is not mutated.
    """
    if not steps:
        return []

    result: list[dict[str, Any]] = []

    for raw in steps:
        action = str(raw.get("action") or "wait").strip().lower()
        if action not in VALID_ACTIONS:
            action = "wait"

        selector = raw.get("selector") or None
        value = raw.get("value") or None
        description = str(raw.get("description") or "").strip()

        if not description:
            if action == "navigate" and value:
                description = f"Navigate to {value}"
            elif action == "click" and selector:
                description = f"Click {selector}"
            elif action == "type" and selector:
                description = f"Type into {selector}"
            elif action == "assert" and selector:
                description = f"Assert {selector}"
            else:
                description = _DEFAULT_DESCRIPTIONS.get(action, action.capitalize())

        step: dict[str, Any] = {
            "order": 0,  # placeholder — re-sequenced below
            "action": action,
            "selector": selector,
            "value": value,
            "description": description,
        }

        # Deduplicate: skip if identical to the last accepted step
        if result and _is_duplicate(result[-1], step):
            continue

        result.append(step)

    # Re-sequence orders
    for i, step in enumerate(result):
        step["order"] = i

    return result


def _is_duplicate(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two steps are consecutive duplicates when action + selector + value all match."""
    return (
        a["action"] == b["action"]
        and a["selector"] == b["selector"]
        and a["value"] == b["value"]
    )
