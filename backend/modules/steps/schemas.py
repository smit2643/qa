import enum
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StepAction(str, enum.Enum):
    click = "click"
    type = "type"
    navigate = "navigate"
    assert_ = "assert"
    wait = "wait"


class StepCreate(BaseModel):
    test_id: str
    order: int
    action: StepAction
    selector: str | None = None
    value: str | None = None
    description: str = ""
    is_assertion: bool = False


class StepUpdate(BaseModel):
    order: int | None = None
    action: StepAction | None = None
    selector: str | None = None
    value: str | None = None
    description: str | None = None
    is_assertion: bool | None = None


class BulkStepItem(BaseModel):
    """One step entry in a bulk-replace request (no test_id — inferred from URL)."""
    action: StepAction
    selector: str | None = None
    value: str | None = None
    description: str = ""
    is_assertion: bool = False


class StepInsert(BaseModel):
    """Insert a new step at `at_order`, shifting existing steps down."""
    at_order: int
    action: StepAction
    selector: str | None = None
    value: str | None = None
    description: str = ""
    is_assertion: bool = False


class StepResponse(BaseModel):
    id: str
    test_id: str
    order: int
    action: str
    selector: str | None
    value: str | None
    description: str
    is_assertion: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
