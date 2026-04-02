"""Generator Agent — converts recorded steps into Playwright Python code."""

import json
import re

from .llm import LLMProvider

GENERATOR_SYSTEM = """You are an expert Playwright test engineer. Convert a list of browser actions into production-ready Playwright Python code.

Rules:
- Use playwright.async_api — import Page, expect
- Use accessibility selectors wherever possible:
    page.get_by_role("button", name="Login")
    page.get_by_label("Email")
    page.get_by_placeholder("Search...")
    page.get_by_text("Submit")
- Only use CSS/XPath as last resort when no accessibility selector fits
- Add expect() assertions after navigation and key actions
- Use async/await throughout
- Function signature: async def test_<snake_case_name>(page: Page):
- Add a brief inline comment per step describing what it does

Output ONLY the Python code — no markdown fences, no explanation, no imports (the test runner handles imports).
"""


async def generate_code(steps: list[dict], llm: LLMProvider, test_name: str = "flow") -> str:
    """
    Takes a list of steps (from browser-use Agent or video/recording extraction)
    and returns Playwright Python test code.

    steps format:
    [{"order": 0, "action": "navigate", "selector": None, "value": "https://...", "description": "..."}]
    """
    steps_json = json.dumps(steps, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"Convert these browser actions into a Playwright Python test function named 'test_{_snake(test_name)}':\n\n"
                f"{steps_json}\n\n"
                "Action types:\n"
                "  navigate: go to value URL\n"
                "  click: click the element described by selector\n"
                "  type: fill selector field with value\n"
                "  assert: verify selector element contains/shows value\n"
                "  wait: wait for value milliseconds\n\n"
                "Output only the Python function."
            ),
        }
    ]

    code = await llm.complete(messages, system=GENERATOR_SYSTEM)
    return _strip_fences(code.strip())


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model wrapped the output."""
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code.rstrip())
    return code.strip()


def _snake(text: str) -> str:
    """Convert text to snake_case for use in function names."""
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text).lower()
    return re.sub(r"\s+", "_", text.strip())[:50] or "generated"
