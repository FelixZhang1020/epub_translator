"""Project database model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.chapter import Chapter
    from app.models.database.translation import TranslationTask
    from app.models.database.book_analysis import BookAnalysis
    from app.models.database.analysis_task import AnalysisTask
    from app.models.database.reference_epub import ReferenceEPUB
    from app.models.database.paragraph_match import ParagraphMatch
    from app.models.database.proofreading import ProofreadingSession


class Project(Base):
    """EPUB translation project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # EPUB metadata
    epub_title: Mapped[Optional[str]] = mapped_column(String(500))
    epub_author: Mapped[Optional[str]] = mapped_column(String(255))
    epub_language: Mapped[Optional[str]] = mapped_column(String(10))
    epub_metadata: Mapped[Optional[dict]] = mapped_column(JSON)

    # Table of Contents structure (hierarchical)
    toc_structure: Mapped[Optional[list]] = mapped_column(JSON)

    # Author context for translation
    author_background: Mapped[Optional[str]] = mapped_column(Text)
    custom_prompts: Mapped[Optional[list]] = mapped_column(JSON)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="created")
    total_chapters: Mapped[int] = mapped_column(default=0)
    total_paragraphs: Mapped[int] = mapped_column(default=0)

    # Workflow tracking
    current_step: Mapped[str] = mapped_column(String(50), default="upload")
    has_reference_epub: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    translation_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    proofreading_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # User preferences
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    chapters: Mapped[list["Chapter"]] = relationship(
        "Chapter", back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["TranslationTask"]] = relationship(
        "TranslationTask", back_populates="project", cascade="all, delete-orphan"
    )
    analysis: Mapped[Optional["BookAnalysis"]] = relationship(
        "BookAnalysis", back_populates="project", uselist=False,
        cascade="all, delete-orphan"
    )
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(
        "AnalysisTask", back_populates="project", cascade="all, delete-orphan"
    )
    reference_epub: Mapped[Optional["ReferenceEPUB"]] = relationship(
        "ReferenceEPUB", back_populates="project", uselist=False,
        cascade="all, delete-orphan"
    )
    paragraph_matches: Mapped[list["ParagraphMatch"]] = relationship(
        "ParagraphMatch", back_populates="project", cascade="all, delete-orphan"
    )
    proofreading_sessions: Mapped[list["ProofreadingSession"]] = relationship(
        "ProofreadingSession", back_populates="project", cascade="all, delete-orphan"
    )

