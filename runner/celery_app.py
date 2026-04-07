"""Celery application factory — Task 21: Celery worker setup + Redis queue."""

import sys
import os
from pathlib import Path
from celery import Celery

# Load .env from project root so REDIS_URL and other vars are available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # dotenv not installed — rely on shell env vars

# Add backend to path so runner workers can import backend modules if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

REDIS_URL = os.getenv("REDIS_URL", "redis://:bug0redis@localhost:6380/0")

celery_app = Celery(
    "bug0_runner",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["runner.workers.test_runner"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,         # Only ack after task completes (safer)
    worker_prefetch_multiplier=1,  # One task at a time per worker
)
