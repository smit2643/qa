from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class TestSuite(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_suites"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="suites")
    tests: Mapped[list["TestCase"]] = relationship(back_populates="suite", cascade="all, delete-orphan")
    runs: Mapped[list["TestRun"]] = relationship(back_populates="suite", cascade="all, delete-orphan")
