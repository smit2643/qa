"""Planner Agent — converts a test description + accessibility tree into a structured plan."""

from .llm import LLMProvider

PLANNER_SYSTEM = """You are a QA test planning expert. Given a website's accessibility tree and a user's test description, you produce a structured test plan.

Output JSON with this exact structure:
{
  "test_name": "short descriptive name",
  "description": "what this test verifies",
  "p0_paths": ["critical user journey 1", "critical user journey 2"],
  "steps": [
    {
      "order": 0,
      "action": "navigate|click|type|assert|wait",
      "selector": "accessibility selector or null",
      "value": "text to type or URL or null",
      "description": "human readable description"
    }
  ]
}

Rules:
- Use accessibility-based selectors: getByRole('button', {name: '...'}), getByLabel('...'), getByPlaceholder('...')
- action must be one of: navigate, click, type, assert, wait
- For navigate: value = URL, selector = null
- For click: selector = the element description, value = null
- For type: selector = input description, value = text to type
- For assert: selector = element to check, value = expected text/state
- For wait: value = milliseconds as string, selector = null
- steps must be complete enough to generate working Playwright code
"""


async def plan_test(
    description: str,
    accessibility_tree: str,
    target_url: str,
    llm: LLMProvider,
) -> dict:
    """Returns the structured test plan dict."""
    from .compression import compress_tree

    compressed_tree = compress_tree(accessibility_tree)

    messages = [
        {
            "role": "user",
            "content": (
                f"Target URL: {target_url}\n\n"
                f"Accessibility Tree:\n{compressed_tree}\n\n"
                f"Test Description: {description}\n\n"
                "Produce the test plan JSON."
            ),
        }
    ]
    return await llm.complete_json(messages, system=PLANNER_SYSTEM)
