# Bug0 — AI-Powered E2E Testing Platform

A production-grade SaaS clone of [bug0.com](https://bug0.com). Autonomous AI QA engineer that generates, runs, self-heals, and reports on Playwright browser tests — on every commit, 24/7.

## What it does

**Test Creation (3 input methods)**
- **Plain English → tests**: Describe a flow, AI generates Playwright code in ~30s
- **Screen Recording**: Record your browser tab in-app → AI extracts steps → generates code
- **Video Upload**: Upload mp4/webm → Claude Vision analyzes frames → generates code
- **Visual Step Editor**: Edit/reorder extracted steps before generating code (drag & drop)

**AI Engine (Multi-Agent)**
- **Planner Agent**: Maps critical user journeys, identifies P0 paths
- **Generator Agent**: Produces resilient Playwright code using accessibility selectors
- **Healer Agent**: Fixes broken tests automatically — 90% healed without intervention
- **Human-in-the-Loop**: Review healing suggestions before they apply

**Test Execution**
- **Parallel execution**: 500+ tests simultaneously
- **Cross-browser**: Chromium, Firefox, WebKit
- **Visual Regression**: Screenshot comparison with pixel-level diffing
- **Live Streaming**: Watch tests run in real-time (split-screen: AI reasoning + browser)
- **Full artifacts**: Video, console logs, HAR traces, visual diffs per run

**Reporting & CI/CD**
- **AI Failure Analysis**: Plain English explanation of every failure
- **Bug Report Generation**: Auto-create actionable bug reports
- **Failure Triage**: Clusters related failures, eliminates noise
- **Release Gates**: Block PR merges based on test results
- **CI Integrations**: GitHub Actions, GitLab, Jenkins, Bitbucket
- **Notifications**: Slack, email, GitHub/GitLab PR comments, JIRA tickets

**SaaS Platform**
- **Multi-tenant**: Organizations, teams, projects, API keys
- **Stripe Billing**: Studio ($250/mo) + Managed ($2,500/mo) tiers
- **RBAC**: Owner / Admin / Member / Viewer
- **Enterprise**: Audit logs, rate limiting, SOC 2 readiness

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui |
| Animations | Framer Motion |
| Drag & Drop | dnd-kit (visual step editor) |
| Charts | Recharts (coverage maps, trend charts) |
| Backend API | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic |
| Test Runner | Playwright-Python, Celery, browser-use |
| AI (default) | Claude Sonnet 4.6 (Anthropic) |
| AI Vision | Claude Vision / GPT-4o (video frame analysis) |
| AI Agents | browser-use (Planner + Generator + Healer) |
| Visual Diff | pixelmatch (screenshot comparison) |
| Database | PostgreSQL 16 + pgvector (failure clustering) |
| Queue / Cache | Redis + Celery |
| Storage | MinIO (dev) → AWS S3 (prod) |
| Auth | JWT + OAuth2 (GitHub, Google) |
| Billing | Stripe (usage + seat) |
| Logging | loguru + Sentry |
| Metrics | Prometheus + Grafana |
| Email | SendGrid |
| Infra | Docker, Docker Compose, Nginx 1.27 |

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
