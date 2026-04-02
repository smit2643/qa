# Demo Script — Bug0 AI Testing Platform

**Setup time:** ~5 minutes
**Demo time:** ~10 minutes
**Wow factor:** AI visits your app and writes Playwright tests in real time

---

## Prerequisites

- Docker running
- `ANTHROPIC_API_KEY` set in `.env`
- Backend running on port 8080

---

## Start the Stack

```bash
# Terminal 1 — infrastructure
cd infra
docker compose up -d postgres redis minio

# Terminal 2 — backend API
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn main:app --reload --port 8080
```

API docs available at: **http://localhost:8080/api/docs**

---

## Demo Flow

### Step 1 — Sign up (30 seconds)

```bash
curl -X POST http://localhost:8080/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@yourapp.com","name":"Demo User","password":"secret123"}'
```

- Account created
- Personal organization auto-created
- JWT token returned

---

### Step 2 — Log in and get token

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@yourapp.com","password":"secret123"}'
```

Copy the `access_token` — use it as `Bearer <token>` for all requests.

---

### Step 3 — Create a project (30 seconds)

```bash
# Get your org ID first
curl http://localhost:8080/api/v1/organizations \
  -H "Authorization: Bearer <token>"

# Create project
curl -X POST http://localhost:8080/api/v1/projects \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App",
    "target_url": "https://yourapp.com",
    "organization_id": "<org_id>"
  }'
```

- Project created with an **auto-generated API key** (for CI/CD)
- `target_url` is where AI will navigate to read the page

---

### Step 4 — Create a test suite

```bash
curl -X POST http://localhost:8080/api/v1/suites \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Smoke Tests", "project_id": "<project_id>"}'
```

---

### Step 5 — AI generates a test (the money shot — ~30 seconds)

```bash
curl -X POST http://localhost:8080/api/v1/ai/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "user logs in with email and password and lands on dashboard",
    "suite_id": "<suite_id>"
  }'
```

**What happens behind the scenes:**
1. AI opens your `target_url` in a headless browser
2. Reads the page accessibility tree (buttons, inputs, links)
3. Planner Agent maps the user journey → structured test plan
4. Generator Agent writes Playwright Python code
5. Test + steps saved to DB automatically

**Response:**
```json
{
  "test_id": "...",
  "version": 1,
  "code": "async def test_user_login(page):\n    await page.goto('https://yourapp.com/login')\n    await page.get_by_label('Email').fill('user@test.com')\n    ...",
  "plan": { "steps": [...] }
}
```

---

### Step 6 — Run the test (Phase 5 — coming soon)

> Tests will execute in parallel across Chromium, Firefox, WebKit.
> Live browser stream visible in the UI.

---

### Step 7 — See results (Phase 5 — coming soon)

> Pass/fail status, video recording, console logs, screenshot diffs.

---

### Step 8 — Full UI (Phase 8 — coming soon)

> Polished Next.js dashboard. Dark mode. Live execution split-screen.

---

## Key Talking Points

| Feature | What to say |
|---|---|
| Accessibility selectors | "No CSS selectors — AI uses roles and labels, 10x more stable when UI changes" |
| LLM swappable | "Claude by default, swap to GPT-4o or Gemini with one env var change" |
| storageState.json | "Upload Playwright auth state — AI can test logged-in flows without re-logging in" |
| Version history | "Every time AI regenerates code, version increments — full history kept" |
| API key per project | "Drop-in CI/CD — one curl command in GitHub Actions triggers your suite" |
| 3 input methods | "Text description today, screen recording and video upload coming next" |

---

## What's Coming Next

| Feature | Phase | Status |
|---|---|---|
| Screen recording → test | 4 | Building next |
| Video upload → test (Claude Vision) | 4 | Building next |
| Run tests (parallel, cross-browser) | 5 | Building next |
| Live browser stream during execution | 5 | Building next |
| Pass/fail + video + visual diff | 5 | Building next |
| Full polished UI | 8 | After 4 + 5 |
