"""ParagraphMatch database model for EN-CN paragraph matching."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project
    from app.models.database.paragraph import Paragraph


class ParagraphMatch(Base):
    """Match between source English paragraph and reference Chinese text."""

    __tablename__ = "paragraph_matches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_paragraph_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("paragraphs.id", ondelete="CASCADE"), nullable=False
    )

    # Reference text from Chinese EPUB
    reference_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Reference location info
    reference_chapter_index: Mapped[int] = mapped_column(default=0)
    reference_paragraph_index: Mapped[int] = mapped_column(default=0)

    # Match metadata
    match_type: Mapped[str] = mapped_column(String(20), default="auto")  # auto or manual
    confidence: Mapped[Optional[float]] = mapped_column(Float)  # 0-1 for auto matches

    # User verification
    user_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    user_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="paragraph_matches")
    source_paragraph: Mapped["Paragraph"] = relationship(
        "Paragraph", back_populates="reference_match"
    )

