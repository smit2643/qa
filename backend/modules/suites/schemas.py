from pydantic import BaseModel, ConfigDict
from datetime import datetime


class SuiteCreate(BaseModel):
    name: str
    project_id: str


class SuiteUpdate(BaseModel):
    name: str | None = None


class SuiteResponse(BaseModel):
    id: str
    project_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
