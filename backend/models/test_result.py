import enum
from sqlalchemy import String, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class ResultStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    flaky = "flaky"

class TestResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_results"

    run_id: Mapped[str] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[ResultStatus] = mapped_column(Enum(ResultStatus), default=ResultStatus.pending, nullable=False, index=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trace_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    log_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser: Mapped[str] = mapped_column(String(50), default="chromium", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    run: Mapped["TestRun"] = relationship(back_populates="results")
    test: Mapped["TestCase"] = relationship(back_populates="results")
    visual_diffs: Mapped[list["VisualDiff"]] = relationship(back_populates="result", cascade="all, delete-orphan")
    healing_suggestions: Mapped[list["HealingSuggestion"]] = relationship(back_populates="result", cascade="all, delete-orphan")
