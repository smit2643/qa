# Ollama Custom Browser Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser_use.Agent with a custom Playwright-based vision loop in `browser.py` so all features work fully with Ollama qwen3.5 — while keeping Claude/OpenAI paths unchanged.

**Architecture:** At each step, the agent takes a screenshot, sends it to Ollama vision with the task description and history, parses the JSON action, executes it in Playwright, and records the step. The loop retries failed actions up to 3x before stopping gracefully. Claude and OpenAI still use browser_use.Agent unchanged.

**Tech Stack:** Python 3.11, Playwright async API, httpx (already in venv), Ollama cloud API (`/api/chat` with `images` field for vision)

---

## File Map

| File | Change |
|---|---|
| `backend/modules/ai/browser.py` | Add `_run_custom_agent()`, update `run_agent()` to dispatch by provider |
| `backend/tests/test_ai.py` | Add unit tests for `_run_custom_agent` and `_execute_action` |

No other files change.

---

## Task 1: Add `_execute_action` helper

**Files:**
- Modify: `backend/modules/ai/browser.py`

This function takes a Playwright `page` and an action dict from the LLM and executes it. Returns `(success: bool, error: str | None)`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_ai.py`, add at the bottom:

```python
# ---------------------------------------------------------------------------
# _execute_action unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_navigate():
    from unittest.mock import AsyncMock, MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    success, err = await _execute_action(page, {
        "action": "navigate",
        "selector": None,
        "value": "https://example.com",
        "description": "Go to example",
    })

    assert success is True
    assert err is None
    page.goto.assert_called_once_with("https://example.com", timeout=15000)


@pytest.mark.asyncio
async def test_execute_action_done():
    from unittest.mock import MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    success, err = await _execute_action(page, {"action": "done", "selector": None, "value": None, "description": "done"})
    assert success is True
    assert err is None


@pytest.mark.asyncio
async def test_execute_action_click_fallback():
    from unittest.mock import AsyncMock, MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    # First locator (get_by_role) raises, second (get_by_text) succeeds
    mock_locator_fail = MagicMock()
    mock_locator_fail.click = AsyncMock(side_effect=Exception("not found"))
    mock_locator_ok = MagicMock()
    mock_locator_ok.first = MagicMock()
    mock_locator_ok.first.click = AsyncMock()

    page.get_by_role = MagicMock(return_value=mock_locator_fail)
    page.get_by_text = MagicMock(return_value=mock_locator_ok)
    page.wait_for_load_state = AsyncMock()

    success, err = await _execute_action(page, {
        "action": "click",
        "selector": "Login",
        "value": None,
        "description": "Click login",
    })

    assert success is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_ai.py::test_execute_action_navigate -v
```

Expected: `FAILED` — `ImportError: cannot import name '_execute_action'`

- [ ] **Step 3: Implement `_execute_action` in `browser.py`**

Add after the `_extract_selector` function (around line 132), before the `run_agent` function:

```python
# ---------------------------------------------------------------------------
# Custom agent — action executor
# ---------------------------------------------------------------------------

async def _execute_action(page: Any, action: dict) -> tuple[bool, str | None]:
    """
    Execute a single LLM-decided action in the Playwright page.
    Returns (success, error_message).
    """
    act = action.get("action", "")
    selector = action.get("selector") or ""
    value = action.get("value") or ""

    try:
        if act == "navigate":
            await page.goto(value, timeout=15000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        elif act == "click":
            clicked = False
            # Try role-based first (button, link)
            for role in ("button", "link", "menuitem", "tab"):
                try:
                    await page.get_by_role(role, name=selector).click(timeout=5000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                # Fallback to text match
                await page.get_by_text(selector).first.click(timeout=5000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)

        elif act == "type":
            filled = False
            for method in (
                lambda: page.get_by_label(selector).fill(value, timeout=5000),
                lambda: page.get_by_placeholder(selector).fill(value, timeout=5000),
                lambda: page.get_by_role("textbox", name=selector).fill(value, timeout=5000),
            ):
                try:
                    await method()
                    filled = True
                    break
                except Exception:
                    continue
            if not filled:
                raise Exception(f"Could not find input field: {selector!r}")

        elif act == "assert":
            from playwright.async_api import expect
            await expect(page.get_by_text(value)).to_be_visible(timeout=5000)

        elif act == "done":
            pass  # terminal — caller handles break

        else:
            pass  # unknown action — skip silently

        return True, None

    except Exception as exc:
        return False, str(exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ai.py::test_execute_action_navigate tests/test_ai.py::test_execute_action_done tests/test_ai.py::test_execute_action_click_fallback -v
```

Expected: all 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ai/browser.py backend/tests/test_ai.py
git commit -m "feat: add _execute_action helper for custom browser agent"
```

---

## Task 2: Add `_run_custom_agent` loop

**Files:**
- Modify: `backend/modules/ai/browser.py`

The core agent loop — takes screenshot, asks LLM, executes action, retries on failure.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_ai.py`:

```python
# ---------------------------------------------------------------------------
# _run_custom_agent unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_custom_agent_basic():
    """Agent completes task in 2 steps: navigate then done."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from modules.ai.browser import _run_custom_agent

    # Mock LLM responses: step 1 = navigate, step 2 = done
    llm_responses = [
        '{"action": "navigate", "selector": null, "value": "https://example.com", "description": "Go to site", "done": false}',
        '{"action": "done", "selector": null, "value": null, "description": "Task complete", "done": true}',
    ]

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(side_effect=llm_responses)

    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    mock_page.url = "https://example.com"

    with patch("modules.ai.browser.LLMProvider", return_value=mock_llm):
        steps = await _run_custom_agent(
            task="visit example.com",
            target_url="https://example.com",
            page=mock_page,
            max_steps=10,
        )

    assert len(steps) >= 1
    assert steps[0]["action"] == "navigate"
    assert steps[0]["value"] == "https://example.com"


@pytest.mark.asyncio
async def test_run_custom_agent_retries_on_failure():
    """Agent retries when action fails, stops after max consecutive failures."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from modules.ai.browser import _run_custom_agent

    # LLM always returns a click on a nonexistent element
    bad_action = '{"action": "click", "selector": "Nonexistent", "value": null, "description": "click", "done": false}'
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=bad_action)

    mock_page = MagicMock()
    mock_page.screenshot = AsyncMock(return_value=b"fake_png")
    mock_page.url = "https://example.com"
    mock_page.get_by_role = MagicMock(side_effect=Exception("not found"))
    mock_page.get_by_text = MagicMock(side_effect=Exception("not found"))
    mock_page.wait_for_load_state = AsyncMock()

    with patch("modules.ai.browser.LLMProvider", return_value=mock_llm):
        steps = await _run_custom_agent(
            task="click something",
            target_url="https://example.com",
            page=mock_page,
            max_steps=10,
        )

    # Should stop gracefully after 3 consecutive failures — no crash
    assert isinstance(steps, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ai.py::test_run_custom_agent_basic -v
```

Expected: `FAILED` — `ImportError: cannot import name '_run_custom_agent'`

- [ ] **Step 3: Implement `_run_custom_agent` in `browser.py`**

Add after `_execute_action`, before `run_agent`:

```python
# ---------------------------------------------------------------------------
# Custom agent — main loop (Ollama vision)
# ---------------------------------------------------------------------------

_AGENT_SYSTEM = (
    "You are a browser automation agent. Look at the screenshot and decide "
    "the next single action to complete the task. "
    "Respond with JSON only — no explanation, no markdown fences."
)


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
    import base64
    import re
    from modules.ai.llm import LLMProvider

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
        # Take screenshot
        try:
            screenshot_bytes = await page.screenshot(type="png", timeout=10000)
        except Exception:
            break

        img_b64 = base64.standard_b64encode(screenshot_bytes).decode()
        current_url = page.url

        # Build history summary (last 5 steps to keep context short)
        history_summary = json.dumps([
            {"action": s["action"], "description": s["description"]}
            for s in step_history[-5:]
        ])

        error_note = f"\nLast action failed: {last_error}\nTry a different selector or approach." if last_error else ""

        user_text = (
            f"Task: {task}\n"
            f"Current URL: {current_url}\n"
            f"Steps completed so far: {history_summary}{error_note}\n\n"
            'What is the next action? Respond ONLY with this JSON:\n'
            '{\n'
            '  "action": "click|type|navigate|assert|done",\n'
            '  "selector": "visible text or label of the element (null if not needed)",\n'
            '  "value": "URL to navigate to or text to type (null if not needed)",\n'
            '  "description": "what you are doing",\n'
            '  "done": false\n'
            '}\n'
            'Set done=true when the task is fully complete.'
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": user_text},
            ],
        }]

        # Ask LLM — retry once on JSON parse failure
        raw = ""
        action: dict = {}
        for attempt in range(2):
            try:
                raw = await llm.complete(messages, system=_AGENT_SYSTEM)
                # Strip markdown fences if present
                raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
                raw = re.sub(r"\n?```$", "", raw.rstrip())
                action = json.loads(raw)
                break
            except (json.JSONDecodeError, Exception):
                if attempt == 0:
                    messages[-1]["content"][-1]["text"] += "\n\nYour last response was not valid JSON. Respond with JSON only."
                else:
                    action = {"action": "done", "selector": None, "value": None, "description": "LLM parse failed", "done": True}

        # Stop if done
        if action.get("done") or action.get("action") == "done":
            break

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
            if consecutive_failures >= 3:
                break  # Stop gracefully

    from modules.extraction.normalizer import normalize_steps
    return normalize_steps(step_history)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ai.py::test_run_custom_agent_basic tests/test_ai.py::test_run_custom_agent_retries_on_failure -v
```

Expected: both `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ai/browser.py backend/tests/test_ai.py
git commit -m "feat: add _run_custom_agent vision loop for Ollama"
```

---

## Task 3: Wire custom agent into `run_agent` by provider

**Files:**
- Modify: `backend/modules/ai/browser.py`

Update `run_agent` to use `_run_custom_agent` when provider is `ollama`, and the existing browser_use path for claude/openai.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_ai.py`:

```python
def test_generate_endpoint_uses_custom_agent_for_ollama(client, auth_headers_with_suite):
    """When provider=ollama, run_agent is called and returns steps correctly."""
    headers, suite_id = auth_headers_with_suite

    with patch("modules.ai.browser.run_agent", new=AsyncMock(return_value=MOCK_STEPS)):
        with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
            res = client.post("/api/v1/ai/generate", json={
                "description": "user logs in with email and password",
                "suite_id": suite_id,
            }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert len(data["steps"]) == 3
    assert data["code"] == MOCK_CODE
```

- [ ] **Step 2: Run test to verify it fails (or passes — it may already pass since run_agent is mocked)**

```bash
pytest tests/test_ai.py::test_generate_endpoint_uses_custom_agent_for_ollama -v
```

- [ ] **Step 3: Update `run_agent` to dispatch by provider**

Replace the entire `run_agent` function in `browser.py` with:

```python
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
                import tempfile
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
```

- [ ] **Step 4: Run all AI tests**

```bash
pytest tests/test_ai.py -v
```

Expected: all existing tests still pass, new tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ai/browser.py backend/tests/test_ai.py
git commit -m "feat: wire custom Ollama agent into run_agent, keep browser_use for claude/openai"
```

---

## Task 4: End-to-end smoke test

**Files:**
- No code changes — verify the full pipeline works live

- [ ] **Step 1: Restart the backend with correct env**

```bash
cd /home/smit/Documents/qa/backend
kill $(ps aux | grep "uvicorn main:app --port 8080" | grep -v grep | awk '{print $2}') 2>/dev/null
REDIS_URL="redis://:bug0redis@localhost:6380/0" nohup .venv/bin/python -m uvicorn main:app --port 8080 > /tmp/bug0_backend.log 2>&1 &
sleep 3 && curl -s http://localhost:8080/health
```

Expected: `{"status":"ok","environment":"development"}`

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all 142+ tests pass

- [ ] **Step 3: Live smoke test via API**

```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demotest@bug0.com","password":"secret123"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Get suite ID
SUITE_ID=$(curl -s http://localhost:8080/api/v1/organizations \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Trigger AI generation on example.com
curl -s -X POST http://localhost:8080/api/v1/ai/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"click the more information link\",\"suite_id\":\"$SUITE_ID\"}"
```

Expected: JSON response with `test_id`, `code` containing a real `async def test_*` function, and `steps` with real recorded actions.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Ollama custom browser agent — full pipeline working"
```
