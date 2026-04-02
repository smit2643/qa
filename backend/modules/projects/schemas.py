from pydantic import BaseModel, AnyHttpUrl, ConfigDict
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    target_url: AnyHttpUrl
    organization_id: str


class ProjectUpdate(BaseModel):
    name: str | None = None
    target_url: str | None = None


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    target_url: str
    api_key: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
