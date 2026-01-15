"""BookAnalysis database model for storing LLM-generated book analysis."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project


class BookAnalysis(Base):
    """Book analysis result from LLM for translation context."""

    __tablename__ = "book_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Dynamic analysis result - stores raw LLM response as JSON
    # Structure depends on the prompt template used
    raw_analysis: Mapped[Optional[dict]] = mapped_column(JSON)

    # User confirmation
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    user_modifications: Mapped[Optional[dict]] = mapped_column(JSON)  # Track changes

    # LLM config used for analysis
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="analysis")

