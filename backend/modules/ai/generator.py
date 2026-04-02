"""Generator Agent — converts a structured test plan into Playwright Python code."""

import json

from .llm import LLMProvider

GENERATOR_SYSTEM = """You are an expert Playwright test engineer. Convert a test plan into production-ready Playwright Python code.

Rules:
- Use playwright.async_api
- Use accessibility selectors: page.get_by_role(), page.get_by_label(), page.get_by_placeholder(), page.get_by_text()
- Avoid CSS selectors and XPath unless absolutely necessary
- Add expect() assertions to verify state
- Include proper async/await
- Wrap in a proper test function with async def test_<name>(page: Page):
- Add a brief comment per step

Output ONLY the Python code, no markdown fences, no explanation.
"""


async def generate_code(plan: dict, llm: LLMProvider) -> str:
    """Takes a plan dict, returns Playwright Python code string."""
    messages = [
        {
            "role": "user",
            "content": (
                "Convert this test plan to Playwright Python code:\n\n"
                f"{json.dumps(plan, indent=2)}\n\n"
                "Output only the Python code."
            ),
        }
    ]
    code = await llm.complete(messages, system=GENERATOR_SYSTEM)
    # Strip markdown fences if model wrapped it anyway
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return code.strip()
