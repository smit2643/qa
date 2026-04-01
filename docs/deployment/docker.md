# Docker Deployment

---

## Development

Start everything with Docker Compose:

```bash
cp .env.example .env
# Fill in .env

cd infra
docker compose up --build -d

# Run migrations
docker compose exec backend alembic upgrade head

# Check all services
docker compose ps
```

Services:
| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API via Nginx | http://localhost/api |
| MinIO Console | http://localhost:9001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Scaling Workers

To run more parallel test workers:

```bash
# In docker-compose.yml, add replicas:
runner:
  deploy:
    replicas: 4
```

Or run ad-hoc:
```bash
docker compose up --scale runner=4 -d
```

---

## Production Checklist

- [ ] All `.env` secrets replaced with production values
- [ ] `SECRET_KEY` is unique and 32+ chars
- [ ] MinIO replaced with AWS S3 (update `MINIO_ENDPOINT` + credentials)
- [ ] PostgreSQL uses managed DB (RDS, Supabase, Neon, etc.)
- [ ] Redis uses managed Redis (ElastiCache, Upstash, etc.)
- [ ] Nginx configured with TLS (Let's Encrypt via Certbot)
- [ ] Frontend `NEXT_PUBLIC_API_URL` set to production API URL
- [ ] Docker images tagged with version (not `latest`)
- [ ] Health checks configured in `docker-compose.yml`
- [ ] Log aggregation set up (CloudWatch, Datadog, etc.)

---

## Adding TLS (Nginx + Certbot)

```nginx
# infra/nginx/nginx.conf — add to server block:
listen 443 ssl;
ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

```bash
# Issue cert
docker run -it --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d yourdomain.com
```

---

## Cloud Deployment (Docker + VPS)

Any VPS (Hetzner, DigitalOcean, Vultr):

```bash
# On the server:
git clone <repo> && cd repo
cp .env.example .env && nano .env
cd infra && docker compose -f docker-compose.yml up -d
```

Minimum recommended specs: **4 vCPU, 8GB RAM** (Playwright is memory-intensive per worker).
