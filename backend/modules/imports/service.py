"""
Code Import service — converts existing test code (any language/framework) into
Bug0 steps + Playwright Python code.

Flow:
  1. RBAC — suite member+
  2. LLM reads the source code, detects language, extracts browser actions as steps
  3. If suite has login config and source code doesn't contain login actions,
     prepend login steps automatically (same pattern as video/recording import)
  4. Generator produces Playwright Python from the steps
  5. Save TestCase (InputMethod.code_import) + TestSteps
  6. Return {test_id, steps, code, ...}
"""

import json
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import TestSuite, TestCase, TestStep, Role, InputMethod
from modules.organizations.service import require_role
from modules.ai.llm import LLMProvider
from modules.ai import generator
from modules.extraction.normalizer import normalize_steps


_DETECT_AND_EXTRACT_SYSTEM = """You are a test code analyzer. You receive test code written in ANY language or framework
(Selenium Java/Python/C#/Ruby, Cypress, Playwright JS/TS, Jest, Pytest, Capybara, TestCafe, plain English test cases, etc.)
and convert it into a structured list of browser actions.

RULES:
- Read the code and understand the INTENT of each action — do not do syntax parsing.
- Extract ONLY real browser interactions: navigation, clicks, typing, assertions, waits.
- Ignore setup/teardown boilerplate (driver initialization, imports, before/after hooks, etc.).
- Detect the source language automatically.
- Each step must have: action, selector, value, description.
  - action: navigate | click | type | assert | wait | scroll
  - selector: the human-readable element name/label/text as it appears on screen (not CSS/XPath)
  - value: URL for navigate, text to type for type, expected text for assert, ms for wait, "up"/"down" for scroll
  - description: one clear sentence describing what this step does
- Convert framework-specific locators to plain English:
  - cy.get('#email') → selector: "Email"
  - driver.findElement(By.xpath("//button[@class='login']")) → selector: "Login button"
  - screen.getByRole('button', {name: 'Submit'}) → selector: "Submit"
- If the code has a login section, include those steps.
- If the code asserts something, include an assert step.

Respond with JSON only — a single object with two fields:
{
  "detected_language": "cypress|selenium-python|selenium-java|selenium-csharp|playwright-js|pytest|jest|capybara|plain-english|other",
  "steps": [
    {"action": "navigate", "selector": null, "value": "https://...", "description": "..."},
    {"action": "type", "selector": "Email", "value": "user@example.com", "description": "..."},
    ...
  ]
}"""


async def _extract_steps_from_code(source_code: str, llm: LLMProvider) -> tuple[str, list[dict]]:
    """
    Ask LLM to read source_code (any language) and return (detected_language, steps).
    """
    messages = [
        {
            "role": "user",
            "content": (
                "Analyze this test code and extract browser actions as steps.\n\n"
                f"```\n{source_code}\n```\n\n"
                "Return a JSON object with 'detected_language' and 'steps' array."
            ),
        }
    ]

    raw = await llm.complete(messages, system=_DETECT_AND_EXTRACT_SYSTEM)

    # Strip thinking tokens
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip markdown fences
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.rstrip())
    # Extract first JSON object
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="LLM could not parse the test code into steps.")

    detected_language = parsed.get("detected_language", "unknown")
    steps = parsed.get("steps", [])

    if not steps:
        raise HTTPException(
            status_code=422,
            detail="No browser actions found in the provided code. Make sure it contains navigation, clicks, or form interactions.",
        )

    return detected_language, steps


def _has_login_steps(steps: list[dict]) -> bool:
    """Check if extracted steps already include login actions."""
    for step in steps:
        sel = (step.get("selector") or "").lower()
        val = (step.get("value") or "").lower()
        if step.get("action") == "type" and any(
            kw in sel for kw in ("email", "password", "username", "passwd", "login")
        ):
            return True
        if step.get("action") == "navigate" and any(
            kw in val for kw in ("login", "signin", "sign-in", "auth")
        ):
            return True
    return False


def _prepend_login_steps(
    steps: list[dict],
    login_url: str,
    login_email: str,
    login_password: str,
) -> list[dict]:
    """Prepend login steps before the existing steps."""
    login_steps = [
        {
            "order": 0,
            "action": "navigate",
            "selector": None,
            "value": login_url,
            "description": "Navigate to login page",
        },
        {
            "order": 1,
            "action": "type",
            "selector": "Email",
            "value": login_email,
            "description": "Enter login email",
        },
        {
            "order": 2,
            "action": "type",
            "selector": "Password",
            "value": login_password,
            "description": "Enter login password",
        },
        {
            "order": 3,
            "action": "click",
            "selector": "Sign in",
            "value": None,
            "description": "Click sign in button",
        },
        {
            "order": 4,
            "action": "wait",
            "selector": None,
            "value": "2000",
            "description": "Wait for login to complete",
        },
    ]
    # Re-number existing steps
    for s in steps:
        s["order"] = s.get("order", 0) + len(login_steps)
    return login_steps + steps


async def import_code(
    db: Session,
    user_id: str,
    suite_id: str,
    test_name: str,
    source_code: str,
    source_language: str = "auto",
) -> dict:
    """
    Full import pipeline:
    1. RBAC
    2. Extract steps from source code via LLM
    3. Prepend login steps if suite has credentials and code doesn't include login
    4. Generate Playwright Python code from steps
    5. Save TestCase + TestSteps
    6. Return result
    """
    # 1. RBAC
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    require_role(db, user_id, suite.project.organization_id, Role.member)

    llm = LLMProvider()

    # 2. Extract steps from source code
    detected_language, raw_steps = await _extract_steps_from_code(source_code, llm)

    # Normalize orders
    for i, s in enumerate(raw_steps):
        s["order"] = i

    # 3. Prepend login if suite has credentials and code doesn't include login
    login_url: str | None = getattr(suite, "login_url", None)
    login_email: str | None = getattr(suite, "login_email", None)
    login_password: str | None = getattr(suite, "login_password", None)
    has_auth_state: bool = bool(getattr(suite, "storage_state_json", None))

    if login_email and login_password and login_url and not has_auth_state and not _has_login_steps(raw_steps):
        raw_steps = _prepend_login_steps(raw_steps, login_url, login_email, login_password)

    # Normalize steps
    steps = normalize_steps(raw_steps)

    # 4. Generate Playwright Python code
    code = await generator.generate_code(steps=steps, llm=llm, test_name=test_name)

    # 5. Save TestCase
    test_case = TestCase(
        suite_id=suite_id,
        name=test_name[:200],
        description=f"Imported from {detected_language} test code",
        code=code,
        version=1,
        input_method=InputMethod.code_import,
    )
    db.add(test_case)
    db.flush()

    # Save TestSteps
    for step_data in steps:
        step = TestStep(
            test_id=test_case.id,
            order=step_data.get("order", 0),
            action=step_data.get("action", "wait"),
            selector=step_data.get("selector"),
            value=str(step_data.get("value")) if step_data.get("value") is not None else None,
            description=step_data.get("description", ""),
            is_assertion=step_data.get("action") == "assert",
        )
        db.add(step)

    db.commit()
    db.refresh(test_case)

    return {
        "test_id": test_case.id,
        "suite_id": suite_id,
        "test_name": test_name,
        "source_language": detected_language,
        "steps": steps,
        "code": code,
        "version": test_case.version,
        "message": f"Imported {len(steps)} steps from {detected_language} code.",
    }
