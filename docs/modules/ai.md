# AI Module

Location: `backend/modules/ai/`

Handles all AI-powered test generation. Three input methods feed into the same pipeline — all produce Playwright Python code saved as a `TestCase`.

---

## How It Actually Works

**browser-use `Agent`** is the core. It's not a static page reader — it's an autonomous browser controller that actually navigates the app, clicks buttons, fills forms, and records every action it takes. Those real actions become the test steps.

```
WITHOUT browser-use (naive approach):
  description → static page snapshot → LLM guesses steps → unreliable code

WITH browser-use (what we use):
  description → Agent NAVIGATES the real app → records real clicks/types → code from real interactions
```

---

## Pipeline Overview

### Input Method 1: Plain English (text)

```
POST /ai/generate  {description, suite_id}
    │
    ▼
browser-use Agent
  task: "Navigate the app and perform: <description>"
  llm: Claude Sonnet 4.6 (default)
  browser: headless Chromium
    │
    ├── Agent navigates target_url
    ├── Finds and interacts with real elements
    ├── Records every step (action, selector, value)
    └── Returns AgentHistoryList
    │
    ▼
extract_steps_from_history(history)
  → list of {action, selector, value, description}
    │
    ▼
Generator Agent (LLM)
  → Playwright Python code from real steps
    │
    ▼
Save TestCase (code + version) + TestSteps to DB
Return {test_id, code, version, steps}
```

### Input Method 2: Screen Recording

```
POST /recordings/upload  (WebM from browser MediaRecorder API)
    │
    ▼
Extract browser events from recording
  → click coordinates → map to accessibility selectors
  → keyboard input → value
  → navigation events → URL
    │
    ▼
Structured steps []
    │
    ▼
POST /ai/generate-from-steps → Generator Agent → Playwright code
```

### Input Method 3: Video Upload

```
POST /videos/upload  (mp4 or webm)
    │
    ▼
Sample frames every 2 seconds
    │
    ▼
Claude Vision per frame:
  "What user action is happening in this frame?"
    │
    ▼
Sequence of {action, element, value} from frames
    │
    ▼
POST /ai/generate-from-steps → Generator Agent → Playwright code
```

---

## Files

| File | Responsibility |
|---|---|
| `llm.py` | Unified async LLM interface — Claude, OpenAI, Gemini |
| `browser.py` | browser-use Agent — navigates app, records real actions |
| `compression.py` | Context compression — tree and message history |
| `planner.py` | Fallback planner — used when Agent cannot navigate (private/blocked pages) |
| `generator.py` | Generator Agent — steps → Playwright Python code |
| `service.py` | Orchestrates full pipeline, RBAC check, DB writes |
| `router.py` | FastAPI routes — `/ai/generate`, `/ai/generate-from-steps` |

---

## browser-use Agent (`browser.py`)

Uses `browser_use.Agent` (v0.12.5) to autonomously interact with the target app.

```python
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile

agent = Agent(
    task=f"Navigate to {target_url} and perform: {description}. Record every action.",
    llm=llm,
    browser_session=session,
)
history = await agent.run(max_steps=20)
steps = extract_steps_from_history(history)
```

**What we extract from `AgentHistoryList`:**
- `history.action_names()` — list of action types (click, type, navigate…)
- `history.model_actions()` — full action details with selectors and values
- `history.urls()` — all URLs visited during the run

**storageState injection:** If the project has `storage_state_json`, it's loaded into `BrowserProfile` so the agent starts already authenticated — no login step needed.

---

## LLM Provider (`llm.py`)

Unified async interface wrapping Claude, OpenAI, and Gemini.

| Provider | Model | Required Env Var |
|---|---|---|
| `claude` (default) | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `gemini` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |

Switch provider: set `LLM_PROVIDER=openai` in `.env` — no code changes needed.

---

## Generator Agent (`generator.py`)

Takes structured steps (from browser-use history, screen recording, or video) and produces Playwright Python code.

**Selector strategy — accessibility first (10x more stable):**
```python
# What the generator produces:
await page.get_by_role("button", name="Login").click()
await page.get_by_label("Email").fill("user@test.com")
await page.get_by_placeholder("Search...").fill("query")

# What it avoids:
await page.click(".login-btn-v2")      # CSS — breaks when class changes
await page.click("//div[@id='btn']")   # XPath — fragile
```

---

## Context Compression (`compression.py`)

| Function | Trigger | Behaviour |
|---|---|---|
| `compress_tree(text, max=12000)` | Tree > 12k chars | Keeps interactive roles: button, link, textbox, input, combobox, heading |
| `compress_messages(msgs, max=40000)` | History > 40k chars | Last 4 messages intact, older ones summarized |

---

## API Endpoints

### `POST /api/v1/ai/generate` 🔒

Generate test from plain English. browser-use Agent actually navigates the app.

**Request:**
```json
{
  "description": "user logs in with email and password and lands on dashboard",
  "suite_id": "...",
  "test_id": "..."
}
```

> `test_id` optional — if provided, updates existing test and bumps version.

**Response:**
```json
{
  "test_id": "...",
  "code": "async def test_user_login(page: Page):\n    ...",
  "version": 1,
  "steps": [
    {"order": 0, "action": "navigate", "value": "https://app.com/login"},
    {"order": 1, "action": "type", "selector": "Email", "value": "user@test.com"},
    {"order": 2, "action": "click", "selector": "Login button"}
  ]
}
```

> Expect 15–40 seconds — agent is actually browsing your app.

### `POST /api/v1/ai/generate-from-steps` 🔒

Generate code from pre-built steps (screen recording or video upload output).

**Request:**
```json
{
  "suite_id": "...",
  "test_name": "User login flow",
  "steps": [
    {"order": 0, "action": "navigate", "value": "https://app.com/login"},
    {"order": 1, "action": "type", "selector": "email input", "value": "user@test.com"},
    {"order": 2, "action": "click", "selector": "Login button"}
  ]
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `claude` | `claude` \| `openai` \| `gemini` |
| `ANTHROPIC_API_KEY` | — | Required for Claude |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `GOOGLE_API_KEY` | — | Required for Gemini |

---

## Testing

All AI tests mock browser-use Agent and LLM — no real API calls:

```python
from unittest.mock import AsyncMock, patch

with patch("modules.ai.browser.run_agent", new=AsyncMock(return_value=mock_steps)):
    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=mock_code)):
        res = client.post("/api/v1/ai/generate", json={...}, headers=headers)
```
