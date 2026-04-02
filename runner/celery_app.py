"""Celery application factory — Task 21: Celery worker setup + Redis queue."""

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://:bug0redis@localhost:6379/0")

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
