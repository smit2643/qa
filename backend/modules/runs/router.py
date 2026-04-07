"""Runs router — Task 30: Jobs API + Task 28: WebSocket live streaming."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.database import get_db
from modules.auth.dependencies import get_current_user
from models import User
from . import service as runs_service
from .schemas import RunCreate, RunResponse, ResultResponse, ResultUpdate, RunFinish

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])


# ---------------------------------------------------------------------------
# Jobs API (Task 30)
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=RunResponse)
def create_run(
    body: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a new test run. Dispatches Celery tasks immediately."""
    return runs_service.create_run(db, current_user.id, body)


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return runs_service.get_run(db, current_user.id, run_id)


@router.get("/suites/{suite_id}/runs", response_model=list[RunResponse])
def list_suite_runs(
    suite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return runs_service.list_suite_runs(db, current_user.id, suite_id)


@router.patch("/runs/{run_id}/results/{result_id}", response_model=ResultResponse)
def update_result(
    run_id: str,
    result_id: str,
    body: ResultUpdate,
    db: Session = Depends(get_db),
):
    """
    Internal callback endpoint — called by Celery worker to report result.
    No auth required (internal network only; add API-key auth in Phase 10 hardening).
    """
    return runs_service.update_result(db, run_id, result_id, body)


@router.patch("/runs/{run_id}/finish")
def finish_run(
    run_id: str,
    body: RunFinish,
    db: Session = Depends(get_db),
):
    """Internal callback — called by worker when all tasks for this run are done."""
    return runs_service.finish_run(db, run_id, body.status)


# ---------------------------------------------------------------------------
# WebSocket live streaming (Task 28)
# ---------------------------------------------------------------------------

@router.websocket("/ws/runs/{run_id}/stream")
async def stream_run_logs(websocket: WebSocket, run_id: str):
    """
    Stream live log events for a run via WebSocket.

    The Celery worker publishes JSON events to Redis pub/sub channel
    `run:{run_id}:logs`. This endpoint subscribes and forwards them
    to the connected WebSocket client.

    Event types:
      {"event": "started",  "result_id": "...", "test_name": "..."}
      {"event": "log",      "result_id": "...", "line": "..."}
      {"event": "finished", "result_id": "...", "status": "passed|failed"}
      {"event": "error",    "result_id": "...", "message": "..."}
    """
    await websocket.accept()

    try:
        import redis.asyncio as aioredis
        from core.config import settings

        r = await aioredis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"run:{run_id}:logs")

        idle_seconds = 0
        max_idle = 300  # close after 5 min of no messages

        try:
            while idle_seconds < max_idle:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=2.0,
                    )
                    if message and message["type"] == "message":
                        await websocket.send_text(message["data"].decode())
                        idle_seconds = 0
                        # Stop streaming only on run-level completion events
                        # ("finished" is per-result — do NOT break on it)
                        try:
                            data = json.loads(message["data"].decode())
                            if data.get("event") in ("run_passed", "run_failed"):
                                break
                        except Exception:
                            pass
                    else:
                        idle_seconds += 2
                except asyncio.TimeoutError:
                    idle_seconds += 2
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe()
            await r.aclose()

    except ImportError:
        await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket stream error for run %s: %s", run_id, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
