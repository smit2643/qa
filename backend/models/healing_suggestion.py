import enum
from sqlalchemy import String, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class HealingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    applied = "applied"

class HealingSuggestion(UUIDMixin, TimestampMixin, Base):
    """AI-suggested fix for a broken test selector — requires human approval."""
    __tablename__ = "healing_suggestions"

    result_id: Mapped[str] = mapped_column(ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    broken_selector: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_selector: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[HealingStatus] = mapped_column(Enum(HealingStatus), default=HealingStatus.pending, nullable=False, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    result: Mapped["TestResult"] = relationship(back_populates="healing_suggestions")
