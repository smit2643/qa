# Projects, Suites, Tests & Steps Modules

Built in Phase 2. Covers full CRUD for the project management layer: organizations own projects, projects contain test suites, suites contain test cases, and test cases contain steps.

---

## Module Locations

| Module | Path | Responsibility |
|---|---|---|
| Projects | `backend/modules/projects/` | Project CRUD, API key management, storageState upload |
| Suites | `backend/modules/suites/` | TestSuite CRUD under projects |
| Tests | `backend/modules/tests/` | TestCase CRUD + version history |
| Steps | `backend/modules/steps/` | Individual step CRUD + reorder |

Each module follows the same layout:

| File | Responsibility |
|---|---|
| `schemas.py` | Pydantic request/response models |
| `service.py` | Business logic + RBAC enforcement |
| `router.py` | FastAPI route definitions |

---

## RBAC Overview

All operations check the caller's membership role in the owning organization before proceeding. Roles in ascending order:

```
viewer < member < admin < owner
```

The access chain for nested resources:

```
TestStep → TestCase → TestSuite → Project → Organization → membership role check
```

The helper used everywhere:

```python
from modules.organizations.service import require_role

require_role(db, user_id, org_id, Role.member)  # raises 403 if insufficient
```

---

## Projects

### Files

`backend/modules/projects/` — `schemas.py`, `service.py`, `router.py`

### API Endpoints

| Method | Path | Description | Min Role |
|---|---|---|---|
| `POST` | `/api/v1/projects` | Create a project | member |
| `GET` | `/api/v1/projects` | List all projects across all user's orgs | viewer |
| `GET` | `/api/v1/organizations/{org_id}/projects` | List all projects in an org | viewer |
| `GET` | `/api/v1/projects/{project_id}` | Get a single project | viewer |
| `PATCH` | `/api/v1/projects/{project_id}` | Update project name or target URL | admin |
| `DELETE` | `/api/v1/projects/{project_id}` | Delete project (cascades to suites/tests/steps) | owner |
| `POST` | `/api/v1/projects/{project_id}/rotate-api-key` | Generate a new API key | admin |
| `POST` | `/api/v1/projects/{project_id}/storage-state` | Upload storageState.json | admin |
| `DELETE` | `/api/v1/projects/{project_id}/storage-state` | Remove storageState.json | admin |

### Create Request Body

```json
{
  "organization_id": "<org_id>",
  "name": "My Project",
  "target_url": "https://app.example.com"
}
```

### Response Shape

```json
{
  "id": "proj_abc123",
  "organization_id": "org_xyz",
  "name": "My Project",
  "target_url": "https://app.example.com",
  "api_key": "a3f9...<64-char hex>",
  "storage_state_json": null,
  "created_at": "2026-04-02T10:00:00Z",
  "updated_at": "2026-04-02T10:00:00Z"
}
```

---

## Project API Keys

Every project is created with an auto-generated API key (`secrets.token_hex(32)` — 64 hex chars). The key is used to authenticate CI/CD triggers without requiring a user session.

### Rotating the Key

```
POST /api/v1/projects/{project_id}/rotate-api-key
Authorization: Bearer <jwt>
```

Returns the updated project with the new `api_key`. The previous key is immediately invalidated.

### Using the Key in CI

Pass the key in the `X-API-Key` header when triggering a test job from your pipeline:

```bash
curl -X POST https://your-instance.com/api/v1/jobs/trigger \
  -H "X-API-Key: a3f9c1d2e4b5..." \
  -H "Content-Type: application/json" \
  -d '{"suite_id": "suite_abc123", "browser": "chromium"}'
```

Store the key as a CI secret (e.g., `BUG0_API_KEY` in GitHub Actions secrets) and never commit it to source control.

---

## storageState.json

### What It Is

Playwright's `storageState` captures browser authentication state — cookies, `localStorage`, and `sessionStorage` — into a JSON file. When injected into a test context, Playwright starts with the browser already logged in, bypassing the login flow entirely.

This is critical for testing pages that sit behind authentication without repeating the login steps in every test.

### How to Capture It

```javascript
// In your Playwright setup script
await page.context().storageState({ path: 'storageState.json' });
```

### Uploading to a Project

```bash
curl -X POST https://your-instance.com/api/v1/projects/{project_id}/storage-state \
  -H "Authorization: Bearer <jwt>" \
  -F "file=@storageState.json"
```

The file must be valid JSON. The backend validates this on upload and returns `422 Unprocessable Entity` if the content is not valid JSON.

### Removing It

```bash
curl -X DELETE https://your-instance.com/api/v1/projects/{project_id}/storage-state \
  -H "Authorization: Bearer <jwt>"
```

Returns `{"message": "Storage state removed"}`. The `storage_state_json` field on the project is set to `null`.

### How It Is Used

At execution time, the runner reads `project.storage_state_json` and passes it to Playwright's `browser.newContext({ storageState: <json> })`. Tests run as a pre-authenticated user without any login steps.

---

## Suites

### Files

`backend/modules/suites/` — `schemas.py`, `service.py`, `router.py`

### API Endpoints

| Method | Path | Description | Min Role |
|---|---|---|---|
| `POST` | `/api/v1/suites` | Create a suite under a project | member |
| `GET` | `/api/v1/projects/{project_id}/suites` | List suites in a project | viewer |
| `GET` | `/api/v1/suites/{suite_id}` | Get a single suite | viewer |
| `PATCH` | `/api/v1/suites/{suite_id}` | Rename a suite | member |
| `DELETE` | `/api/v1/suites/{suite_id}` | Delete suite (cascades to tests/steps) | admin |

### Create Request Body

```json
{
  "project_id": "<project_id>",
  "name": "Checkout Flow"
}
```

---

## Tests (TestCases)

### Files

`backend/modules/tests/` — `schemas.py`, `service.py`, `router.py`

### API Endpoints

| Method | Path | Description | Min Role |
|---|---|---|---|
| `POST` | `/api/v1/tests` | Create a test case | member |
| `GET` | `/api/v1/suites/{suite_id}/tests` | List tests in a suite | viewer |
| `GET` | `/api/v1/tests/{test_id}` | Get a single test case | viewer |
| `PATCH` | `/api/v1/tests/{test_id}` | Update name, description, or code | member |
| `DELETE` | `/api/v1/tests/{test_id}` | Delete a test case | admin |

### Create Request Body

```json
{
  "suite_id": "<suite_id>",
  "name": "Add item to cart",
  "description": "Verifies that a user can add a product to the cart",
  "input_method": "text"
}
```

`input_method` accepts: `text` | `recording` | `video`

### Version History

The `version` field starts at `1` when a test case is created. Every `PATCH` request that includes the `code` field increments `version` by 1:

```python
if data.code is not None:
    test.code = data.code
    test.version += 1
```

This provides a lightweight audit trail of how many times the generated code has been updated. Full version history (storing previous code snapshots) is planned for a later phase.

### Response Shape

```json
{
  "id": "test_abc123",
  "suite_id": "suite_xyz",
  "name": "Add item to cart",
  "description": "Verifies that a user can add a product to the cart",
  "code": "import { test, expect } from '@playwright/test';\n...",
  "version": 3,
  "input_method": "text",
  "created_at": "2026-04-02T10:00:00Z",
  "updated_at": "2026-04-02T10:05:00Z"
}
```

---

## Steps (TestSteps)

### Files

`backend/modules/steps/` — `schemas.py`, `service.py`, `router.py`

Steps represent the individual actions of a test case as structured data. They power the visual step builder in the frontend and are the intermediate representation before code generation.

### API Endpoints

| Method | Path | Description | Min Role |
|---|---|---|---|
| `POST` | `/api/v1/steps` | Create a step on a test | member |
| `GET` | `/api/v1/tests/{test_id}/steps` | List steps for a test (ordered by `order`) | viewer |
| `GET` | `/api/v1/steps/{step_id}` | Get a single step | viewer |
| `PATCH` | `/api/v1/steps/{step_id}` | Update step fields | member |
| `DELETE` | `/api/v1/steps/{step_id}` | Delete a step | member |
| `POST` | `/api/v1/tests/{test_id}/steps/reorder` | Reorder all steps in a test | member |

### Step Actions

| Action | Description |
|---|---|
| `click` | Click on an element identified by `selector` |
| `type` | Type `value` into element identified by `selector` |
| `navigate` | Navigate to the URL in `value` |
| `assert` | Assert that element identified by `selector` is present/visible |
| `wait` | Wait for `value` milliseconds or for `selector` to appear |

### Create Request Body

```json
{
  "test_id": "<test_id>",
  "order": 0,
  "action": "navigate",
  "value": "https://app.example.com/login",
  "selector": null,
  "description": "Open the login page",
  "is_assertion": false
}
```

### Step Response Shape

```json
{
  "id": "step_abc123",
  "test_id": "test_xyz",
  "order": 0,
  "action": "navigate",
  "selector": null,
  "value": "https://app.example.com/login",
  "description": "Open the login page",
  "is_assertion": false,
  "created_at": "2026-04-02T10:00:00Z",
  "updated_at": "2026-04-02T10:00:00Z"
}
```

### Reorder Endpoint

`POST /api/v1/tests/{test_id}/steps/reorder`

Accepts an ordered list of all step IDs for a test. Reassigns `order` values starting from `0`. All `step_ids` must belong to the specified `test_id` — any foreign step ID returns `400 Bad Request`.

```json
{
  "step_ids": ["step_3", "step_1", "step_2"]
}
```

Response: the full list of steps in the new order.

This endpoint is called by the frontend drag-and-drop step editor after the user drops a step into a new position.

---

## Data Hierarchy

```
Organization
└── Project  (has api_key, storage_state_json)
    └── TestSuite
        └── TestCase  (has code, version, input_method)
            └── TestStep  (has order, action, selector, value)
```

All delete operations cascade — deleting a project removes all suites, tests, and steps beneath it.
