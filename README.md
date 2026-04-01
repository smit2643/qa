# Bug0 — AI-Powered E2E Testing Platform

A production-grade SaaS clone of [bug0.com](https://bug0.com). Autonomous AI QA engineer that generates, runs, self-heals, and reports on Playwright browser tests — on every commit, 24/7.

## What it does

- **Natural language → tests**: Describe a flow in plain English, AI generates a Playwright test
- **Parallel execution**: Run hundreds of tests simultaneously via Celery workers
- **Self-healing**: Broken selectors auto-fixed by AI using accessibility tree analysis
- **Full reporting**: Video playback, console logs, HAR traces, AI failure summaries
- **CI/CD integration**: GitHub Actions, webhook API trigger, PR status checks
- **Multi-tenant SaaS**: Organizations, teams, projects, API keys, Stripe billing

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui |
| Backend API | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic |
| Test Runner | Playwright-Python, Celery, browser-use |
| AI | Claude 3.7 Sonnet (default, swappable via provider abstraction) |
| Database | PostgreSQL 16 |
| Queue / Cache | Redis |
| Storage | MinIO (dev) → AWS S3 (prod) |
| Auth | JWT + OAuth2 (GitHub, Google) |
| Billing | Stripe |
| Infra | Docker, Docker Compose, Nginx |

## Quick Start

```bash
# 1. Clone and configure
git clone <repo>
cp .env.example .env
# Edit .env with your API keys

# 2. Start infrastructure
cd infra && docker compose up -d

# 3. Run migrations
cd backend && alembic upgrade head

# 4. Start backend
uvicorn main:app --reload

# 5. Start runner workers
cd runner && celery -A celery_app worker --loglevel=info

# 6. Start frontend
cd frontend && npm run dev
```

Visit http://localhost:3000

## Project Structure

```
/
├── frontend/          # Next.js 14 app
├── backend/           # FastAPI monolith
├── runner/            # Celery test execution workers
├── infra/             # Docker Compose, Nginx, Postgres init
└── docs/              # All documentation
    ├── architecture/  # System design, data flow diagrams
    ├── api/           # API reference
    ├── modules/       # Per-module documentation
    ├── deployment/    # Deploy guides (Docker, cloud)
    └── superpowers/   # Design specs and implementation plans
```

## Documentation

| Doc | Description |
|---|---|
| [Architecture](docs/architecture/overview.md) | System design, component diagram, data flow |
| [API Reference](docs/api/reference.md) | All REST endpoints |
| [Auth Module](docs/modules/auth.md) | JWT auth, OAuth2, tokens |
| [AI Module](docs/modules/ai.md) | Test generation, self-healing, LLM providers |
| [Runner](docs/modules/runner.md) | Celery workers, Playwright execution, artifacts |
| [Reporting](docs/modules/reporting.md) | Run history, AI failure analysis |
| [Billing](docs/modules/billing.md) | Stripe plans, webhooks |
| [Environment Variables](docs/deployment/env-vars.md) | All config options |
| [Docker Deploy](docs/deployment/docker.md) | Production Docker setup |
| [Design Spec](docs/superpowers/specs/2026-04-01-bug0-clone-design.md) | Original system design |
| [Implementation Plan](docs/superpowers/plans/2026-04-01-bug0-clone.md) | Step-by-step build plan |

## Development

```bash
# Run backend tests
cd backend && pytest tests/ -v

# Run runner tests
cd runner && pytest tests/ -v

# Run frontend type check
cd frontend && npx tsc --noEmit
```

## License

MIT
