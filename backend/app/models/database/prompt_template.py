"""Prompt Template models for managing global and project-specific prompts."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import PromptCategory  # noqa: F401 - re-exported

# Re-export for backwards compatibility
__all__ = ["PromptTemplate", "ProjectPromptConfig", "PromptCategory"]


class PromptTemplate(Base):
    """Global system prompt templates shared across all projects.

    This is the first layer of prompt engineering - reusable system prompts
    that define the LLM's role and behavior.

    NOTE: Prompt content is stored in files at backend/prompts/{category}/
    The template_name field references files like system.{template_name}.md
    """
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # analysis, translation, etc.

    # Reference to file template (e.g., "default", "reformed-theology")
    # Content is loaded from backend/prompts/{category}/system.{template_name}.md
    template_name: Mapped[str] = mapped_column(String(100), default="default")

    # Whether this is a built-in template (cannot be deleted)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Whether this is the default template for its category
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ProjectPromptConfig(Base):
    """Project-specific prompt configuration (metadata only).

    Maps a project to a global template for each category.
    - System prompts: Always loaded from global templates
    - User prompts: Loaded from project files at projects/{project_id}/prompts/{category}/user.md

    This follows the "only metadata in database" principle.
    Actual prompt content is stored in files, not in the database.
    """
    __tablename__ = "project_prompt_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # Template name referencing filesystem template (e.g., 'default', 'reformed-theology')
    # Points to: backend/prompts/{category}/system.{template_name}.md
    template_name: Mapped[str] = mapped_column(String(100), default="default")

    # Whether project has a custom user prompt file
    # If True, load from: projects/{project_id}/prompts/{category}/user.md
    # If False, use global: backend/prompts/{category}/user.{template_name}.md
    has_custom_user_prompt: Mapped[bool] = mapped_column(Boolean, default=False)

    # Legacy columns (kept for backward compatibility)
    use_custom_system: Mapped[bool] = mapped_column(Boolean, default=False)
    use_custom_user: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# NOTE: ProjectVariable has been removed from database storage.
# Project variables are now stored in files at: projects/{project_id}/variables.json
# This follows the "only metadata in database" principle.
#
# Example variables.json:
# {
#   "custom_term": "value",
#   "author_style": "formal",
#   "terminology": {"term1": "translation1", ...}
# }
#
# Variables are accessed in templates via {{user.variable_name}} syntax.

