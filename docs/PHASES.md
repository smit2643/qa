# Bug0 Clone — Phase-by-Phase Build Plan

**Approach:** Build phase by phase. Each phase ships working, testable software. User approves each phase before the next starts.

**Current status:** Phase 3 complete

---

## Demo Strategy

**Goal:** Ship a demoable product fast. Full investor/customer demo in the shortest path.

**Demo flow:**
1. Sign up → create project with your app's URL
2. Describe a test in English → browser-use Agent navigates your real app → Playwright code generated
3. OR upload a video of you using your app → Claude Vision extracts steps → code generated
4. OR record your screen in-app → steps extracted → code generated
5. Click "Run" → tests execute in parallel across browsers
6. Watch live browser execution (split-screen: AI reasoning + live browser)
7. See pass/fail + video recording + screenshot diffs
8. All through a polished Next.js UI with dark mode

**Key technical decision — browser-use Agent:**
The AI doesn't guess steps from a static page snapshot. It uses `browser_use.Agent` to actually navigate and interact with your app — recording real clicks, real inputs, real selectors. This produces dramatically more reliable tests.

**Build order for demo:**
| Phase | Status | Why |
|---|---|---|
| 1 — Foundation | ✅ Complete | |
| 2 — Project Management | ✅ Complete | |
| 3 — AI Engine (fix) | 🔨 Next | Replace static snapshot with browser-use Agent |
| 4 — Input Methods | 🔨 Next | Video upload + screen recording |
| 5 — Execution Engine | 🔨 Next | Tests must actually run |
| 8 — Frontend UI | 🔨 Next | Can't demo an API |
| 6, 7, 9, 10 | ⏸ Post-demo | Self-healing, CI/CD, billing, hardening |

---

## Phase 1 — Foundation
**Goal:** Everything boots. Auth works. Database ready.

| Task | Description |
|---|---|
| ✅ 1 | Docker Compose (postgres, redis, minio, nginx) |
| ✅ 2 | FastAPI skeleton + health endpoint |
| ✅ 3 | All SQLAlchemy models + Alembic migrations |
| ✅ 4 | JWT auth — signup, login, `/me` |

**Deliverable:** `docker compose up` → stack running. Can sign up, log in, get token. ✅ **COMPLETE**

---

## Phase 2 — Project Management Backend
**Goal:** Full CRUD for projects, suites, tests. API keys for CI.

| Task | Description |
|---|---|
| ✅ 5 | Organizations + membership model + OAuth (GitHub, Google) |
| ✅ 6 | Projects + TestSuites CRUD + API key generation |
| ✅ 7 | TestCase CRUD + version history |
| ✅ 8 | Step model (JSON steps array per test — visual builder data) |
| ✅ 9 | storageState.json upload per project (Playwright auth state) |

**Deliverable:** Full project/suite/test management via API. CI can trigger with API key. ✅ **COMPLETE**

---

## Phase 3 — AI Engine (Multi-Agent Architecture)
**Goal:** Plain English → working Playwright test code via 3 AI agents.

| Task | Description |
|---|---|
| ✅ 10 | LLM provider abstraction (Claude default, GPT-4o, Gemini swappable) |
| ✅ 11 | **Planner Agent** — maps user journey, identifies P0 paths, produces structured test plan |
| ✅ 12 | **Generator Agent** — converts plan → Playwright code with `getByRole` selectors |
| ✅ 13 | browser-use integration — visit URL, read accessibility tree |
| ✅ 14 | Hierarchical context compression (long flows don't hit LLM limits) |
| ✅ 15 | `/ai/generate` endpoint — text description → test code |

**Deliverable:** POST description → get back working Playwright test code in ~30 seconds. ✅ **COMPLETE**

---

## Phase 4 — Input Methods
**Goal:** All 3 input methods working (text ✅, screen recording, video upload).

| Task | Description |
|---|---|
| ⬜ 16 | Screen recording API — accept WebM recording from frontend, extract browser actions |
| ⬜ 17 | Video upload API — accept mp4/webm, Claude Vision analyzes frames → steps |
| ⬜ 18 | Step extraction pipeline — any input → structured JSON steps array |
| ⬜ 19 | Visual step editor API — CRUD for individual steps before code generation |
| ⬜ 20 | `/ai/generate-from-steps` — JSON steps → Playwright code |

**Deliverable:** Record your screen → upload → AI shows you extracted steps → edit them → generate code.

---

## Phase 5 — Test Execution Engine
**Goal:** Tests actually run, parallel, cross-browser, with full artifact capture.

| Task | Description |
|---|---|
| ⬜ 21 | Celery worker setup + Redis queue |
| ⬜ 22 | Playwright executor — run test code in isolated browser context |
| ⬜ 23 | Cross-browser support — Chromium, Firefox, WebKit |
| ⬜ 24 | Video recording per test run (Playwright built-in) |
| ⬜ 25 | Visual regression — before/after screenshot + pixelmatch diff |
| ⬜ 26 | Console logs + HAR network trace capture |
| ⬜ 27 | State management — test isolation (clean browser state per run) |
| ⬜ 28 | WebSocket live streaming — CDP browser stream during execution |
| ⬜ 29 | Artifact upload to MinIO/S3 |
| ⬜ 30 | Jobs API — trigger, status, result update endpoints |

**Deliverable:** Hit "Run" → tests execute in parallel across browsers → video + logs + visual diffs appear.

---

## Phase 6 — Self-Healing + Reporting + Triage
**Goal:** Tests fix themselves. Failures are explained. Coverage is visible.

| Task | Description |
|---|---|
| ⬜ 31 | **Healer Agent** — broken selector + accessibility tree → corrected selector |
| ⬜ 32 | Human-in-the-loop review — healing suggestions queue, approve/reject UI |
| ⬜ 33 | Healing history — track all healed tests, before/after selectors |
| ⬜ 34 | Failure clustering — group related failures using pgvector similarity |
| ⬜ 35 | Noise control — deduplicate failure reports across runs |
| ⬜ 36 | AI failure analysis — plain English explanation per failed test |
| ⬜ 37 | Bug report generation — auto-create structured bug report from failure |
| ⬜ 38 | Test coverage map — which user journeys are tested (data layer) |
| ⬜ 39 | Release gates — block/allow PR merge based on run result |
| ⬜ 40 | Reporting API — run history, result detail, coverage, trends |

**Deliverable:** Tests self-heal. Failures come with explanations + bug reports. Coverage is tracked.

---

## Phase 7 — CI/CD + Integrations
**Goal:** Works with every major CI platform and team tool.

| Task | Description |
|---|---|
| ⬜ 41 | GitHub integration — Actions trigger + PR status check + PR comment |
| ⬜ 42 | GitLab integration — CI pipeline trigger + MR status |
| ⬜ 43 | Jenkins + Bitbucket — webhook trigger endpoints |
| ⬜ 44 | Slack notifications — run summary, failures, healing suggestions |
| ⬜ 45 | Email notifications — SendGrid, run complete + failure alerts |
| ⬜ 46 | JIRA integration — auto-create ticket from bug report |

**Deliverable:** Every PR triggers tests. Results appear in GitHub/GitLab. Team gets Slack/email alerts.

---

## Phase 8 — Premium Frontend
**Goal:** A UI you could demo to any investor or customer. Best-in-class design.

| Task | Description |
|---|---|
| ⬜ 47 | Next.js 14 setup — App Router, Tailwind, shadcn/ui, Framer Motion, dark mode |
| ⬜ 48 | Auth pages — login, signup, OAuth buttons (GitHub, Google) |
| ⬜ 49 | Dashboard — test coverage map, recent runs, stats overview |
| ⬜ 50 | Projects page — create/list/manage projects |
| ⬜ 51 | Visual step editor — dnd-kit drag & drop, edit steps before generating |
| ⬜ 52 | Screen recording interface — MediaRecorder API, record browser tab in-app |
| ⬜ 53 | Video upload UI — drag & drop upload, progress, frame preview |
| ⬜ 54 | Test generation UI — all 3 input methods + storageState.json upload |
| ⬜ 55 | Split-screen live execution — AI reasoning panel (left) + live browser (right) |
| ⬜ 56 | Run detail page — video player, visual diff viewer, AI summary, logs, healing queue |
| ⬜ 57 | Healing review UI — approve/reject healing suggestions |
| ⬜ 58 | Settings pages — project settings, API keys, notification config |

**Deliverable:** Full polished UI. Every feature accessible. Dark mode. Smooth animations.

---

## Phase 9 — SaaS Layer
**Goal:** People can sign up and pay for it.

| Task | Description |
|---|---|
| ⬜ 59 | Stripe billing — Studio ($250/mo) + Managed ($2,500/mo) |
| ⬜ 60 | Usage metering — count test minutes per org per billing period |
| ⬜ 61 | Plan enforcement — free plan limits, upgrade prompts |
| ⬜ 62 | Organization management — create org, rename, delete |
| ⬜ 63 | Team invites — invite by email, accept invite flow |
| ⬜ 64 | RBAC — Owner / Admin / Member / Viewer permissions enforced everywhere |
| ⬜ 65 | API key management UI — create, rotate, revoke keys |

**Deliverable:** Full multi-tenant SaaS. Sign up → choose plan → pay → use the product.

---

## Phase 10 — Production Hardening
**Goal:** Deploy-ready, observable, secure, enterprise-grade.

| Task | Description |
|---|---|
| ⬜ 66 | Rate limiting — per API key + per user (slowapi) |
| ⬜ 67 | Audit logs — every user action logged to audit_logs table |
| ⬜ 68 | Sentry integration — error tracking backend + frontend |
| ⬜ 69 | Prometheus metrics + Grafana dashboard |
| ⬜ 70 | Structured logging (loguru) — JSON logs, request IDs |
| ⬜ 71 | Security hardening — CORS, CSP headers, secrets scan |
| ⬜ 72 | Performance — DB query optimization, Redis caching, N+1 fixes |
| ⬜ 73 | SOC 2 readiness checklist — encryption at rest, access control audit |
| ⬜ 74 | Final docs update — all MD files reflect production state |
| ⬜ 75 | Production deploy guide — cloud VPS + domain + TLS |

**Deliverable:** Deployable to any cloud. Observable. Secure. Enterprise-ready.

---

## Summary

| Phase | Tasks | Key Deliverable |
|---|---|---|
| 1 — Foundation | 4 | Stack boots, auth works |
| 2 — Project Management | 5 | Projects/suites/tests CRUD |
| 3 — AI Engine | 6 | Text → Playwright code (multi-agent) |
| 4 — Input Methods | 5 | Screen recording + video → code |
| 5 — Execution Engine | 10 | Parallel runs, video, visual regression |
| 6 — Healing + Reporting | 10 | Self-heal, triage, coverage, release gates |
| 7 — CI/CD + Integrations | 6 | GitHub, GitLab, Slack, JIRA |
| 8 — Premium Frontend | 12 | Full polished UI |
| 9 — SaaS Layer | 7 | Billing, teams, RBAC |
| 10 — Production Hardening | 10 | Deploy-ready, observable, secure |
| **Total** | **75 tasks** | **Production SaaS product** |

---

## What Was Missing From Original Plan

| Feature | Added In |
|---|---|
| Screen recording (in-app) | Phase 4 |
| Video upload + Claude Vision | Phase 4 |
| Visual step builder (drag & drop) | Phase 4 + 8 |
| storageState.json auth bypass | Phase 2 |
| Multi-agent (Planner + Generator + Healer) | Phase 3 |
| Hierarchical context compression | Phase 3 |
| Human-in-the-loop healing review | Phase 6 |
| Cross-browser (Firefox, WebKit) | Phase 5 |
| Visual regression testing (pixelmatch) | Phase 5 |
| State management (test isolation) | Phase 5 |
| Live browser streaming (WebSocket + CDP) | Phase 5 |
| Failure clustering (pgvector) | Phase 6 |
| Noise control / deduplication | Phase 6 |
| Bug report generation | Phase 6 |
| Test coverage map | Phase 6 |
| Release gates | Phase 6 |
| GitLab + Jenkins + Bitbucket | Phase 7 |
| JIRA integration | Phase 7 |
| Split-screen live execution UI | Phase 8 |
| Visual diff viewer | Phase 8 |
| Healing review UI | Phase 8 |
| Usage metering | Phase 9 |
| Plan enforcement (limits) | Phase 9 |
| RBAC enforced everywhere | Phase 9 |
| Audit logs | Phase 10 |
| Prometheus + Grafana | Phase 10 |
| SOC 2 readiness | Phase 10 |
