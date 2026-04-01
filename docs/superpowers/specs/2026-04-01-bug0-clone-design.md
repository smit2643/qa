# Bug0.com Clone — Full System Design Spec
**Date:** 2026-04-01
**Status:** Approved — Full Feature Parity

---

## Overview

A production-grade SaaS clone of bug0.com — a full AI-powered E2E testing platform. Complete feature parity: natural language + screen recording + video upload → AI test generation → parallel execution → self-healing → visual regression → reporting → CI/CD integrations → Stripe billing.

---

## What We're Building (Complete Feature List)

### Test Creation (3 input methods)
- **Plain English** → AI generates Playwright test code
- **In-app Screen Recording** → Record browser tab live → AI extracts steps → generates code
- **Video Upload** (mp4/webm) → Claude Vision analyzes frames → extracts steps → generates code
- **Visual Step Builder** → Edit/add/remove extracted steps before code generation (drag & drop)
- **storageState.json** → Paste Playwright auth state to test authenticated flows without re-logging

### AI Engine (Multi-Agent Architecture)
- **Planner Agent** → Maps critical user journeys, identifies P0 paths, creates test plan
- **Generator Agent** → Converts test plan → Playwright code with resilient selectors
- **Healer Agent** → Detects broken tests, generates fix suggestions, human reviews before apply
- **Hierarchical Context Compression** → Handles long test flows without hitting LLM context limits
- **LLM Provider Abstraction** → Claude (default), GPT-4o, Gemini — swappable via config

### Test Execution
- **Parallel Execution** → 500+ tests simultaneously via Celery workers
- **Cross-Browser** → Chromium, Firefox, WebKit (Playwright native)
- **Video Recording** → Per test run, .webm, inline playback
- **Visual Regression** → Screenshot comparison with pixelmatch diffing
- **State Management** → Snapshot/restore for isolated test environments
- **Live Execution Streaming** → WebSocket stream of browser via CDP (split-screen UI)
- **Console Logs + HAR Traces** → Full network + console capture per run

### Self-Healing
- **Automatic Selector Healing** → 90% of UI changes healed without intervention
- **Human-in-the-Loop** → Healing suggestions queued for review before applying
- **Healing History** → Track all healed tests, before/after selectors

### Reporting & Triage
- **Run History** → Full pass/fail/flaky history per suite
- **AI Failure Analysis** → Plain English explanation per failed test
- **Failure Triage** → Clusters related failures, eliminates duplicate reports
- **Bug Report Generation** → Auto-create actionable bug reports from failures
- **Test Coverage Map** → Visual map of which user journeys are covered
- **Release Gates** → Block PR merges based on test results

### CI/CD Integrations
- **GitHub Actions** → Official action + PR status checks + release gates
- **GitLab CI** → Native integration + MR status
- **Jenkins** → Webhook trigger
- **Bitbucket** → Pipeline integration
- **REST API** → Trigger runs from any CI via API key

### Notifications
- **Slack** → Run summary, failure alerts, healing suggestions
- **Email** → SendGrid — run complete, failure, billing
- **GitHub/GitLab** → PR comments with test summary

### SaaS
- **Multi-tenant** → Organizations → Teams → Projects → Suites → Tests
- **RBAC** → Owner / Admin / Member / Viewer
- **API Keys** → Per project, for CI/CD
- **Stripe Billing** → Studio ($250/mo) + Managed ($2,500/mo) tiers
- **Usage Metering** → Count test minutes per billing period
- **OAuth** → GitHub + Google login

### Enterprise
- **Audit Logs** → All user actions logged
- **Rate Limiting** → Per API key + per user
- **SOC 2 Type 1 Readiness** → Logging, access control, encryption at rest
- **Structured Logging** → loguru + Sentry error tracking

---

## Architecture

### Services

```
┌──────────────────────────────────────────────────────────────┐
│                  FRONTEND (Next.js 14)                       │
│   Tailwind + shadcn/ui + Framer Motion + dnd-kit             │
│   Split-screen live exec | Visual step editor | Dark mode    │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                  BACKEND API (FastAPI/Python)                 │
│                                                              │
│  auth  │  projects  │  ai  │  jobs  │  reporting            │
│  healing  │  billing  │  notifications  │  audit            │
└──────┬────────────────────────────┬────────────────────────┘
       │ PostgreSQL                 │ Redis (Celery broker)
┌──────▼──────┐         ┌───────────▼──────────────────────────┐
│  PostgreSQL │         │     TEST RUNNER (Python/Celery)       │
│  + pgvector │         │  playwright-python + browser-use      │
│  (for AI    │         │  Cross-browser | Video | Visual diff  │
│   memory)   │         │  WebSocket CDP stream                 │
└─────────────┘         └──────────────────────────────────────┘
┌─────────────┐
│    MinIO    │  ← videos, screenshots, traces, visual diffs
│  (S3-compat)│
└─────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 14 (App Router) | SSR + streaming |
| UI System | Tailwind CSS + shadcn/ui | Best component library |
| Animations | Framer Motion | Premium feel |
| Drag & Drop | dnd-kit | Visual step editor |
| Charts | Recharts | Test coverage maps, trend charts |
| State | Zustand + React Query | Local + server state |
| Backend | FastAPI (Python 3.12) | Best Python AI ecosystem |
| ORM | SQLAlchemy 2.0 + Alembic | Type-safe, clean migrations |
| Database | PostgreSQL 16 + pgvector | Relational + AI vector similarity |
| Queue | Redis + Celery | Parallel job execution |
| Browser | playwright-python | Cross-browser, video, traces |
| AI Agent | browser-use (Python) | LLM↔browser glue |
| AI Default | Claude Sonnet 4.6 | Best reasoning + vision |
| AI Vision | Claude Vision / GPT-4o | Video frame analysis |
| Visual Diff | pixelmatch | Pixel-level screenshot comparison |
| Storage | MinIO → AWS S3 | Videos, screenshots, artifacts |
| Auth | JWT + OAuth2 (GitHub, Google) | Standard SaaS |
| Billing | Stripe | Usage + seat billing |
| Logging | loguru + Sentry | Structured + error tracking |
| Metrics | Prometheus + Grafana | Production observability |
| Email | SendGrid | Transactional email |
| Infra | Docker + Docker Compose | Cloud-agnostic |
| Proxy | Nginx 1.27 | Routing + WebSocket |

---

## Database Schema

```
organizations ──< memberships >── users
      │                               │
      └──< projects >──< suites >──< tests >──< steps (JSON)
                │
                └──< runs >──< results >──< visual_diffs
                                │
                                └──< healing_suggestions

audit_logs  billing_subscriptions  notifications_config
```

Key additions vs original plan:
- `steps` table — JSON step array per test (from visual step builder)
- `visual_diffs` — screenshot comparison results per result
- `healing_suggestions` — queued healing proposals awaiting human review
- `pgvector` — for AI similarity search (cluster related failures)

---

## Phase Plan

### Phase 1 — Foundation
Docker, FastAPI, models, JWT auth

### Phase 2 — Project Management Backend
Orgs, projects, suites, tests CRUD, API keys, OAuth

### Phase 3 — AI Engine (Multi-Agent)
Planner + Generator + Healer agents, LLM abstraction, browser-use, text→test

### Phase 4 — Input Methods
Screen recording capture, video upload + Vision analysis, visual step builder API

### Phase 5 — Test Execution Engine
Celery workers, cross-browser, video, visual regression, state management, WebSocket streaming, Jobs API

### Phase 6 — Self-Healing + Reporting + Triage
Healer with human review, failure clustering, AI analysis, bug report gen, coverage map, release gates

### Phase 7 — CI/CD + Integrations
GitHub, GitLab, Jenkins, Bitbucket, Slack, email, JIRA

### Phase 8 — Premium Frontend
Full Next.js UI — split-screen execution, visual step editor, screen recording, video upload, dark mode

### Phase 9 — SaaS Layer
Stripe billing, org management, RBAC, usage metering, team invites

### Phase 10 — Production Hardening
Rate limiting, audit logs, Sentry, Prometheus, SOC 2 readiness, performance
