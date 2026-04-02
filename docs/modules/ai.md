# AI Module

Location: `backend/modules/ai/`

Handles AI-powered test generation: takes a plain-English description of a user journey, visits the target URL in a headless browser, and returns working Playwright Python code — all via a multi-agent pipeline.

---

## Pipeline Overview

```
description + suite_id
    → get project target_url
    → browser visits URL → accessibility tree
    → compress tree (fit in LLM context)
    → Planner Agent → structured test plan (JSON)
    → Generator Agent → Playwright Python code
    → save TestCase + TestSteps to DB
    → return {test_id, code, version, plan}
```

Each stage is a discrete module so individual components can be swapped or tested independently.

---

## Files

| File | Responsibility |
|---|---|
| `llm.py` | Unified async LLM interface — Claude, OpenAI, Gemini |
| `browser.py` | Headless browser visit → accessibility tree string |
| `compression.py` | Context compression — tree and message history |
| `planner.py` | Planner Agent — description + tree → structured JSON plan |
| `generator.py` | Generator Agent — plan → Playwright Python code |
| `service.py` | Orchestrates the full pipeline, RBAC check, DB writes |
| `router.py` | FastAPI router — `POST /api/v1/ai/generate` |

---

## LLM Provider (`llm.py`)

`LLMProvider` is a unified async class that wraps Claude, OpenAI, and Gemini behind a single interface.

### Methods

| Method | Signature | Returns |
|---|---|---|
| `complete` | `complete(messages, system) -> str` | Raw string reply from the model |
| `complete_json` | `complete_json(messages, system) -> dict` | Parsed dict; strips markdown fences, raises `ValueError` on invalid JSON |

### Supported Providers

| Provider | Model | Required Env Var |
|---|---|---|
| `claude` (default) | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `gemini` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |

### Switching Providers

Set `LLM_PROVIDER` in `.env`. No code changes needed.

```
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

The provider is read from `settings.llm_provider` at runtime, or can be passed directly to the `LLMProvider` constructor.

---

## Browser + Accessibility Tree (`browser.py`)

```python
get_accessibility_tree(url, storage_state_json=None) -> str
```

Uses Playwright in headless mode to visit `url` and extract the page's accessibility tree via `page.accessibility.snapshot()`. The tree is formatted by `_format_tree()`, which recursively renders each node as indented text:

```
role: name
  role: name
    role: name
```

### storageState.json Integration

If `storage_state_json` is provided (a JSON string containing cookies/localStorage from a logged-in session), the browser module:

1. Writes the JSON to a temp file
2. Passes the temp file path to Playwright's browser context as `storage_state`
3. The browser launches already authenticated — no login step needed

This allows the accessibility tree to reflect authenticated page state (dashboards, account pages, etc.).

**How it flows:**

```
Project.storage_state_json (stored in DB, uploaded via Phase 2 API)
    → service.py reads it from project record
    → passes it to get_accessibility_tree()
    → browser.py writes temp file, injects into Playwright context
    → accessibility tree reflects authenticated page
```

---

## Context Compression (`compression.py`)

LLM context windows are finite. Two compression helpers prevent hitting token limits.

### `compress_tree(tree_text, max_chars=12000)`

Compresses the raw accessibility tree before sending it to the Planner Agent.

| Condition | Action |
|---|---|
| `len(tree_text) <= max_chars` | Pass through unchanged |
| Tree too long | Keep only interactive roles: `button`, `link`, `textbox`, `input`, `combobox`, `checkbox`, `radio`, `menuitem`, `tab`, `listitem` |
| Still too long after filtering | Truncate to `max_chars` and append a note indicating truncation |

### `compress_messages(messages, max_total_chars=40000)`

Compresses conversation history to prevent overflow in multi-turn flows.

| Condition | Action |
|---|---|
| Total chars `<= max_total_chars` | Pass through unchanged |
| History too long | Keep the last 4 messages verbatim; summarize older messages into a single system-style context message |

---

## Planner Agent (`planner.py`)

```python
plan_test(description, accessibility_tree, target_url, llm) -> dict
```

Sends the compressed accessibility tree, user description, and target URL to the LLM with a system prompt that instructs it to output structured JSON. Uses `llm.complete_json()` to guarantee a parsed dict.

### Output Schema

```json
{
  "test_name": "string",
  "description": "string",
  "p0_paths": ["string"],
  "steps": [
    {
      "order": 1,
      "action": "navigate|click|type|assert|wait",
      "selector": "getByRole / getByLabel / getByPlaceholder expression",
      "value": "string or null",
      "description": "human-readable step description"
    }
  ]
}
```

`p0_paths` lists the critical happy-path user journeys the test covers (e.g. "User submits login form with valid credentials").

---

## Generator Agent (`generator.py`)

```python
generate_code(plan, llm) -> str
```

Takes the plan dict from the Planner Agent and asks the LLM to convert it into async Playwright Python. The system prompt enforces:

- Use `page.get_by_role()`, `page.get_by_label()`, `page.get_by_placeholder()` — never CSS selectors or XPath
- Proper `async`/`await` throughout
- `expect()` assertions for all assert steps
- No `page.locator(".some-css-class")` calls

Strips markdown code fences if the model wraps output in triple backticks.

### Example Output Shape

```python
import asyncio
from playwright.async_api import async_playwright, expect

async def run_test(page):
    await page.goto("https://app.example.com/login")
    await page.get_by_label("Email").fill("user@example.com")
    await page.get_by_label("Password").fill("hunter2")
    await page.get_by_role("button", name="Sign in").click()
    await expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
```

---

## Selector Strategy

The pipeline uses accessibility selectors exclusively — `getByRole`, `getByLabel`, `getByPlaceholder` — rather than CSS classes or XPaths. This is intentional:

| Selector type | Stability | Why |
|---|---|---|
| CSS class (`.btn-primary`) | Low | Classes change with design system updates |
| XPath (`//div[3]/button`) | Low | Breaks on any DOM restructure |
| `getByRole("button", name="Sign in")` | High | Reflects semantic meaning; survives CSS and DOM refactors |
| `getByLabel("Email")` | High | Tied to accessible label, which rarely changes |

This is the same approach recommended by Playwright's official docs and used by bug0's production system.

---

## Service Layer (`service.py`)

Orchestrates the full pipeline and handles persistence.

### Steps

1. **RBAC check** — verify requesting user is `member` or above in the suite's organization; raise 403 otherwise
2. **Fetch project data** — load `target_url` and `storage_state_json` from the project record
3. **Accessibility tree** — call `get_accessibility_tree(target_url, storage_state_json)`
4. **Compress tree** — call `compress_tree()` before passing to agents
5. **Plan** — call `plan_test(description, compressed_tree, target_url, llm)`
6. **Generate** — call `generate_code(plan, llm)`
7. **Persist** — create or update `TestCase` in DB (if `test_id` provided, update existing); replace all `TestStep` rows from plan steps
8. **Return** — `{test_id, code, version, plan}`

---

## API Endpoint (`router.py`)

### `POST /api/v1/ai/generate`

Requires a valid JWT (`Authorization: Bearer <token>`).

#### Request Body

```json
{
  "description": "User logs in with valid credentials and lands on the dashboard",
  "suite_id": "uuid",
  "test_id": "uuid | null"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | string | Yes | Plain-English description of the user journey to test |
| `suite_id` | UUID | Yes | Which test suite this test belongs to |
| `test_id` | UUID | No | If provided, updates an existing test instead of creating a new one |

#### Response

```json
{
  "test_id": "uuid",
  "code": "import asyncio\nfrom playwright...",
  "version": 2,
  "plan": {
    "test_name": "Login flow — valid credentials",
    "description": "...",
    "p0_paths": ["..."],
    "steps": [...]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `test_id` | UUID | ID of the created or updated TestCase |
| `code` | string | Full Playwright Python async code, ready to execute |
| `version` | int | Version number (incremented on each regeneration) |
| `plan` | object | Structured plan from the Planner Agent |

#### Error Responses

| Status | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | User is not a member of the suite's organization |
| 404 | `suite_id` or `test_id` not found |
| 422 | Missing required fields |
| 500 | LLM call failed or returned invalid JSON |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | No (default: `claude`) | Active LLM provider: `claude`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` | If using Claude | API key for Anthropic |
| `OPENAI_API_KEY` | If using OpenAI | API key for OpenAI |
| `GOOGLE_API_KEY` | If using Gemini | API key for Google |

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude API client |
| `openai` | OpenAI API client |
| `google-generativeai` | Gemini API client |
| `playwright` | Headless browser for accessibility tree extraction |
