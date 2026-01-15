"""Proofreading database models for review sessions and suggestions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base
from app.models.database.enums import ProofreadingStatus, SuggestionStatus, ImprovementLevel
from app.models.database.mixins import ProgressTrackingMixin

# Re-export for backwards compatibility
__all__ = ["ProofreadingSession", "ProofreadingSuggestion", "ProofreadingStatus", "SuggestionStatus", "ImprovementLevel"]

if TYPE_CHECKING:
    from app.models.database.project import Project
    from app.models.database.paragraph import Paragraph


class ProofreadingSession(Base, ProgressTrackingMixin):
    """Proofreading session for tracking review cycles."""

    __tablename__ = "proofreading_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # LLM config for proofreading
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Progress tracking
    status: Mapped[str] = mapped_column(
        String(50), default=ProofreadingStatus.PENDING.value
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100 scale (percentage)
    total_paragraphs: Mapped[int] = mapped_column(Integer, default=0)
    completed_paragraphs: Mapped[int] = mapped_column(Integer, default=0)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="proofreading_sessions"
    )
    suggestions: Mapped[list["ProofreadingSuggestion"]] = relationship(
        "ProofreadingSuggestion", back_populates="session", cascade="all, delete-orphan"
    )


class ProofreadingSuggestion(Base):
    """Individual proofreading suggestion for a paragraph."""

    __tablename__ = "proofreading_suggestions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("proofreading_sessions.id", ondelete="CASCADE"), nullable=False
    )
    paragraph_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("paragraphs.id", ondelete="CASCADE"), nullable=False
    )

    # Translation versions
    original_translation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_translation: Mapped[Optional[str]] = mapped_column(Text)
    explanation: Mapped[Optional[str]] = mapped_column(Text)

    # Improvement assessment (from enhanced proofreading v2)
    improvement_level: Mapped[Optional[str]] = mapped_column(
        String(20), default=None
    )  # none, optional, recommended, critical
    issue_types: Mapped[Optional[list]] = mapped_column(
        JSON, default=None
    )  # ["accuracy", "naturalness", "modern_usage", "style_consistency", "readability"]

    # User action
    status: Mapped[str] = mapped_column(
        String(20), default=SuggestionStatus.PENDING.value
    )
    user_modified_text: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    session: Mapped["ProofreadingSession"] = relationship(
        "ProofreadingSession", back_populates="suggestions"
    )
    paragraph: Mapped["Paragraph"] = relationship(
        "Paragraph", back_populates="proofreading_suggestions"
    )

