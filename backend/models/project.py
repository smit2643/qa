import secrets
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import UUIDMixin, TimestampMixin
from core.database import Base

class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32), index=True)
    storage_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # Playwright storageState for auth bypass

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    suites: Mapped[list["TestSuite"]] = relationship(back_populates="project", cascade="all, delete-orphan")
