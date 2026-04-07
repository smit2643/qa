# API Reference

Base URL: `http://localhost:8080/api/v1`

All authenticated endpoints (🔒) require: `Authorization: Bearer <token>`

---

## Auth

### POST `/auth/signup`
Create account. A personal organization is auto-created and the user is assigned as `owner`.

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
**Response:** `{ "id": "...", "email": "...", "name": "...", "is_active": true }`

---

### GET `/auth/github`
Redirect to GitHub OAuth. Requires `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` in `.env`.

### GET `/auth/github/callback`
GitHub redirects here after authorization. Issues JWT and redirects to `{FRONTEND_URL}/auth/callback?token=<jwt>`.

### GET `/auth/google`
Redirect to Google OAuth. Requires `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env`.

### GET `/auth/google/callback`
Google redirects here after authorization. Issues JWT and redirects to `{FRONTEND_URL}/auth/callback?token=<jwt>`.

> If a user with the same email already exists (password account), OAuth is linked to that account automatically.

---

## Organizations

### GET `/organizations` 🔒
List all organizations the current user belongs to.

**Response:** `[{ "id", "name", "slug", "plan", "created_at" }]`

---

### GET `/organizations/{org_id}` 🔒

---

### PATCH `/organizations/{org_id}` 🔒
Rename org. Requires `admin`+.

**Body:** `{ "name": "New Name" }`

---

### GET `/organizations/{org_id}/members` 🔒
List all members with their roles.

**Response:** `[{ "user_id", "user_name", "user_email", "role", "joined_at" }]`

---

### POST `/organizations/{org_id}/members` 🔒
Invite a user by email. Requires `admin`+.

**Body:** `{ "email": "user@example.com", "role": "member" }`

> Roles: `owner` | `admin` | `member` | `viewer`

---

### PATCH `/organizations/{org_id}/members/{user_id}` 🔒
Update a member's role. Requires `admin`+.

**Body:** `{ "role": "admin" }`

---

### DELETE `/organizations/{org_id}/members/{user_id}` 🔒
Remove a member. Requires `admin`+. Cannot remove yourself.

---

## Projects

### POST `/projects` 🔒
Create a project. Requires `member`+ in the org.

**Body:**
```json
{ "name": "My App", "target_url": "https://myapp.com", "organization_id": "..." }
```
**Response:** `{ "id", "organization_id", "name", "target_url", "api_key", "storage_state_json", "created_at", "updated_at" }`

> `api_key` is auto-generated — use it for CI/CD triggers.

---

### GET `/organizations/{org_id}/projects` 🔒
List all projects in an org.

---

### GET `/projects` 🔒
List all projects the current user can access across all their organizations.

**Response:** Array of project objects.

---

### GET `/projects/{project_id}` 🔒

---

### PATCH `/projects/{project_id}` 🔒
Update name or target_url. Requires `admin`+.

**Body:** `{ "name": "New Name", "target_url": "https://newurl.com" }`

---

### DELETE `/projects/{project_id}` 🔒
Requires `owner`.

---

### POST `/projects/{project_id}/rotate-api-key` 🔒
Generate a new API key, invalidating the old one. Requires `admin`+.

**Response:** Updated project with new `api_key`.

---

### POST `/projects/{project_id}/storage-state` 🔒
Upload a Playwright `storageState.json` for authenticated test flows. Requires `admin`+.

**Body:** `multipart/form-data` with field `file` (must be valid JSON).

---

### DELETE `/projects/{project_id}/storage-state` 🔒
Remove the stored auth state. Requires `admin`+.

---

## Test Suites

### POST `/suites` 🔒
Create a suite inside a project. Requires `member`+.

**Body:** `{ "name": "Smoke Tests", "project_id": "..." }`

---

### GET `/projects/{project_id}/suites` 🔒
List all suites in a project.

---

### GET `/suites/{suite_id}` 🔒

---

### PATCH `/suites/{suite_id}` 🔒
Rename suite. Requires `member`+.

**Body:** `{ "name": "New Name" }`

---

### DELETE `/suites/{suite_id}` 🔒
Requires `admin`+.

---

## Test Cases

### POST `/tests` 🔒
Create a test case. Requires `member`+.

**Body:**
```json
{
  "name": "User can log in",
  "suite_id": "...",
  "description": "Verify the login flow works end to end",
  "input_method": "text"
}
```
> `input_method`: `text` | `recording` | `video`

**Response:** `{ "id", "suite_id", "name", "description", "code", "version", "input_method", "created_at", "updated_at" }`

---

### GET `/suites/{suite_id}/tests` 🔒
List all tests in a suite.

---

### GET `/tests/{test_id}` 🔒

---

### PATCH `/tests/{test_id}` 🔒
Update test. Requires `member`+.

**Body:** `{ "name": "...", "description": "...", "code": "..." }`

> Updating `code` automatically increments `version`.

---

### DELETE `/tests/{test_id}` 🔒
Requires `admin`+.

---

## Test Steps

### POST `/steps` 🔒
Add a step to a test. Requires `member`+.

**Body:**
```json
{
  "test_id": "...",
  "order": 0,
  "action": "navigate",
  "selector": null,
  "value": "https://myapp.com/login",
  "description": "Go to login page",
  "is_assertion": false
}
```
> `action`: `navigate` | `click` | `type` | `assert` | `wait`

---

### GET `/tests/{test_id}/steps` 🔒
List all steps for a test, ordered by `order`.

---

### GET `/steps/{step_id}` 🔒

---

### PATCH `/steps/{step_id}` 🔒
Update a step. Requires `member`+.

---

### DELETE `/steps/{step_id}` 🔒
Requires `member`+.

---

### POST `/tests/{test_id}/steps/reorder` 🔒
Reorder steps (for drag-and-drop visual editor). Requires `member`+.

**Body:** `{ "step_ids": ["id1", "id2", "id3"] }`

> Steps are reassigned `order` values (0-indexed) in the given sequence.

---

## AI Test Generation

### POST `/ai/generate` 🔒
Generate a Playwright test from a plain English description.

**Body:**
```json
{
  "description": "user logs in with email and password and lands on dashboard",
  "suite_id": "...",
  "test_id": "..."
}
```
> `test_id` is optional. If provided, updates that test (version increments). If omitted, creates a new test.

**Response:**
```json
{
  "test_id": "...",
  "code": "async def test_user_login(page):\n    ...",
  "version": 1,
  "plan": {
    "test_name": "User Login",
    "description": "...",
    "p0_paths": ["login flow"],
    "steps": [...]
  }
}
```

> This endpoint visits the project's `target_url` in a headless browser, reads the accessibility tree, plans the test, then generates code. Expect 10–30 seconds.

**LLM provider** is set by `LLM_PROVIDER` in `.env` (`claude` | `openai` | `gemini`).

---

## Jobs (Run Execution — Phase 5)

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

**GitHub Actions example:**
```yaml
- name: Run Bug0 tests
  run: |
    curl -X POST "$BUG0_URL/api/v1/runs/trigger/ci?api_key=$BUG0_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"suite_id": "$SUITE_ID", "trigger": "api", "branch": "$GITHUB_REF_NAME", "commit_sha": "$GITHUB_SHA"}'
```

---

### GET `/runs/{run_id}` 🔒
Get run status and results.

---

## Reporting (Phase 6)

### GET `/reporting/runs/{run_id}` 🔒
Full run detail with all results, AI summaries, and artifact URLs.

---

### GET `/reporting/suites/{suite_id}/runs` 🔒
Run history for a suite (latest 20 by default).

---

### POST `/reporting/results/{result_id}/analyze` 🔒
Generate AI failure summary for a result on demand.

---

## Billing (Phase 9)

### POST `/billing/checkout` 🔒
Create Stripe checkout session.

**Body:** `{ "plan": "studio" }`

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
| 401 | Unauthenticated or invalid/expired token |
| 403 | Forbidden — insufficient role |
| 404 | Resource not found |
| 422 | Unprocessable entity (e.g. invalid JSON file upload) |
| 500 | Internal server error |
