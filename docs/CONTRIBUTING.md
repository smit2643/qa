# Contributing

## Branch Strategy

```
main          — production-ready, always deployable
dev           — integration branch
feature/xyz   — feature branches, branch from dev
fix/xyz       — bugfix branches
```

## Commit Convention

```
feat: add AI test generation endpoint
fix: correct selector healing retry logic
chore: update dependencies
docs: add runner module documentation
test: add billing webhook tests
refactor: extract LLM provider abstraction
```

## Development Setup

```bash
# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn main:app --reload

# Runner
cd runner
pip install -e ".[dev]"
playwright install chromium
celery -A celery_app worker --loglevel=debug

# Frontend
cd frontend
npm install
npm run dev
```

## Testing

```bash
# Backend — all tests
cd backend && pytest tests/ -v

# Backend — single module
pytest tests/test_auth.py -v

# Runner
cd runner && pytest tests/ -v

# Frontend types
cd frontend && npx tsc --noEmit
```

## Documentation Rule

**Every new module, feature, or API endpoint must have its doc updated.**

- New backend module → add `docs/modules/<module>.md`
- New API endpoint → update `docs/api/reference.md`
- Architecture change → update `docs/architecture/overview.md`
- New env var → update `docs/deployment/env-vars.md`

Docs that are stale are treated as bugs.

## Code Standards

- **Backend:** Type hints everywhere, Pydantic schemas for all I/O, no raw SQL
- **Frontend:** TypeScript strict mode, no `any` except where unavoidable
- **Tests:** TDD — write failing test first, then implementation
- **No secrets in code** — all config via environment variables
