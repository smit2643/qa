from pydantic import BaseModel, ConfigDict
from datetime import datetime


class SuiteCreate(BaseModel):
    name: str
    project_id: str


class SuiteUpdate(BaseModel):
    name: str | None = None


class SuiteLoginConfig(BaseModel):
    login_url: str
    login_email: str
    login_password: str


class SuiteResponse(BaseModel):
    id: str
    project_id: str
    name: str
    login_url: str | None = None
    login_email: str | None = None
    has_auth_state: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_auth(cls, suite) -> "SuiteResponse":
        return cls(
            id=suite.id,
            project_id=suite.project_id,
            name=suite.name,
            login_url=suite.login_url,
            login_email=suite.login_email,
            has_auth_state=bool(suite.storage_state_json),
            created_at=suite.created_at,
            updated_at=suite.updated_at,
        )
