"""TranslationReasoning database model for on-demand translation explanations."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.translation import Translation


class TranslationReasoning(Base):
    """On-demand reasoning/explanation for a translation."""

    __tablename__ = "translation_reasonings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    translation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("translations.id", ondelete="CASCADE"), nullable=False
    )

    # Reasoning content
    reasoning_text: Mapped[str] = mapped_column(Text, nullable=False)

    # LLM config used
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    translation: Mapped["Translation"] = relationship(
        "Translation", back_populates="reasoning"
    )
