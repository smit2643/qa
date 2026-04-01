import enum
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    cancelled = "cancelled"

class TriggerType(str, enum.Enum):
    manual = "manual"
    api = "api"
    schedule = "schedule"
    github = "github"
    gitlab = "gitlab"

class TestRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_runs"

    suite_id: Mapped[str] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued, nullable=False, index=True)
    trigger: Mapped[TriggerType] = mapped_column(Enum(TriggerType), default=TriggerType.manual, nullable=False)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    browser: Mapped[str] = mapped_column(String(50), default="chromium", nullable=False)  # chromium | firefox | webkit
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    suite: Mapped["TestSuite"] = relationship(back_populates="runs")
    results: Mapped[list["TestResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
