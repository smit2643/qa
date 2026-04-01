# Bug0.com Clone — System Design Spec
**Date:** 2026-04-01  
**Status:** Approved  

---

## Overview

A full SaaS clone of bug0.com: an AI-powered end-to-end testing platform that acts as an autonomous QA engineer. Users describe test flows in natural language (or upload videos/recordings), and the system generates, executes, self-heals, and reports on Playwright-based browser tests — continuously, on every commit.

---

## Goals

- Natural language → Playwright test generation via AI
- Video / screen recording → test generation
- Parallel test execution with video, logs, and traces per run
- Self-healing tests (broken selectors auto-fixed by AI)
- CI/CD integration (GitHub Actions, REST API webhook)
- Dashboard: run history, video playback, AI failure analysis, notifications
- Multi-tenant SaaS: organizations, projects, teams, API keys, billing

---

## Architecture

### Two deployable units

1. **Backend** (`/backend`) — FastAPI Python monolith with clean internal modules
2. **Test Runner** (`/runner`) — Python Celery workers using playwright-python + browser-use

Both share **PostgreSQL** (primary DB), **Redis** (queue + cache), and **MinIO** (S3-compatible artifact storage).

```
┌──────────────────────────────────────────────────────────┐
│                  FRONTEND (Next.js 14)                   │
│            Tailwind CSS + shadcn/ui + React Query        │
└─────────────────────────┬────────────────────────────────┘
                          │ REST / WebSocket
┌─────────────────────────▼────────────────────────────────┐
│                BACKEND API (FastAPI/Python)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │   auth   │ │ projects │ │    ai    │ │  reporting  │  │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────────────┐   │
│  │ billing  │ │   jobs   │ │      notifications      │   │
│  └──────────┘ └──────────┘ └─────────────────────────┘   │
└──────┬────────────────────────────┬───────────────────────┘
       │ PostgreSQL                 │ Redis (Celery broker)
┌──────▼──────┐         ┌───────────▼──────────────────────┐
│  PostgreSQL │         │     TEST RUNNER (Python/Celery)   │
└─────────────┘         │  playwright-python + browser-use  │
                        │  (artifacts → MinIO/S3)           │
┌─────────────┐         └──────────────────────────────────┘
│    MinIO    │◄──────────────────────────────────────────
│  (S3-compat)│
└─────────────┘
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router) | SSR + client components |
| UI | Tailwind CSS + shadcn/ui | Consistent design system |
| State / Data | React Query + Zustand | Server state + local state |
| Backend API | FastAPI (Python 3.12) | Async, modular, fast |
| ORM | SQLAlchemy 2.0 + Alembic | Typed models, clean migrations |
| Database | PostgreSQL 16 | Primary data store |
| Queue / Broker | Redis + Celery | Job dispatch to workers |
| Cache | Redis | API response caching, rate limits |
| Test Runner | playwright-python | Deterministic test execution |
| AI Agent | browser-use (Python) | LLM ↔ browser glue, multi-provider |
| LLM (default) | Claude 3.7 Sonnet (Anthropic) | Best reasoning for code gen; swappable |
| LLM (alt) | Gemini 2.5 Pro / GPT-4o | Via browser-use provider abstraction |
| Storage | MinIO (dev) → AWS S3 (prod) | Videos, traces, HAR, screenshots |
| Auth | JWT + OAuth2 (GitHub, Google) | Standard SaaS auth |
| Billing | Stripe | Usage-based + seat billing |
| Notifications | SendGrid (email) + Slack webhooks | Run results delivery |
| Reverse Proxy | Nginx | Routes all services |
| Containers | Docker + Docker Compose | Dev parity, cloud-agnostic |

---

## Module Breakdown

### `auth` module
- JWT access + refresh tokens
- OAuth2 login via GitHub and Google
- Organization membership, invites
- Role: Owner / Admin / Member / Viewer

### `projects` module
- Organization → Teams → Projects → Test Suites → Tests
- API key management per project (for CI/CD triggers)
- Target URL configuration per project

### `ai` module
- **Abstracted LLM provider interface** (swap Claude ↔ Gemini ↔ GPT-4o in config)
- **Test generation pipeline:**
  1. Accept input: plain text description, video file, or screen recording
  2. If video/recording: extract frames + transcribe intent (Whisper or Gemini Vision)
  3. Use browser-use agent to explore target URL, read accessibility tree
  4. LLM generates structured test steps + Playwright assertion code
  5. Store generated test in DB with version history
- **Self-healing pipeline:**
  1. Receive broken selector + current page accessibility tree
  2. LLM identifies correct new selector
  3. Test code auto-updated in DB, run retried

### `jobs` module
- Schedule test runs: on-demand, webhook-triggered, cron
- Push jobs to Redis/Celery queue with priority
- Track job status (queued → running → completed/failed)
- WebSocket endpoint for real-time run progress updates to frontend

### `reporting` module
- Store test run results (pass/fail/flaky per test)
- Link artifacts: video URL, HAR trace URL, console log URL, screenshot URLs
- AI failure analysis: plain English summary of why a test failed
- Test history, flakiness scores, trend charts

### `billing` module
- Stripe integration: subscription plans + usage-based billing
- Plans: Free (limited runs) / Pro / Enterprise
- Metered billing: count test runs per billing period
- Webhook handler for Stripe events (payment failed, subscription cancelled)

### `notifications` module
- Slack webhook: post run summary to configured channel
- Email (SendGrid): run complete / failure alerts
- GitHub: post commit status check + PR comment with results

---

## Test Runner (Celery Workers)

### Job lifecycle
```
1. Worker picks job from Redis queue
2. Launch Playwright browser (chromium, headless)
3. Execute test steps via playwright-python
4. On selector failure → call AI module self-heal endpoint → retry
5. Record video (Playwright built-in video recording)
6. Capture: console logs, network HAR, full trace
7. Upload all artifacts to MinIO/S3
8. Post results back to Backend API (HTTP)
9. Backend stores results + fires notifications
```

### Parallelism
- Multiple Celery worker processes consume from same Redis queue
- Scale horizontally: add more worker containers
- Playwright browser contexts are isolated per job (no shared state)

### Self-healing
- Selector failure triggers synchronous call to `/internal/ai/heal`
- Returns corrected selector within ~2s
- Test retried with new selector (max 2 retries)
- If healed: test DB updated with new selector
- If not healed: run marked failed with AI explanation

---

## CI/CD Integration

### Trigger endpoint
```
POST /api/v1/runs/trigger
Authorization: Bearer <project_api_key>
Body: { "suite_id": "...", "branch": "main", "commit_sha": "abc123" }
```

### GitHub Actions (official action)
```yaml
- uses: your-org/bug0-action@v1
  with:
    api-key: ${{ secrets.BUG0_API_KEY }}
    suite-id: "suite_123"
```

### GitHub status checks
- Pending status posted when run starts
- Pass/fail status posted when run completes
- PR blocked if configured as required check

---

## Data Models (key tables)

```
organizations        id, name, slug, created_at
users                id, email, name, oauth_provider, created_at
memberships          user_id, org_id, role
projects             id, org_id, name, target_url, api_key
test_suites          id, project_id, name
tests                id, suite_id, name, code, version, created_at
test_runs            id, suite_id, trigger(api/ci/schedule), status, started_at, finished_at
test_results         id, run_id, test_id, status, video_url, trace_url, log_url, ai_summary
notifications_cfg    id, project_id, type(slack/email/github), config_json
billing_subscriptions id, org_id, stripe_customer_id, plan, status
```

---

## Folder Structure

```
/
├── frontend/
│   ├── app/                    # Next.js App Router pages
│   │   ├── (auth)/             # Login, signup
│   │   ├── dashboard/          # Main dashboard
│   │   ├── projects/[id]/      # Project detail, test suites
│   │   └── runs/[id]/          # Run detail, video, logs
│   ├── components/             # shadcn/ui + custom components
│   └── lib/                    # API client, hooks, utils
│
├── backend/
│   ├── api/                    # FastAPI route handlers
│   │   └── v1/
│   ├── modules/
│   │   ├── auth/
│   │   ├── projects/
│   │   ├── ai/                 # browser-use + LLM abstraction
│   │   ├── jobs/
│   │   ├── reporting/
│   │   ├── billing/
│   │   └── notifications/
│   ├── models/                 # SQLAlchemy models
│   ├── core/                   # Config, DB session, Redis, S3 client
│   └── main.py
│
├── runner/
│   ├── workers/                # Celery worker definitions
│   ├── executor/               # playwright-python test execution
│   ├── healer/                 # Self-healing logic (calls backend AI module)
│   └── storage/                # Artifact upload to MinIO/S3
│
├── infra/
│   ├── docker-compose.yml
│   ├── nginx/
│   │   └── nginx.conf
│   └── postgres/
│       └── init.sql
│
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-01-bug0-clone-design.md
```

---

## Build Order (Phases)

### Phase 1 — Foundation
- Docker Compose: PostgreSQL, Redis, MinIO, Nginx
- FastAPI app skeleton with health check
- SQLAlchemy models + Alembic migrations
- JWT auth + GitHub OAuth
- Next.js app with login/signup pages

### Phase 2 — Core Test Management
- Organization / project / suite / test CRUD
- API key generation per project
- Test editor (view/edit generated code)
- Basic dashboard

### Phase 3 — AI Test Generation
- browser-use integration in `ai` module
- LLM provider abstraction (Claude default)
- Natural language → test code pipeline
- Video/recording → test code pipeline
- Accessibility tree reading

### Phase 4 — Test Execution
- Celery workers + playwright-python
- Video recording, HAR, console logs
- Artifact upload to MinIO/S3
- Real-time WebSocket run progress

### Phase 5 — Self-Healing + Reporting
- Self-healing pipeline
- AI failure analysis
- Run history + video playback UI
- Flakiness tracking

### Phase 6 — CI/CD + Notifications
- Webhook trigger endpoint
- GitHub status checks
- Slack + email notifications
- GitHub Actions action

### Phase 7 — SaaS Layer
- Stripe billing integration
- Role-based access control
- Team management UI
- Usage metering

---

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Browser automation | playwright-python | Official Python client, full feature parity |
| AI ↔ browser glue | browser-use | Saves ~3 weeks of custom agent code, multi-LLM |
| LLM default | Claude 3.7 Sonnet | Best code generation reasoning |
| No Node.js | Pure Python runner | Simpler ops, one language |
| Queue | Celery + Redis | Battle-tested Python async jobs |
| Storage | MinIO → S3 | Cloud-agnostic, same API |
| Modular monolith | Not microservices | Ship fast, split only when needed |
