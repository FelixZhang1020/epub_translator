"""TranslationConversation database models for multi-turn translation discussions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base

if TYPE_CHECKING:
    from app.models.database.translation import Translation


class TranslationConversation(Base):
    """Conversation session for a translation discussion."""

    __tablename__ = "translation_conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    translation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("translations.id", ondelete="CASCADE"), nullable=False
    )

    # LLM config used
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Context snapshot (for consistency across messages)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    initial_translation: Mapped[str] = mapped_column(Text, nullable=False)

    # Stats
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    translation: Mapped["Translation"] = relationship(
        "Translation", back_populates="conversation"
    )
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage", back_populates="conversation",
        cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(Base):
    """Individual message in a translation conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("translation_conversations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user/assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # For assistant messages - detected translation suggestion
    suggested_translation: Mapped[Optional[str]] = mapped_column(Text)
    suggestion_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    # Token usage for this message
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    conversation: Mapped["TranslationConversation"] = relationship(
        "TranslationConversation", back_populates="messages"
    )

