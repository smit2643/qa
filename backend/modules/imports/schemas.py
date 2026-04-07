"""Schemas for code import module."""

from pydantic import BaseModel


class CodeImportRequest(BaseModel):
    suite_id: str
    test_name: str
    source_code: str          # raw test code in any language/format
    source_language: str = "auto"  # hint: "cypress", "selenium", "pytest", "jest", "auto"


class CodeImportResponse(BaseModel):
    test_id: str
    suite_id: str
    test_name: str
    source_language: str      # detected language
    steps: list[dict]
    code: str                 # generated Playwright Python
    version: int
    message: str
