from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class TestSuite(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_suites"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Suite-level login config — stored once, used for every test run in this suite
    login_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    login_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    login_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cached Playwright storage state (cookies/localStorage) from last successful login
    storage_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="suites")
    tests: Mapped[list["TestCase"]] = relationship(back_populates="suite", cascade="all, delete-orphan")
    runs: Mapped[list["TestRun"]] = relationship(back_populates="suite", cascade="all, delete-orphan")
