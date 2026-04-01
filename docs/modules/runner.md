# Test Runner

Location: `runner/`

Separate Python service — Celery workers that execute Playwright tests, capture artifacts, and report results back to the backend API.

---

## Files

| File | Responsibility |
|---|---|
| `celery_app.py` | Celery app factory + Redis broker config |
| `workers/test_runner.py` | Celery task definition (`run_test_task`) |
| `executor/playwright_executor.py` | Executes test code in isolated browser context |
| `executor/recorder.py` | Finds recorded video file after context close |
| `healer/selector_healer.py` | Calls backend `/ai/heal` on selector failure |
| `storage/artifact_uploader.py` | Uploads video/logs/traces to MinIO/S3 |

---

## Job Lifecycle

```
1. Backend pushes job to Redis (Celery queue)
2. Worker picks up job (one per worker process)
3. Temporary directory created for artifacts
4. Playwright chromium launched (headless, with video recording)
5. test_cases.code executed as `async def run_test(page)`
6. Console logs captured via page.on("console", ...)
7. On selector error → call /ai/heal → retry (max 2)
8. Context closed → video file finalized
9. Video + logs uploaded to MinIO
10. PATCH /runs/{run_id}/results/{result_id} with results
11. Temp directory cleaned up
```

---

## Parallelism

Workers consume from the same Redis queue. To scale:

```bash
# Start 8 parallel workers
celery -A celery_app worker --concurrency=8

# Or run multiple worker containers in Docker Compose
# Each container runs: celery -A celery_app worker --concurrency=4
```

Each worker runs one Playwright browser context at a time (`worker_prefetch_multiplier=1`).

---

## Self-Healing

When `playwright_executor.py` catches an error containing a selector:

1. Extracts the failed selector from the error message
2. Gets current page accessibility tree snapshot
3. Calls `healer/selector_healer.py` → POST to backend `/api/v1/ai/heal`
4. Backend runs Claude with broken selector + tree
5. Returns corrected selector
6. Executor retries the failing step (max 2 attempts)

If healing succeeds → backend updates the test code in DB automatically.
If healing fails → test marked failed with AI-generated error summary.

---

## Video Recording

Playwright built-in video recording is used:

```python
context = await browser.new_context(record_video_dir=tmpdir)
# ... run test ...
await context.close()  # video file written here
```

Video format: `.webm` (Chromium default).
Uploaded to MinIO at: `runs/{run_id}/{result_id}/video.webm`

---

## Artifact Storage Layout (MinIO/S3)

```
bug0-artifacts/
└── runs/
    └── {run_id}/
        └── {result_id}/
            ├── video.webm
            ├── console.log
            └── trace.zip      (future: Playwright trace)
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `REDIS_URL` | Celery broker + backend URL |
| `MINIO_ENDPOINT` | MinIO host:port (e.g. `minio:9000`) |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |
| `MINIO_BUCKET` | Bucket name (default: `bug0-artifacts`) |
| `BACKEND_URL` | Backend API URL (e.g. `http://backend:8000`) |

---

## Running Locally (without Docker)

```bash
cd runner
pip install -e ".[dev]"
playwright install chromium
celery -A celery_app worker --loglevel=info --concurrency=2
```
