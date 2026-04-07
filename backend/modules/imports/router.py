"""Router for code import module."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from modules.auth.dependencies import get_current_user
from models import User
from .schemas import CodeImportRequest, CodeImportResponse
from . import service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/code", response_model=CodeImportResponse)
async def import_code(
    data: CodeImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import existing test code (any language/framework) and convert to Playwright Python.

    Accepts: Selenium (Java/Python/C#/Ruby), Cypress, Playwright JS/TS, Jest, Pytest,
             Capybara, TestCafe, plain English test cases — any format.

    If the suite has login config set and the imported code doesn't contain login steps,
    login steps are automatically prepended so the test starts authenticated.
    """
    result = await service.import_code(
        db=db,
        user_id=current_user.id,
        suite_id=data.suite_id,
        test_name=data.test_name,
        source_code=data.source_code,
        source_language=data.source_language,
    )
    return CodeImportResponse(**result)
