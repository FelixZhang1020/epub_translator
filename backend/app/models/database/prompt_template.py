"""Prompt Template models for managing global and project-specific prompts."""

from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PromptCategory(str, Enum):
    """Categories of prompts."""
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    OPTIMIZATION = "optimization"
    PROOFREADING = "proofreading"
    REASONING = "reasoning"


class PromptTemplate(Base):
    """Global system prompt templates shared across all projects.

    This is the first layer of prompt engineering - reusable system prompts
    that define the LLM's role and behavior.
    """
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # analysis, translation, etc.
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Default user prompt template (can be overridden per project)
    default_user_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Variables that can be used in the prompts (JSON array of variable names)
    variables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    # Relationships
    project_configs: Mapped[list["ProjectPromptConfig"]] = relationship(
        "ProjectPromptConfig", back_populates="template"
    )


class ProjectPromptConfig(Base):
    """Project-specific prompt configuration.

    This is the second layer of prompt engineering - project-specific
    customizations that override or extend the global templates.
    """
    __tablename__ = "project_prompt_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # Reference to the selected global template (optional - can use custom)
    template_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True
    )

    # Custom system prompt (overrides template if provided)
    custom_system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Custom user prompt (overrides template's default if provided)
    custom_user_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Whether to use the template's system prompt or custom
    use_custom_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # Whether to use custom user prompt or template's default
    use_custom_user: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    template: Mapped[Optional["PromptTemplate"]] = relationship(
        "PromptTemplate", back_populates="project_configs"
    )


class VariableType(str, Enum):
    """Types of variable values."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"  # For arrays or objects


class ProjectVariable(Base):
    """User-defined variables for a project.

    These are custom key-value pairs that can be used in prompt templates
    via the {{user.variable_name}} syntax.
    """
    __tablename__ = "project_variables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Variable name (used as {{user.name}} in templates)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Variable value (stored as text, parsed based on value_type)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Type of the value for proper parsing
    value_type: Mapped[str] = mapped_column(
        String(20), default=VariableType.STRING.value
    )

    # Optional description for documentation
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Ensure unique variable names per project
    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uix_project_variable_name'),
    )
