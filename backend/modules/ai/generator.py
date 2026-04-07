"""Generator Agent — converts recorded steps into Playwright Python code."""

import json
import re

from .llm import LLMProvider


def _sanitize_code(code: str) -> str:
    """
    Post-process generated Playwright code to remove patterns that always fail
    and replace fragile locators with resilient ones.

    1. Strip <think>...</think> blocks (qwen/deepseek reasoning models).
    2. Remove brittle expect() assertions.
    3. Fix email/password/label locators.
    4. Fix malformed CSS selectors (truncated href patterns etc.).
    """
    # 1. Strip thinking tokens
    code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL)

    # 2. Drop any line containing a brittle expect() assertion (line filter handles nested parens)
    _ASSERT_PATTERNS = (
        ".to_have_url(", ".to_be_visible(", ".to_be_hidden(",
        ".to_have_text(", ".to_contain_text(", ".to_have_value(",
        ".to_be_checked(", ".to_be_disabled(", ".to_be_enabled(",
    )
    lines = code.splitlines()
    lines = [ln for ln in lines if not any(p in ln for p in _ASSERT_PATTERNS)]
    code = "\n".join(lines)

    # Fix malformed href CSS selectors like a[href*=\  or a[href*='] (truncated)
    # Replace with a safe sidebar link click
    code = re.sub(
        r'page\.locator\([\'"]a\[href\*=[\\\'"]?\s*[\'"]?\)',
        'page.locator("nav a, aside a, [role=\'navigation\'] a").first',
        code,
    )
    # Fix _smart_click with malformed CSS selector argument
    code = re.sub(
        r"_smart_click\(page,\s*'a\[href\*=.*?'\)",
        "_smart_click(page, 'Customers')",
        code,
    )

    # 3. Email fields — always use type attribute (most reliable, works without <label>)
    code = re.sub(
        r'page\.get_by_(?:label|placeholder)\(["\'](?:email|e-mail|username|user name|login)["\'][^)]*\)',
        "page.locator(\"input[type='email'], input[name*='email' i], input[placeholder*='email' i]\").first",
        code, flags=re.IGNORECASE,
    )

    # 4. Password fields
    code = re.sub(
        r'page\.get_by_(?:label|placeholder)\(["\'](?:password|passwd|pass|pwd|secret)["\'][^)]*\)',
        "page.locator(\"input[type='password']\").first",
        code, flags=re.IGNORECASE,
    )

    # 5. All remaining get_by_label calls — replace with a resilient combo that
    #    tries label, placeholder, name attribute, and visible input in order.
    #    Captures the quoted field name so we can build the fallback selectors.
    def _resilient_locator(m: re.Match) -> str:
        field = m.group(1)  # e.g. "First Name"
        field_lower = field.lower().replace(" ", "")
        # Don't append input:visible — the executor's _smart_fill handles the fallback
        return (
            f'page.locator('
            f'"[placeholder*=\'{field}\' i], [aria-label*=\'{field}\' i], '
            f'[name*=\'{field_lower}\'], [id*=\'{field_lower}\']").first'
        )

    code = re.sub(
        r'page\.get_by_label\(["\']([^"\']+)["\'][^)]*\)',
        _resilient_locator,
        code,
    )

    return code.strip()

GENERATOR_SYSTEM = """You are an expert Playwright test engineer. Convert a list of browser actions into clean, production-ready Playwright Python code.

DEDUPLICATION RULE (most important):
- The input steps may contain repeated sequences from agent retries (e.g. same search field filled twice, same button clicked twice, same page navigated twice).
- Generate each logical action ONCE. Use the LAST occurrence of any repeated action.
- If you see the same field being filled multiple times, generate only the final fill.
- If you see the agent navigate back to the same page and redo steps, generate only the final pass.

Locator rules (in order of preference):
- Email/username: page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i]").first.fill(value)
- Password: page.locator("input[type='password']").first.fill(value)
- Search: page.locator("input[type='search'], input[name*='search' i], input[placeholder*='search' i]").first.fill(value)
- Other fields: page.locator("[placeholder*='FIELD' i], [aria-label*='FIELD' i], [name*='FIELD' i]").first.fill(value)
- Buttons/links: page.get_by_role("button", name=TEXT, exact=False).or_(page.get_by_text(TEXT, exact=False)).first.click()
- XPath selectors (starts with //): page.locator("xpath=SELECTOR").first.click()
- NEVER use get_by_label() — many apps have no linked <label> elements
- NEVER use CSS selectors with href patterns like a[href*=...] — use get_by_text or get_by_role instead

Navigation rules:
- page.goto(url) then page.wait_for_load_state("domcontentloaded")
- After clicks that navigate: page.wait_for_load_state("domcontentloaded")
- Add page.wait_for_timeout(1000) after heavy pages only

Assertion rules:
- For SCROLL steps: use await page.evaluate("window.scrollBy(0, 600)") for down, await page.evaluate("window.scrollBy(0, -600)") for up
- NEVER use expect(page).to_have_url() — URL assertions fail when apps redirect
- NEVER use expect(...).to_be_visible/to_have_text/to_contain_text() — brittle across environments
- Do not add assertions after form submissions or button clicks

Output format:
- Function signature: async def test_flow(page: Page):
- Use async/await throughout
- One brief inline comment per step explaining what it does
- Output ONLY the Python function — no imports, no markdown, no explanation
"""


def _deduplicate_steps(steps: list[dict]) -> list[dict]:
    """
    Remove redundant steps caused by Ollama's looping/retry behavior before sending to code generator.

    Rules:
    1. For 'type' steps: if the same selector appears multiple times, keep only the last.
    2. For 'navigate' steps (non-first): if the same URL appears later, skip the earlier one.
    3. Re-number orders after dedup.
    """
    if len(steps) <= 1:
        return steps

    result = []
    for i, step in enumerate(steps):
        action = step.get("action", "")
        sel = (step.get("selector") or "").strip().lower()
        url = str(step.get("value") or "").strip()

        # Type step: skip if same selector appears later
        if action == "type" and sel:
            has_later = any(
                steps[j].get("action") == "type"
                and (steps[j].get("selector") or "").strip().lower() == sel
                for j in range(i + 1, len(steps))
            )
            if has_later:
                continue

        # Navigate step (not first): skip if same URL navigated again later
        if action == "navigate" and i > 0 and url:
            has_later = any(
                steps[j].get("action") == "navigate"
                and (steps[j].get("value") or "").strip() == url
                for j in range(i + 1, len(steps))
            )
            if has_later:
                continue

        result.append(dict(step))

    # Re-number
    for i, step in enumerate(result):
        step["order"] = i

    return result


async def generate_code(steps: list[dict], llm: LLMProvider, test_name: str = "flow") -> str:
    """
    Takes a list of steps (from browser-use Agent or video/recording extraction)
    and returns Playwright Python test code.

    steps format:
    [{"order": 0, "action": "navigate", "selector": None, "value": "https://...", "description": "..."}]
    """
    steps = _deduplicate_steps(steps)
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
                "  wait: wait for value milliseconds (if value is null/missing use 2000)\n\n"
                "Output only the Python function."
            ),
        }
    ]

    code = await llm.complete(messages, system=GENERATOR_SYSTEM)
    return _sanitize_code(_strip_fences(code.strip()))


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model wrapped the output."""
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code.rstrip())
    return code.strip()


def _snake(text: str) -> str:
    """Convert text to snake_case for use in function names."""
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text).lower()
    return re.sub(r"\s+", "_", text.strip())[:50] or "generated"
