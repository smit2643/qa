from pydantic import BaseModel
from datetime import datetime


class StepSchema(BaseModel):
    order: int
    action: str
    selector: str | None = None
    value: str | None = None
    description: str = ""


class VideoUploadResponse(BaseModel):
    test_id: str
    suite_id: str
    test_name: str
    steps: list[StepSchema]
    frame_count: int
    message: str
