"""Videos router — POST /videos/upload."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from modules.auth.dependencies import get_current_user
from models import User
from . import service as video_service
from .schemas import VideoUploadResponse

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/octet-stream",  # some browsers send this for video files
}


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    suite_id: str = Form(...),
    test_name: str = Form("Video Upload Test"),
    sample_interval: float = Form(2.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a video file (mp4 or webm) of a user flow.
    Claude Vision analyzes frames and extracts test steps.
    Returns extracted steps for review before code generation.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {file.content_type}. Use mp4 or webm.",
        )

    # Clamp interval to a sane range
    sample_interval = max(1.0, min(sample_interval, 10.0))

    video_bytes = await file.read()

    if len(video_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    result = await video_service.process_video(
        db=db,
        user_id=current_user.id,
        suite_id=suite_id,
        test_name=test_name,
        video_bytes=video_bytes,
        filename=file.filename or "upload",
        sample_interval=sample_interval,
    )
    return result
