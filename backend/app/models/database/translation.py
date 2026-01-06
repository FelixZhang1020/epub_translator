"""Translation and TranslationTask database models."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project
    from app.models.database.paragraph import Paragraph
    from app.models.database.translation_reasoning import TranslationReasoning
    from app.models.database.translation_conversation import TranslationConversation


class TranslationMode(str, Enum):
    """Translation mode enum."""
    AUTHOR_BASED = "author_based"
    OPTIMIZATION = "optimization"


class TaskStatus(str, Enum):
    """Translation task status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Translation(Base):
    """Individual paragraph translation result."""

    __tablename__ = "translations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    paragraph_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("paragraphs.id", ondelete="CASCADE"), nullable=False
    )

    # Translation content
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Translation metadata
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # Version control
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_manual_edit: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    paragraph: Mapped["Paragraph"] = relationship(
        "Paragraph", back_populates="translations"
    )
    reasoning: Mapped[Optional["TranslationReasoning"]] = relationship(
        "TranslationReasoning", back_populates="translation", uselist=False,
        cascade="all, delete-orphan"
    )
    conversation: Mapped[Optional["TranslationConversation"]] = relationship(
        "TranslationConversation", back_populates="translation", uselist=False,
        cascade="all, delete-orphan"
    )


class TranslationTask(Base):
    """Translation task for tracking progress and enabling pause/resume."""

    __tablename__ = "translation_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Task configuration
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Progress tracking
    status: Mapped[str] = mapped_column(String(50), default=TaskStatus.PENDING.value)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    total_paragraphs: Mapped[int] = mapped_column(Integer, default=0)
    completed_paragraphs: Mapped[int] = mapped_column(Integer, default=0)
    current_chapter_id: Mapped[Optional[str]] = mapped_column(String(36))
    current_paragraph_id: Mapped[Optional[str]] = mapped_column(String(36))

    # Configuration
    author_context: Mapped[Optional[dict]] = mapped_column(JSON)
    custom_prompts: Mapped[Optional[list]] = mapped_column(JSON)
    selected_chapters: Mapped[Optional[list]] = mapped_column(JSON)  # None = all

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")

    def update_progress(self):
        """Update progress percentage based on completed paragraphs."""
        if self.total_paragraphs > 0:
            self.progress = self.completed_paragraphs / self.total_paragraphs
