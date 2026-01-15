"""ReferenceEPUB database model for storing Chinese reference EPUB data."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project


class ReferenceEPUB(Base):
    """Chinese reference EPUB file for translation comparison."""

    __tablename__ = "reference_epubs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="zh")

    # Matching status
    auto_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    match_quality: Mapped[Optional[float]] = mapped_column(Float)  # 0-1 score

    # EPUB metadata
    epub_title: Mapped[Optional[str]] = mapped_column(String(500))
    epub_author: Mapped[Optional[str]] = mapped_column(String(255))
    total_chapters: Mapped[int] = mapped_column(default=0)
    total_paragraphs: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="reference_epub")

