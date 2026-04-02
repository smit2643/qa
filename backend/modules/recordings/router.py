"""Recordings router — accepts WebM screen recording uploads."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from models import User
from modules.auth.dependencies import get_current_user
from modules.recordings import service
from modules.recordings.schemas import RecordingUploadResponse

router = APIRouter(tags=["recordings"])

_ALLOWED_CONTENT_TYPES = {"video/webm", "video/mp4", "application/octet-stream"}


@router.post("/recordings/upload", response_model=RecordingUploadResponse)
async def upload_recording(
    file: UploadFile = File(...),
    suite_id: str = Form(...),
    test_name: str = Form("Screen Recording"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a WebM screen recording, extract steps via Claude Vision, and save as a TestCase."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="File must be a WebM or MP4 video",
        )

    video_bytes = await file.read()
    result = await service.process_recording(
        db=db,
        user_id=current_user.id,
        suite_id=suite_id,
        test_name=test_name,
        video_bytes=video_bytes,
        filename=file.filename or "recording.webm",
    )
    return result
