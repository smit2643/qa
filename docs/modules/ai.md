# AI Module

Location: `backend/modules/ai/`

Handles all AI-powered functionality: test generation from natural language, accessibility tree analysis, and self-healing selector repair.

---

## Files

| File | Responsibility |
|---|---|
| `provider.py` | LLM abstraction layer — swap Claude/Gemini/GPT-4o in config |
| `prompts.py` | All prompt templates (generation, healing, failure analysis) |
| `service.py` | Orchestrates browser-use + LLM to produce test code |
| `router.py` | FastAPI endpoints: `/ai/generate`, `/ai/heal` |

---

## LLM Provider Abstraction

`provider.py` defines a `LLMProvider` abstract base class with a single `complete(system, user) -> str` method.

`ClaudeProvider` is the default implementation using `claude-sonnet-4-6`.

**To swap providers:** Change `get_provider()` to return a different implementation. No other code changes needed.

```python
# To add Gemini support:
class GeminiProvider(LLMProvider):
    def complete(self, system: str, user: str) -> str:
        # Use google-generativeai SDK
        ...

def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiProvider()
    return ClaudeProvider()
```

---

## Test Generation Pipeline

```
User input (description + target_url)
         │
         ▼
browser-use agent visits target_url
         │
         ▼
Accessibility tree snapshot extracted
         │
         ▼
Claude receives: description + tree + URL
         │
         ▼
Returns: async def run_test(page) — Playwright code
         │
         ▼
Stored in test_cases table
```

### Why accessibility tree (not CSS selectors)?

CSS classes change frequently. The accessibility tree (`role=button, name=Login`) reflects semantic meaning, which stays stable across UI redesigns. This is the same approach used by bug0 and Playwright's recommended locator strategy.

---

## Self-Healing Pipeline

Triggered by the runner when a selector fails:

```
Runner: playwright raises "Element not found" on selector X
         │
         ▼
Runner calls POST /api/v1/ai/heal
         │
         ▼
Backend: send {broken_selector, current_accessibility_tree} to Claude
         │
         ▼
Claude returns corrected selector string
         │
         ▼
Runner retries test with new selector (max 2 retries)
         │
         ├── Success → update test_cases.code in DB
         └── Failure → mark result failed, generate AI summary
```

---

## Prompts

All prompts live in `prompts.py` as constants + builder functions.

| Prompt | Purpose |
|---|---|
| `SYSTEM_TEST_GENERATOR` | System prompt for test generation |
| `test_generation_prompt()` | Builds user message with description + URL + tree |
| `SYSTEM_HEALER` | System prompt for selector healing |
| `healing_prompt()` | Builds user message with broken selector + tree |
| `SYSTEM_FAILURE_ANALYZER` | System prompt for failure summaries |
| `failure_analysis_prompt()` | Builds user message with test name + error + code |

---

## browser-use Integration

[browser-use](https://github.com/browser-use/browser-use) is a Python library that connects LLMs to Playwright browsers. We use it specifically to:

1. Visit the target URL in a headless browser
2. Extract the full accessibility tree snapshot
3. Pass the tree to the LLM for stable selector generation

We do **not** use browser-use for test execution — that's done directly with `playwright-python` for full control over assertions, video recording, and traces.

---

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Required for Claude provider |
| `GOOGLE_API_KEY` | Required for Gemini provider (if used) |
| `OPENAI_API_KEY` | Required for GPT-4o provider (if used) |
