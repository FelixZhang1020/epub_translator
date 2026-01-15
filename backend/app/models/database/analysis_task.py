"""Analysis task database model for tracking streaming analysis progress."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.project import Project


class AnalysisTask(Base):
    """Analysis task for tracking streaming analysis progress.

    This allows progress to persist across page refreshes during long-running
    book analysis operations.
    """

    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Task status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pending, processing, completed, failed, cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    current_step: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # loading, sampling, building_prompt, analyzing, parsing, saving, complete
    step_message: Mapped[Optional[str]] = mapped_column(Text)

    # LLM configuration
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

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
        "Project", back_populates="analysis_tasks"
    )

