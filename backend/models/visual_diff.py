from sqlalchemy import String, ForeignKey, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class VisualDiff(UUIDMixin, TimestampMixin, Base):
    """Screenshot comparison result for visual regression testing."""
    __tablename__ = "visual_diffs"

    result_id: Mapped[str] = mapped_column(ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    diff_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    diff_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 = identical, 1.0 = completely different
    diff_pixel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(default=True, nullable=False)

    result: Mapped["TestResult"] = relationship(back_populates="visual_diffs")
