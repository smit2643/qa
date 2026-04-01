from sqlalchemy import String, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class TestCase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"

    suite_id: Mapped[str] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    input_method: Mapped[str] = mapped_column(String(50), default="text", nullable=False)  # text | recording | video

    suite: Mapped["TestSuite"] = relationship(back_populates="tests")
    steps: Mapped[list["TestStep"]] = relationship(back_populates="test", cascade="all, delete-orphan", order_by="TestStep.order")
    results: Mapped[list["TestResult"]] = relationship(back_populates="test")
