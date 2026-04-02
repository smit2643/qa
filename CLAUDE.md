# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

Bug0 clone — AI-powered E2E testing SaaS. Plain English (or screen recording / video) → Playwright test code → parallel execution → results. Built phase by phase; see `docs/PHASES.md` for current status and `docs/DEMO.md` for the demo script.

**Demo-first strategy:** Phases 4 (input methods) → 5 (execution) → 8 (frontend) are the priority before Phases 6, 7, 9, 10.

---

## Commands

All backend commands run from `backend/` with the venv activated:

```bash
cd backend
source .venv/bin/activate
```

### Run tests
```bash
pytest tests/ -v                        # all tests
pytest tests/test_ai.py -v              # single file
pytest tests/ -k "test_create_project"  # single test by name
```

Tests use in-memory SQLite — no Docker needed.

### Start API (local dev)
```bash
# Start infrastructure first
cd infra && docker compose up -d postgres redis minio

# Run migrations (first time or after model changes)
cd backend && alembic upgrade head

# Start API
uvicorn main:app --reload --port 8080
# Swagger UI: http://localhost:8080/api/docs
```

### Database migrations
```bash
alembic revision --autogenerate -m "description"  # generate from model changes
alembic upgrade head                               # apply
alembic downgrade -1                               # roll back one
```

### Install dependencies
```bash
# Create venv (Python 3.11 required — use Anaconda if system python is older)
/home/smit/anaconda3/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Architecture

### Repository layout
```
backend/        FastAPI monolith — all API logic
infra/          Docker Compose (postgres, redis, minio, nginx)
runner/         Celery workers for test execution (Phase 5)
frontend/       Next.js 14 app (Phase 8)
docs/           All documentation — keep these updated on every change
```

### Backend structure

Every module under `backend/modules/` follows the same 4-file pattern:
- `schemas.py` — Pydantic request/response models
- `service.py` — business logic (no HTTP concerns)
- `router.py` — FastAPI routes, dependency injection only
- `__init__.py` — empty

Routers are mounted in `main.py` under `/api/v1`. The app is created via a factory function `create_app()` so Sentry only initialises inside it (not at import time).

### Data hierarchy
```
Organization → Project (has api_key + storage_state_json)
                └── TestSuite
                     └── TestCase (has code + version)
                          └── TestStep (action/selector/value/order)

TestRun → TestResult → VisualDiff, HealingSuggestion
```

All models use `UUIDMixin` (string UUID PK) + `TimestampMixin` (timezone-aware `created_at`/`updated_at`) from `models/base.py`. Import all models via `from models import ...` (they're all in `models/__init__.py`).

### RBAC

Every protected service function calls `require_role(db, user_id, org_id, minimum_role)` from `modules/organizations/service.py`. Never duplicate this logic.

Role hierarchy (lowest → highest): `viewer < member < admin < owner`

Access chain for nested resources: TestStep → TestCase → TestSuite → Project → Organization. Each service resolves `org_id` by walking up this chain.

### Database / sessions

`get_db()` in `core/database.py` is the FastAPI dependency. Always inject via `Depends(get_db)` in routers, never import `SessionLocal` directly in routers.

### Tests

`tests/conftest.py` provides a `client` fixture (function-scoped) using in-memory SQLite + `StaticPool`. It overrides `get_db` and tears down after each test. All new test files use this fixture.

Mock LLM and browser calls in tests — never make real API calls:
```python
from unittest.mock import AsyncMock, patch
with patch("modules.ai.browser.get_accessibility_tree", new=AsyncMock(return_value="...")):
    ...
```

### AI engine (`modules/ai/`)

Pipeline: `browser.py` (browser-use Agent navigates app → real steps) → `generator.py` (steps → Playwright code) → `service.py` (orchestrates + saves to DB).

`browser_use.Agent` is the core — it autonomously navigates the target app, records real clicks/inputs, and returns `AgentHistoryList`. We extract real actions from `history.model_actions()` and convert them to `TestStep` records + Playwright code. This is far more reliable than static page snapshots.

`LLMProvider` in `llm.py` is the unified interface. Default model is `claude-sonnet-4-6`. Switch provider via `LLM_PROVIDER` env var (`claude` | `openai` | `gemini`).

Three input methods all converge on `generate-from-steps`: text (browser-use Agent), screen recording (event extraction), video upload (Claude Vision frame analysis).

---

## Key Conventions

- **Ports:** PostgreSQL on `5434` (Docker), backend API on `8080` (another project owns 5432 and 8000)
- **Timestamps:** Always use `datetime.now(timezone.utc)` + `DateTime(timezone=True)` — never `utcnow()`
- **Error handling:** Raise `HTTPException` in service functions (not `ValueError`) so routers stay thin
- **Docs:** Update the relevant `docs/modules/*.md` whenever a module changes. Update `docs/PHASES.md` when a phase completes.
- **Phase worktrees:** Each phase gets a git worktree at `.worktrees/phase-N-name/` on a `feature/phase-N-name` branch, merged to `master` on completion
- **bcrypt:** Pinned to `bcrypt==4.0.1` — passlib compatibility on Python 3.11
- **Timing-safe login:** `modules/auth/service.py` always runs bcrypt even when user not found (prevents email enumeration)

---

## Environment

Copy `.env.example` → `.env`. Minimum required to run locally:

```
DATABASE_URL=postgresql://bug0:bug0pass@localhost:5434/bug0db
SECRET_KEY=<32+ random chars>
ANTHROPIC_API_KEY=sk-ant-...   # only needed for /ai/generate
LLM_PROVIDER=claude
```

Full env var reference: `docs/deployment/env-vars.md`
