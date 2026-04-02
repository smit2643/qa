from sqlalchemy import String, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class TestStep(UUIDMixin, TimestampMixin, Base):
    """Individual step in a test — populated by visual step editor and AI extraction."""
    __tablename__ = "test_steps"

    test_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)   # click | type | navigate | assert | wait
    selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)    # text to type, URL to navigate, etc.
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_assertion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    test: Mapped["TestCase"] = relationship(back_populates="steps")
