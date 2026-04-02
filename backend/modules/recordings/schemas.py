from pydantic import BaseModel
from modules.steps.schemas import StepResponse


class RecordingUploadResponse(BaseModel):
    test_id: str
    suite_id: str
    test_name: str
    steps: list[StepResponse]
    message: str
