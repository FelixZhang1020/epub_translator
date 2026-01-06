"""Chapter database model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project
    from app.models.database.paragraph import Paragraph


class Chapter(Base):
    """Chapter within an EPUB project."""

    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Chapter info
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    html_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Content stats
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0)

    # Raw HTML content (for regeneration)
    original_html: Mapped[Optional[str]] = mapped_column(Text)

    # Images in this chapter (list of image metadata dicts)
    images: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="chapters")
    paragraphs: Mapped[list["Paragraph"]] = relationship(
        "Paragraph", back_populates="chapter", cascade="all, delete-orphan"
    )
