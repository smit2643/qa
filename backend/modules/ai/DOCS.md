# modules/ai — AI Engine

Phase 3 of the Bug0 clone. Converts plain-English test descriptions into working Playwright test code via a pipeline of: browser accessibility tree capture → LLM planner → LLM code generator.

## Files

| File | Purpose |
|---|---|
| `llm.py` | `LLMProvider` — unified async interface for Claude (claude-sonnet-4-6), OpenAI (gpt-4o), Gemini (gemini-2.0-flash). Provider selected from `settings.llm_provider` or overridden at construction. |
| `compression.py` | `compress_tree(text)` — filters long accessibility trees to interactive elements only. `compress_messages(msgs)` — summarises old conversation history when it grows too long. |
| `browser.py` | `get_accessibility_tree(url, storage_state_json?)` — launches a headless Chromium browser via Playwright, navigates to the URL, and returns the accessibility tree as indented text. Supports injecting auth cookies via `storage_state_json`. |
| `planner.py` | `plan_test(description, tree, url, llm)` — calls the LLM with a structured prompt and returns a JSON plan: `{test_name, description, p0_paths, steps[]}`. Steps contain `order`, `action`, `selector`, `value`, `description`. |
| `generator.py` | `generate_code(plan, llm)` — converts the plan JSON into Playwright Python code via the LLM. Strips markdown code fences if the model wraps the output. |
| `service.py` | `generate_test(db, user_id, description, suite_id, test_id?)` — RBAC-checked orchestration: get suite/project, run browser + planner + generator, persist `TestCase` and `TestStep` rows, return `{test_id, code, version, plan}`. |
| `router.py` | `POST /api/v1/ai/generate` — FastAPI endpoint. Accepts `{description, suite_id, test_id?}`, returns `{test_id, code, version, plan}`. |

## Endpoint

```
POST /api/v1/ai/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "description": "user logs in and adds item to cart",
  "suite_id": "<uuid>",
  "test_id": "<uuid | null>"   // omit to create; provide to update
}

→ 200
{
  "test_id": "<uuid>",
  "code": "async def test_...(page):\n    ...",
  "version": 1,
  "plan": { "test_name": "...", "steps": [...] }
}
```

## LLM Provider selection

Set `LLM_PROVIDER` env var (or `llm_provider` in config) to `claude` (default), `openai`, or `gemini`. Corresponding API key must also be set (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`).

## Version bumping

Every time `/ai/generate` is called with an existing `test_id`, `TestCase.version` increments by 1. Old steps are replaced with the new plan's steps.

## RBAC

Requires at least `member` role in the organization that owns the suite's project. Enforced in `service.py` via `require_role(...)`.
