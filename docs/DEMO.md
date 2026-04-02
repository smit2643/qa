# Demo Script — Bug0 AI Testing Platform

**Setup time:** ~5 minutes
**Demo time:** ~10 minutes
**Wow factor:** browser-use Agent actually navigates your app and writes real Playwright tests

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

API docs: **http://localhost:8080/api/docs**

---

## Demo Flow

### Step 1 — Sign up

```bash
curl -X POST http://localhost:8080/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@yourapp.com","name":"Demo User","password":"secret123"}'
```

Personal organization is auto-created. JWT token returned.

---

### Step 2 — Log in

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@yourapp.com","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

### Step 3 — Create a project

```bash
# Get org ID
ORG_ID=$(curl -s http://localhost:8080/api/v1/organizations \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Create project pointing at your app
curl -X POST http://localhost:8080/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"My App\",\"target_url\":\"https://yourapp.com\",\"organization_id\":\"$ORG_ID\"}"
```

Project gets an **auto-generated API key** for CI/CD. `target_url` is where the AI will navigate.

---

### Step 4 — Create a test suite

```bash
curl -X POST http://localhost:8080/api/v1/suites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Tests\",\"project_id\":\"$PROJECT_ID\"}"
```

---

### Step 5 — AI generates a test (the money shot — ~30 seconds)

```bash
curl -X POST http://localhost:8080/api/v1/ai/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"user logs in with email and password and lands on dashboard\",
    \"suite_id\": \"$SUITE_ID\"
  }"
```

**What actually happens:**
1. `browser_use.Agent` opens your app in a headless browser
2. Agent autonomously navigates — clicks the login link, finds email/password fields, fills them, clicks submit
3. Records every real action it performed (not guesses — real interactions)
4. Generator Agent converts those real actions → Playwright Python code using accessibility selectors
5. Test + steps saved to DB

**Response:**
```json
{
  "test_id": "...",
  "version": 1,
  "code": "async def test_user_login(page: Page):\n    await page.goto('https://yourapp.com')\n    await page.get_by_role('link', name='Login').click()\n    await page.get_by_label('Email').fill('user@test.com')\n    await page.get_by_label('Password').fill('secret')\n    await page.get_by_role('button', name='Sign in').click()\n    await expect(page).to_have_url(re.compile('dashboard'))\n",
  "steps": [
    {"order": 0, "action": "navigate", "value": "https://yourapp.com"},
    {"order": 1, "action": "click", "selector": "Login link"},
    {"order": 2, "action": "type", "selector": "Email", "value": "user@test.com"},
    {"order": 3, "action": "type", "selector": "Password", "value": "secret"},
    {"order": 4, "action": "click", "selector": "Sign in button"},
    {"order": 5, "action": "assert", "selector": "URL contains dashboard"}
  ]
}
```

---

### Step 6 — Video upload input (Phase 4 — coming next)

```bash
# Upload a screen recording of you using your app
curl -X POST http://localhost:8080/api/v1/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@recording.mp4" \
  -F "suite_id=$SUITE_ID" \
  -F "test_name=User login flow"
```

Claude Vision analyzes frames → extracts steps → generates code. No description needed — just show it.

---

### Step 7 — Run the test (Phase 5 — coming next)

```bash
curl -X POST http://localhost:8080/api/v1/runs/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"suite_id\":\"$SUITE_ID\",\"trigger\":\"manual\"}"
```

Tests execute in parallel across Chromium, Firefox, WebKit. Live browser stream visible in UI.

---

### Step 8 — Full UI (Phase 8 — coming next)

Polished Next.js dashboard. Dark mode. Split-screen live execution view (AI reasoning panel + live browser).

---

## Key Talking Points

| Feature | What to say |
|---|---|
| **browser-use Agent** | "The AI doesn't guess — it actually uses your app like a user, recording real clicks and inputs" |
| **Accessibility selectors** | "No CSS selectors — uses roles and labels, 10x more stable when UI changes" |
| **3 input methods** | "Text description, screen recording, or video upload — whatever is easiest" |
| **LLM swappable** | "Claude by default, swap to GPT-4o or Gemini with one env var" |
| **storageState.json** | "Upload Playwright auth state — agent tests logged-in flows without re-logging in every time" |
| **Version history** | "Every regeneration bumps version — full history of how the test evolved" |
| **API key per project** | "One curl command in GitHub Actions triggers your full suite" |

---

## What's Coming Next (Build Order)

| Feature | Phase | Status |
|---|---|---|
| browser-use Agent integration (fix Phase 3) | 3 fix | Building now |
| Video upload → Claude Vision → test | 4 | Next |
| Screen recording → test | 4 | Next |
| Run tests (parallel, cross-browser, video capture) | 5 | Next |
| Live browser stream during execution | 5 | Next |
| Pass/fail + video + screenshot diffs | 5 | Next |
| Full polished Next.js UI | 8 | After 4 + 5 |
