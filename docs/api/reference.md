# API Reference

Base URL: `http://localhost:8000/api/v1`

All authenticated endpoints require: `Authorization: Bearer <token>`

---

## Auth

### POST `/auth/signup`
Create account + personal organization.

**Body:**
```json
{ "email": "user@example.com", "name": "Alice", "password": "secret123" }
```
**Response:** `{ "access_token": "...", "token_type": "bearer" }`

---

### POST `/auth/login`
**Body:**
```json
{ "email": "user@example.com", "password": "secret123" }
```
**Response:** `{ "access_token": "...", "token_type": "bearer" }`

---

### GET `/auth/me` 🔒
**Response:** `{ "id": "...", "email": "...", "name": "..." }`

---

## Projects

### POST `/projects` 🔒
Create project.

**Body:**
```json
{ "name": "My App", "target_url": "https://myapp.com" }
```
**Response:** `{ "id", "name", "target_url", "api_key", "created_at" }`

---

### GET `/projects` 🔒
List all projects for current user's org.

---

### GET `/projects/{project_id}` 🔒

---

### POST `/projects/{project_id}/suites` 🔒
**Body:** `{ "name": "Login Suite" }`

---

### GET `/projects/{project_id}/suites` 🔒

---

## AI Test Generation

### POST `/ai/generate` 🔒
Generate a Playwright test from natural language.

**Body:**
```json
{
  "suite_id": "...",
  "name": "Login flow",
  "description": "User enters email and password then clicks login button and lands on dashboard",
  "target_url": "https://myapp.com/login"
}
```
**Response:** `{ "id", "name", "description", "code", "version" }`

> Note: This call visits the target URL with a headless browser and calls the LLM. Expect 5–15 seconds.

---

### POST `/ai/heal`
Self-healing endpoint called internally by runner workers.

**Body:**
```json
{
  "broken_selector": "div.login-btn-v2",
  "accessibility_tree": "{ role: button, name: Sign in, ... }"
}
```
**Response:** `{ "corrected_selector": "role=button[name='Sign in']" }`

---

## Jobs (Run Execution)

### POST `/runs/trigger` 🔒
Trigger a test suite run manually.

**Body:**
```json
{
  "suite_id": "...",
  "trigger": "manual",
  "branch": "main",
  "commit_sha": "abc1234"
}
```
**Response:** `{ "id", "suite_id", "status", "trigger", "created_at" }`

---

### POST `/runs/trigger/ci?api_key=<key>`
CI/CD trigger — uses project API key instead of JWT.

Same body as above. `api_key` passed as query param.

**GitHub Actions example:**
```yaml
- name: Run Bug0 tests
  run: |
    curl -X POST "$BUG0_URL/api/v1/runs/trigger/ci?api_key=$BUG0_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"suite_id\": \"$SUITE_ID\", \"trigger\": \"api\", \"branch\": \"$GITHUB_REF_NAME\", \"commit_sha\": \"$GITHUB_SHA\"}"
```

---

### GET `/runs/{run_id}` 🔒
Get run status.

---

### PATCH `/runs/{run_id}/results/{result_id}`
Internal endpoint — called by runner workers only. Updates a single test result.

**Body:**
```json
{
  "status": "passed",
  "video_url": "http://minio:9000/bucket/runs/.../video.webm",
  "log_url": "http://minio:9000/bucket/runs/.../console.log",
  "error_message": null
}
```

---

## Reporting

### GET `/reporting/runs/{run_id}` 🔒
Full run detail with all results.

**Response:**
```json
{
  "id": "...",
  "status": "failed",
  "results": [
    {
      "id": "...",
      "status": "failed",
      "video_url": "...",
      "log_url": "...",
      "ai_summary": "The login button was not found. The page may have updated its DOM structure.",
      "error_message": "TimeoutError: Locator 'div.btn-login' not visible"
    }
  ]
}
```

---

### GET `/reporting/suites/{suite_id}/runs` 🔒
Run history for a suite (latest 20 by default).

---

### POST `/reporting/results/{result_id}/analyze` 🔒
Generate AI failure summary for a result on demand.

---

## Billing

### POST `/billing/checkout` 🔒
Create Stripe checkout session.

**Body:** `{ "plan": "pro" }`
**Response:** `{ "checkout_url": "https://checkout.stripe.com/..." }`

---

### POST `/billing/webhook`
Stripe webhook receiver. Requires `Stripe-Signature` header.

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request (validation error, duplicate, etc.) |
| 401 | Unauthenticated or invalid token |
| 403 | Forbidden (insufficient role) |
| 404 | Resource not found |
| 500 | Internal server error |
