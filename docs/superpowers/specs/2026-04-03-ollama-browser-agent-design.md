# Ollama-Compatible Custom Browser Agent Design

**Date:** 2026-04-03
**Status:** Approved
**Goal:** Replace `browser_use.Agent` with a custom Playwright-based browser agent loop that works fully with Ollama qwen3.5 vision — giving the same real-browser-interaction experience as the original Bug0 browser-use approach.

---

## Problem

`browser_use` only supports Claude and OpenAI. It requires the LLM to output strict JSON action schemas at every step. Ollama models (including qwen3.5) don't reliably follow this format, causing the agent to fail after 6 consecutive action parse errors.

All other features (code generation, screen recording, video upload, test execution) already work with Ollama.

---

## Solution — Custom Browser Agent Loop

Build a lightweight browser agent in `browser.py` that:
1. Controls a real Playwright headless browser
2. Takes a screenshot at each step
3. Sends screenshot + task + history to Ollama qwen3.5 vision
4. Executes the returned action in Playwright
5. Records steps in our standard format
6. Passes steps to the existing `generator.py` → Playwright code

This is functionally identical to browser-use but driven by Ollama vision instead of a third-party library.

---

## Architecture

### Call Chain (unchanged externally)
```
POST /ai/generate
  → ai/service.py: generate_test()
      → ai/browser.py: run_agent()     ← REPLACED
          → ai/generator.py: generate_code()   ← unchanged
```

### Custom Agent Loop (new `run_agent` implementation)

```
run_agent(task, target_url, storage_state_json, max_steps=25):
  1. Launch Playwright headless Chromium
  2. Apply storage_state_json if provided (auth state)
  3. Navigate to target_url
  4. step_history = []
  5. Loop up to max_steps:
     a. screenshot_bytes = page.screenshot()
     b. response = llm.complete(vision_message(screenshot, task, history, url))
     c. action = parse_json(response)
     d. execute_action(page, action)  → may retry up to 3x on failure
     e. append to step_history
     f. if action.done → break
  6. return normalize_steps(step_history)
```

### LLM Prompt Design

**System prompt:**
```
You are a browser automation agent. Look at the screenshot and decide 
the next single action to complete the task. Respond with JSON only — 
no explanation, no markdown.
```

**User message per step (multimodal):**
```
Task: {description}
Current URL: {url}
Steps completed so far: {json history}

What is the next action? Respond ONLY with this JSON:
{
  "action": "click|type|navigate|assert|done",
  "selector": "visible text, label, or placeholder of the element",
  "value": "URL to navigate to, or text to type (null otherwise)",
  "description": "what you are doing",
  "done": false
}
Set done=true when the task is fully complete.
```

### Action Execution

| LLM action | Playwright execution (in order of fallback) |
|---|---|
| `navigate` | `page.goto(value)` |
| `click` | `get_by_role("button/link", name=selector)` → `get_by_text(selector)` → `get_by_label(selector)` |
| `type` | `get_by_label(selector)` → `get_by_placeholder(selector)` → `get_by_role("textbox")` |
| `assert` | `expect(page.get_by_text(value)).to_be_visible()` |
| `done` | break loop |

### Error Handling

- **Action fails** (element not found, timeout): retry up to 3x — include failure message in next LLM prompt so it can try a different selector
- **JSON parse fails**: retry the LLM call once with a reminder to respond with JSON only
- **3 consecutive step failures**: stop gracefully, return steps recorded so far
- **max_steps reached**: stop, return what was recorded

---

## Provider Compatibility

The new custom agent path is **Ollama-only**. All other providers keep using the existing `browser_use.Agent` path:

```python
def _get_browser_agent(provider):
    if provider == "ollama":
        return CustomOllamaAgent(...)   # new
    else:
        return browser_use.Agent(...)   # existing (claude, openai)
```

This preserves full backward compatibility for future Claude/OpenAI use.

---

## Files Changed

| File | Change |
|---|---|
| `backend/modules/ai/browser.py` | Add `_run_custom_agent()` function, call it when provider is `ollama` |
| `backend/modules/ai/llm.py` | No change needed (vision messages already supported) |
| `backend/modules/ai/generator.py` | No change |
| `backend/modules/ai/service.py` | No change |
| All other modules | No change |

---

## What Stays the Same

- Screen recording upload → step extraction → code generation ✅
- Video upload → frame analysis → code generation ✅ (needs vision fix — separate)
- Test execution (Celery + Playwright executor) ✅
- All CRUD endpoints ✅
- Frontend UI ✅

---

## Success Criteria

- User types "login with email and password" → agent navigates real site → records real steps → Playwright code generated
- Agent handles: navigation, clicking buttons/links, typing in fields, assertions
- If element not found, agent retries with different approach
- All existing providers (claude, openai) continue to work unchanged
