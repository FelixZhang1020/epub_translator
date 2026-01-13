"""Paragraph database model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base
from app.models.database.enums import ContentType

if TYPE_CHECKING:
    from app.models.database.chapter import Chapter
    from app.models.database.translation import Translation
    from app.models.database.paragraph_match import ParagraphMatch
    from app.models.database.proofreading import ProofreadingSuggestion


class Paragraph(Base):
    """Individual paragraph - the atomic unit for translation."""

    __tablename__ = "paragraphs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    chapter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )

    # Paragraph info
    paragraph_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    html_tag: Mapped[str] = mapped_column(String(50), default="p")

    # For optimization mode - existing translation
    existing_translation: Mapped[Optional[str]] = mapped_column(Text)

    # Word/token count for chunking
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    # V2 parser fields for reconstruction
    xpath: Mapped[Optional[str]] = mapped_column(Text)  # XPath for locating in document
    original_html: Mapped[Optional[str]] = mapped_column(Text)  # Raw HTML with tags
    has_formatting: Mapped[bool] = mapped_column(Boolean, default=False)  # Has inline formatting

    # Content classification (for proofreading filtering)
    content_type: Mapped[str] = mapped_column(
        String(20), default=ContentType.MAIN.value
    )
    is_proofreadable: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="paragraphs")
    translations: Mapped[list["Translation"]] = relationship(
        "Translation", back_populates="paragraph", cascade="all, delete-orphan"
    )
    reference_match: Mapped[Optional["ParagraphMatch"]] = relationship(
        "ParagraphMatch", back_populates="source_paragraph", uselist=False,
        cascade="all, delete-orphan"
    )
    proofreading_suggestions: Mapped[list["ProofreadingSuggestion"]] = relationship(
        "ProofreadingSuggestion", back_populates="paragraph", cascade="all, delete-orphan"
    )

    @property
    def latest_translation(self) -> Optional["Translation"]:
        """Get the latest translation for this paragraph."""
        if not self.translations:
            return None
        return max(self.translations, key=lambda t: t.created_at)
