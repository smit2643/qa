# Environment Variables

Copy `.env.example` to `.env` and fill in all values before starting services.

---

## Required for all environments

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://bug0:pass@localhost:5434/bug0db` | PostgreSQL connection string |
| `REDIS_URL` | `redis://:bug0redis@localhost:6380/0` | Redis connection string (port 6380 on host — avoids conflict with other apps on 6379) |
| `SECRET_KEY` | `<32+ random chars>` | JWT signing key — never reuse across envs |
| `FRONTEND_URL` | `http://localhost:3000` | Used for CORS and redirect URLs |

---

## AI Provider

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `claude` | Which LLM to use: `claude` \| `openai` \| `gemini` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=claude` — get from console.anthropic.com |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` — get from platform.openai.com |
| `GOOGLE_API_KEY` | — | Required when `LLM_PROVIDER=gemini` — get from aistudio.google.com |

---

## Storage (MinIO / S3)

| Variable | Dev Default | Description |
|---|---|---|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO host:port (or S3 endpoint for prod) |
| `MINIO_ACCESS_KEY` | `bug0minio` | Access key |
| `MINIO_SECRET_KEY` | `bug0miniopass` | Secret key |
| `MINIO_BUCKET` | `bug0-artifacts` | Bucket for videos, logs, traces |

For production AWS S3:
```bash
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=AKIA...
MINIO_SECRET_KEY=...
MINIO_BUCKET=your-bucket-name
```

---

## OAuth2 (optional)

| Variable | Description |
|---|---|
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

---

## Notifications (optional)

| Variable | Description |
|---|---|
| `SENDGRID_API_KEY` | SendGrid API key for email notifications |

---

## Billing (optional)

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe secret key (`sk_test_...` for dev) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |

---

## Runner-specific

| Variable | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8080` | Backend API base URL (used by runner to POST results) |

---

## Token Config

| Variable | Default | Description |
|---|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime in minutes (default = 24h) |

---

## Security Checklist for Production

- [ ] `SECRET_KEY` is 32+ random chars, unique per environment
- [ ] `STRIPE_SECRET_KEY` uses `sk_live_...` not `sk_test_...`
- [ ] `DATABASE_URL` uses a dedicated DB user with minimal permissions
- [ ] `MINIO_*` credentials are rotated from dev defaults
- [ ] All secrets are in a secret manager (AWS Secrets Manager, Vault, etc.) — not hardcoded
