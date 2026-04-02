from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from models.test_case import InputMethod


class TestCaseCreate(BaseModel):
    name: str
    suite_id: str
    description: str = ""
    input_method: InputMethod = InputMethod.text

    @field_validator("name")
    @classmethod
    def name_max_length(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("name must be at most 200 characters")
        return v


class TestCaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    code: str | None = None


class TestCaseResponse(BaseModel):
    id: str
    suite_id: str
    name: str
    description: str
    code: str
    version: int
    input_method: InputMethod
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
