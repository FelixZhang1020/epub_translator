# LLM Parameter & Prompt Variable System Refactoring Plan

## Executive Summary

The current system has **three competing variable-building systems**, **duplicated derived-variable extraction logic**, and **LLM parameters (temperature, max_tokens) that are stored but never used**. This plan proposes a unified architecture with clear separation of concerns.

---

## Current Architecture Problems

### Problem 1: LLM Parameters Lost in Transit

```
LLMConfiguration (DB)          ResolvedLLMConfig           LLM Call
┌─────────────────────┐       ┌─────────────────────┐     ┌─────────────────────┐
│ temperature: 0.7    │ ───►  │ temperature: 0.7    │ ──X │ temperature: ???    │
│ max_tokens: (none)  │       │ (carried but unused)│     │ (hardcoded 0.3)     │
└─────────────────────┘       └─────────────────────┘     └─────────────────────┘
```

- `LLMConfiguration` stores `temperature` in database
- `LLMConfigService.resolve_config()` returns it in `ResolvedLLMConfig`
- **But strategies hardcode their own values** (e.g., `direct.py:66` hardcodes 0.3)
- `max_tokens` is not even stored in the database model

### Problem 2: Three Variable Building Systems

| System | Location | Used By | Schema |
|--------|----------|---------|--------|
| **VariableService** | `variables.py:204-342` | Analysis (partial) | Nested `VariableContext` |
| **ContextBuilder** | `context_builder.py:404-542` | Translation | Nested dict |
| **Strategy-specific** | `direct.py:73-96` | Each strategy | Minimal flat dict |

Each produces different variable sets with different schemas!

### Problem 3: Duplicated Derived Variable Extraction

Two implementations of the same logic:

1. **VariableService._extract_derived_vars()** (`variables.py:408-486`)
   - Uses `DERIVED_MAPPINGS` with transforms
   - Creates 30+ fields with boolean flags (`has_analysis`, `has_terminology`, etc.)

2. **BookAnalysisContext.from_raw_analysis()** (`context.py:108-201`)
   - Different extraction logic
   - Different output schema
   - No boolean flags

### Problem 4: Inconsistent Parameter Flow by Stage

| Stage | Variable Source | Temperature | Max Tokens |
|-------|----------------|-------------|------------|
| Analysis | Manual + partial VariableService | Not passed (uses default) | Not passed |
| Translation | ContextBuilder | Hardcoded 0.3 | Hardcoded 4096 |
| Optimization | ContextBuilder | Hardcoded | Hardcoded |
| Proofreading | Per-endpoint custom | Hardcoded | Hardcoded |

---

## Proposed Architecture

### Design Principles

1. **Single Source of Truth** - One place builds variables, one place resolves LLM config
2. **Configuration Flows Through** - LLM params from config to actual LLM call
3. **Stage-Aware Population** - Only populate variables relevant to each stage
4. **Eliminate Duplication** - One derived extraction implementation
5. **Clear Interfaces** - Well-defined data contracts between layers

### New Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  /analysis  │  │/translation │  │/optimization│  │   /proofreading     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Unified Services Layer                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    LLMRuntimeConfig                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Resolution: Request Override → DB Config → Env Vars → Defaults │ │   │
│  │  │ Contains: provider, model, api_key, temperature, max_tokens    │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    UnifiedVariableBuilder                             │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Input: project_id, stage, source_text, context, etc.           │ │   │
│  │  │ Output: Flat Dict[str, Any] with namespaced keys               │ │   │
│  │  │ Sources: Project → Analysis → Content → Context → Meta → User  │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prompt Rendering Layer                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PromptLoader.load_for_project(project_id, stage)                     │   │
│  │     → Returns: PromptTemplate (system + user templates)              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PromptLoader.render(template, variables)                             │   │
│  │     → Returns: Rendered string with all variables resolved           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LLM Execution Layer                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ LLMGateway.execute(                                                  │   │
│  │     system_prompt: str,                                              │   │
│  │     user_prompt: str,                                                │   │
│  │     config: LLMRuntimeConfig  ← temperature, max_tokens from here!  │   │
│  │ )                                                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Design

### Component 1: LLMRuntimeConfig

**File:** `backend/app/core/llm/runtime_config.py` (NEW)

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class LLMRuntimeConfig:
    """Complete LLM configuration resolved for a single request.

    This is the ONLY place LLM parameters should come from.
    All stages use this same config structure.
    """
    # Connection
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None

    # Generation parameters (with sensible defaults)
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None

    # Response format
    response_format: Optional[Dict[str, Any]] = None

    # Metadata (for logging/tracking)
    config_id: Optional[str] = None
    config_name: Optional[str] = None

    def get_litellm_model(self) -> str:
        """Get model string in LiteLLM format."""
        provider_prefixes = {
            "openai": "",
            "anthropic": "anthropic/",
            "gemini": "gemini/",
            "qwen": "openai/",  # Qwen uses OpenAI-compatible API
            "deepseek": "deepseek/",
        }
        prefix = provider_prefixes.get(self.provider, "")
        return f"{prefix}{self.model}"

    def to_litellm_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs for litellm.acompletion()."""
        kwargs = {
            "model": self.get_litellm_model(),
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.frequency_penalty is not None:
            kwargs["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            kwargs["presence_penalty"] = self.presence_penalty
        if self.response_format:
            kwargs["response_format"] = self.response_format
        return kwargs


@dataclass
class LLMConfigOverride:
    """Optional overrides that can be passed from API request."""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    model: Optional[str] = None  # Override model selection


class LLMConfigResolver:
    """Resolves LLM configuration from multiple sources.

    Resolution priority:
    1. Request override (for testing/debugging)
    2. Stored config by ID
    3. Active config (is_active=True)
    4. Default config (is_default=True)
    5. Environment variables
    """

    # Default values when nothing else is configured
    DEFAULTS = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    # Stage-specific default temperatures (can be overridden by config)
    STAGE_TEMPERATURES = {
        "analysis": 0.3,      # More deterministic for structured output
        "translation": 0.5,   # Balanced creativity
        "optimization": 0.3,  # Careful refinement
        "proofreading": 0.3,  # Conservative suggestions
    }

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        *,
        config_id: Optional[str] = None,
        override: Optional[LLMConfigOverride] = None,
        stage: Optional[str] = None,
    ) -> LLMRuntimeConfig:
        """Resolve complete LLM configuration.

        Args:
            db: Database session
            config_id: Specific config ID to use
            override: Request-level parameter overrides
            stage: Current stage (affects default temperature)

        Returns:
            Fully resolved LLMRuntimeConfig ready for use
        """
        from app.models.database.llm_configuration import LLMConfiguration
        from sqlalchemy import select
        import os

        config_record: Optional[LLMConfiguration] = None

        # Try to load from database
        if config_id:
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.id == config_id)
            )
            config_record = result.scalar_one_or_none()

        if not config_record:
            # Try active config
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.is_active == True)
            )
            config_record = result.scalar_one_or_none()

        if not config_record:
            # Try default config
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.is_default == True)
            )
            config_record = result.scalar_one_or_none()

        # Build base config
        if config_record:
            # Resolve API key (DB or env var)
            api_key = config_record.api_key
            if not api_key:
                env_key = f"{config_record.provider.upper()}_API_KEY"
                api_key = os.environ.get(env_key, "")

            runtime_config = LLMRuntimeConfig(
                provider=config_record.provider,
                model=config_record.model,
                api_key=api_key,
                base_url=config_record.base_url,
                temperature=config_record.temperature or cls.DEFAULTS["temperature"],
                max_tokens=config_record.max_tokens or cls.DEFAULTS["max_tokens"],
                config_id=config_record.id,
                config_name=config_record.name,
            )
        else:
            # Fallback to environment variables
            runtime_config = LLMRuntimeConfig(
                provider=cls.DEFAULTS["provider"],
                model=os.environ.get("LLM_MODEL", cls.DEFAULTS["model"]),
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                temperature=cls.DEFAULTS["temperature"],
                max_tokens=cls.DEFAULTS["max_tokens"],
            )

        # Apply stage-specific temperature if not explicitly set in config
        if stage and config_record and config_record.temperature is None:
            stage_temp = cls.STAGE_TEMPERATURES.get(stage)
            if stage_temp:
                runtime_config.temperature = stage_temp

        # Apply request overrides (highest priority)
        if override:
            if override.temperature is not None:
                runtime_config.temperature = override.temperature
            if override.max_tokens is not None:
                runtime_config.max_tokens = override.max_tokens
            if override.top_p is not None:
                runtime_config.top_p = override.top_p
            if override.model is not None:
                runtime_config.model = override.model

        return runtime_config
```

### Component 2: UnifiedVariableBuilder

**File:** `backend/app/core/prompts/variable_builder.py` (NEW)

```python
"""Unified variable builder for all prompt templates.

This is the SINGLE SOURCE OF TRUTH for template variables.
All stages use this builder to ensure consistency.
"""

from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

StageType = Literal["analysis", "translation", "optimization", "proofreading"]


@dataclass
class VariableInput:
    """Input data for variable building.

    Collects all possible inputs; builder extracts what's needed per stage.
    """
    project_id: str
    stage: StageType

    # Content (stage-dependent)
    source_text: Optional[str] = None
    target_text: Optional[str] = None
    chapter_title: Optional[str] = None
    sample_paragraphs: Optional[str] = None  # For analysis stage

    # Context (for translation coherence)
    previous_source: Optional[str] = None
    previous_target: Optional[str] = None
    next_source: Optional[str] = None

    # Pipeline data (from previous steps)
    reference_translation: Optional[str] = None
    suggested_changes: Optional[str] = None

    # Position metadata
    paragraph_index: Optional[int] = None
    chapter_index: Optional[int] = None


class UnifiedVariableBuilder:
    """Builds template variables for all stages consistently.

    Output is always a FLAT dictionary with namespaced keys:
    - project.title, project.author, ...
    - content.source, content.target, ...
    - context.previous_source, context.previous_target, ...
    - derived.writing_style, derived.tone, derived.has_analysis, ...
    - meta.word_count, meta.stage, ...
    - user.* (custom user variables)
    """

    # Derived variable extraction mappings
    # Format: (source_path, target_key, transform_function)
    DERIVED_MAPPINGS: List[tuple] = [
        # Author info
        ("author_name", "author_name", None),
        ("author_biography", "author_biography", "format_multiline"),
        ("author_background", "author_biography", "format_multiline"),  # Fallback

        # Work profile
        ("writing_style", "writing_style", None),
        ("tone", "tone", None),
        ("target_audience", "target_audience", None),
        ("genre_conventions", "genre_conventions", None),

        # Terminology
        ("key_terminology", "terminology_table", "format_terminology"),
        ("key_terminology", "key_terminology", None),  # Raw dict

        # Translation principles (nested in default schema)
        ("translation_principles.priority_order", "priority_order", "format_list"),
        ("translation_principles.faithfulness_boundary", "faithfulness_boundary", None),
        ("translation_principles.permissible_adaptation", "permissible_adaptation", None),
        ("translation_principles.style_constraints", "style_constraints", None),
        ("translation_principles.red_lines", "red_lines", None),

        # Direct translation principles (flat in some schemas)
        ("priority_order", "priority_order", "format_list"),
        ("faithfulness_boundary", "faithfulness_boundary", None),
        ("permissible_adaptation", "permissible_adaptation", None),
        ("style_constraints", "style_constraints", None),
        ("red_lines", "red_lines", None),

        # Custom guidelines
        ("custom_guidelines", "custom_guidelines", "format_list"),
    ]

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        input_data: VariableInput,
    ) -> Dict[str, Any]:
        """Build complete flat variable dictionary.

        Args:
            db: Database session
            input_data: All input data for variable building

        Returns:
            Flat dictionary with namespaced keys (e.g., "project.title")
        """
        variables: Dict[str, Any] = {}

        # 1. Load project variables
        project_vars = await cls._build_project_vars(db, input_data.project_id)
        variables.update(project_vars)

        # 2. Build content variables (stage-aware)
        content_vars = cls._build_content_vars(input_data)
        variables.update(content_vars)

        # 3. Build context variables (for translation coherence)
        context_vars = cls._build_context_vars(input_data)
        variables.update(context_vars)

        # 4. Build derived variables (from analysis)
        derived_vars = await cls._build_derived_vars(db, input_data.project_id)
        variables.update(derived_vars)

        # 5. Build meta variables (computed at runtime)
        meta_vars = cls._build_meta_vars(input_data)
        variables.update(meta_vars)

        # 6. Build pipeline variables
        pipeline_vars = cls._build_pipeline_vars(input_data)
        variables.update(pipeline_vars)

        # 7. Load user-defined variables
        user_vars = await cls._load_user_vars(input_data.project_id)
        variables.update(user_vars)

        return variables

    @classmethod
    async def _build_project_vars(
        cls, db: AsyncSession, project_id: str
    ) -> Dict[str, Any]:
        """Build project.* variables from database."""
        from app.models.database.project import Project

        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            return {}

        return {
            "project.title": project.epub_title or project.name or "",
            "project.author": project.epub_author or "",
            "project.author_background": project.author_background or "",
            "project.name": project.name or "",
            "project.source_language": project.epub_language or "en",
            "project.target_language": "zh",  # TODO: Make configurable
            "project.total_chapters": project.total_chapters or 0,
            "project.total_paragraphs": project.total_paragraphs or 0,
        }

    @classmethod
    def _build_content_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build content.* variables from input."""
        variables: Dict[str, Any] = {}

        if input_data.source_text:
            variables["content.source"] = input_data.source_text
            # Legacy aliases
            variables["content.source_text"] = input_data.source_text
            variables["content.original_text"] = input_data.source_text

        if input_data.target_text:
            variables["content.target"] = input_data.target_text
            # Legacy aliases
            variables["content.translated_text"] = input_data.target_text
            variables["content.existing_translation"] = input_data.target_text

        if input_data.chapter_title:
            variables["content.chapter_title"] = input_data.chapter_title

        if input_data.sample_paragraphs:
            variables["content.sample_paragraphs"] = input_data.sample_paragraphs

        return variables

    @classmethod
    def _build_context_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build context.* variables for translation coherence."""
        variables: Dict[str, Any] = {}

        if input_data.previous_source:
            variables["context.previous_source"] = input_data.previous_source
        if input_data.previous_target:
            variables["context.previous_target"] = input_data.previous_target
        if input_data.next_source:
            variables["context.next_source"] = input_data.next_source

        # Boolean flags for conditional rendering
        variables["context.has_previous"] = bool(
            input_data.previous_source or input_data.previous_target
        )
        variables["context.has_next"] = bool(input_data.next_source)

        return variables

    @classmethod
    async def _build_derived_vars(
        cls, db: AsyncSession, project_id: str
    ) -> Dict[str, Any]:
        """Build derived.* variables from analysis results.

        This is the SINGLE implementation of derived variable extraction.
        """
        from app.models.database.book_analysis import BookAnalysis

        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        analysis = result.scalar_one_or_none()

        # Default empty state
        variables: Dict[str, Any] = {
            "derived.has_analysis": False,
            "derived.writing_style": "",
            "derived.tone": "",
            "derived.target_audience": "",
            "derived.genre_conventions": "",
            "derived.terminology_table": "",
            "derived.priority_order": "",
            "derived.faithfulness_boundary": "",
            "derived.permissible_adaptation": "",
            "derived.style_constraints": "",
            "derived.red_lines": "",
            "derived.custom_guidelines": "",
            "derived.author_name": "",
            "derived.author_biography": "",
            # Boolean flags
            "derived.has_writing_style": False,
            "derived.has_tone": False,
            "derived.has_terminology": False,
            "derived.has_target_audience": False,
            "derived.has_genre_conventions": False,
            "derived.has_translation_principles": False,
            "derived.has_custom_guidelines": False,
            "derived.has_style_constraints": False,
            "derived.has_author_biography": False,
        }

        if not analysis or not analysis.raw_analysis:
            return variables

        raw = analysis.raw_analysis
        variables["derived.has_analysis"] = True

        # Extract using mappings
        for source_path, target_key, transform in cls.DERIVED_MAPPINGS:
            value = cls._get_nested_value(raw, source_path)
            if value is not None:
                if transform:
                    value = cls._apply_transform(value, transform)
                variables[f"derived.{target_key}"] = value

        # Set boolean flags based on extracted values
        variables["derived.has_writing_style"] = bool(variables.get("derived.writing_style"))
        variables["derived.has_tone"] = bool(variables.get("derived.tone"))
        variables["derived.has_terminology"] = bool(variables.get("derived.terminology_table"))
        variables["derived.has_target_audience"] = bool(variables.get("derived.target_audience"))
        variables["derived.has_genre_conventions"] = bool(variables.get("derived.genre_conventions"))
        variables["derived.has_translation_principles"] = bool(
            variables.get("derived.priority_order") or
            variables.get("derived.faithfulness_boundary")
        )
        variables["derived.has_custom_guidelines"] = bool(variables.get("derived.custom_guidelines"))
        variables["derived.has_style_constraints"] = bool(variables.get("derived.style_constraints"))
        variables["derived.has_author_biography"] = bool(variables.get("derived.author_biography"))

        return variables

    @classmethod
    def _build_meta_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build meta.* variables computed at runtime."""
        variables: Dict[str, Any] = {
            "meta.stage": input_data.stage,
        }

        if input_data.source_text:
            variables["meta.word_count"] = len(input_data.source_text.split())
            variables["meta.char_count"] = len(input_data.source_text)

        if input_data.paragraph_index is not None:
            variables["meta.paragraph_index"] = input_data.paragraph_index

        if input_data.chapter_index is not None:
            variables["meta.chapter_index"] = input_data.chapter_index

        return variables

    @classmethod
    def _build_pipeline_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build pipeline.* variables from previous processing steps."""
        variables: Dict[str, Any] = {}

        if input_data.reference_translation:
            variables["pipeline.reference_translation"] = input_data.reference_translation
            variables["pipeline.has_reference"] = True
        else:
            variables["pipeline.has_reference"] = False

        if input_data.suggested_changes:
            variables["pipeline.suggested_changes"] = input_data.suggested_changes
            variables["pipeline.has_suggestions"] = True
        else:
            variables["pipeline.has_suggestions"] = False

        return variables

    @classmethod
    async def _load_user_vars(cls, project_id: str) -> Dict[str, Any]:
        """Load user-defined variables from project config."""
        from app.core.prompts.loader import PromptLoader

        try:
            user_vars = PromptLoader.load_project_variables(project_id)
            # Prefix with user. namespace
            return {f"user.{k}": v for k, v in user_vars.items() if k != "macros"}
        except Exception:
            return {}

    # ========== Helper Methods ==========

    @classmethod
    def _get_nested_value(cls, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    @classmethod
    def _apply_transform(cls, value: Any, transform: str) -> Any:
        """Apply transform function to value."""
        if transform == "format_terminology":
            return cls._format_terminology(value)
        elif transform == "format_list":
            return cls._format_list(value)
        elif transform == "format_multiline":
            return cls._format_multiline(value)
        return value

    @classmethod
    def _format_terminology(cls, terms: Any) -> str:
        """Format terminology as markdown list."""
        if isinstance(terms, dict):
            lines = [f"- **{en}**: {zh}" for en, zh in terms.items() if en and zh]
            return "\n".join(lines)
        elif isinstance(terms, list):
            lines = []
            for term in terms:
                if isinstance(term, dict):
                    en = term.get("english_term") or term.get("english") or term.get("term", "")
                    zh = term.get("chinese_translation") or term.get("chinese", "")
                    if en and zh:
                        lines.append(f"- **{en}**: {zh}")
                else:
                    lines.append(f"- {term}")
            return "\n".join(lines)
        return str(terms) if terms else ""

    @classmethod
    def _format_list(cls, items: Any) -> str:
        """Format as bullet list or comma-separated inline."""
        if isinstance(items, list):
            if len(items) <= 3:
                return ", ".join(str(i) for i in items)
            return "\n".join(f"- {i}" for i in items)
        return str(items) if items else ""

    @classmethod
    def _format_multiline(cls, value: Any) -> str:
        """Format potentially structured value as readable text."""
        if isinstance(value, str):
            return value
        elif isinstance(value, dict):
            parts = []
            for k, v in value.items():
                if v:
                    # Convert snake_case to Title Case
                    label = k.replace("_", " ").title()
                    parts.append(f"**{label}**: {v}")
            return "\n\n".join(parts)
        return str(value) if value else ""
```

### Component 3: Simplified LLMGateway

**File:** `backend/app/core/llm/gateway.py` (Refactored)

```python
"""Unified LLM gateway for all stages.

Replaces: translation/pipeline/llm_gateway.py
All LLM calls go through this single gateway.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from litellm import acompletion

from .runtime_config import LLMRuntimeConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int

    @property
    def estimated_cost(self) -> float:
        """Estimate cost based on token counts."""
        # TODO: Use model-specific pricing from config
        return 0.0


class LLMGateway:
    """Unified gateway for all LLM interactions.

    Usage:
        config = await LLMConfigResolver.resolve(db, stage="translation")
        response = await LLMGateway.execute(
            system_prompt="You are a translator...",
            user_prompt="Translate: Hello",
            config=config,
        )
    """

    @classmethod
    async def execute(
        cls,
        system_prompt: str,
        user_prompt: str,
        config: LLMRuntimeConfig,
        *,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """Execute LLM call with given prompts and config.

        Args:
            system_prompt: System message content
            user_prompt: User message content
            config: Complete LLM configuration (contains temperature, max_tokens, etc.)
            response_format: Optional JSON schema for structured output

        Returns:
            Standardized LLMResponse
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Build kwargs from config
        kwargs = config.to_litellm_kwargs()
        kwargs["messages"] = messages

        if response_format:
            kwargs["response_format"] = response_format

        logger.info(
            f"LLM call: model={config.model}, temp={config.temperature}, "
            f"max_tokens={config.max_tokens}"
        )

        try:
            response = await acompletion(**kwargs)

            return LLMResponse(
                content=response.choices[0].message.content,
                model=config.model,
                provider=config.provider,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
```

### Component 4: Simplified Stage Services

**Example: Translation Service** (Refactored)

```python
"""Translation service using unified components.

This shows the simplified pattern that all stages should follow.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.runtime_config import LLMConfigResolver, LLMConfigOverride
from app.core.llm.gateway import LLMGateway
from app.core.prompts.variable_builder import UnifiedVariableBuilder, VariableInput
from app.core.prompts.loader import PromptLoader


async def translate_paragraph(
    db: AsyncSession,
    project_id: str,
    paragraph_id: str,
    *,
    config_id: Optional[str] = None,
    config_override: Optional[LLMConfigOverride] = None,
) -> str:
    """Translate a single paragraph.

    This is the simplified flow:
    1. Resolve LLM config (unified)
    2. Build variables (unified)
    3. Render prompts
    4. Execute LLM call
    """
    # 1. Resolve LLM configuration
    llm_config = await LLMConfigResolver.resolve(
        db,
        config_id=config_id,
        override=config_override,
        stage="translation",
    )

    # 2. Load paragraph and context
    paragraph = await load_paragraph(db, paragraph_id)
    prev_paragraph = await load_previous_paragraph(db, paragraph)

    # 3. Build variables (unified)
    variables = await UnifiedVariableBuilder.build(
        db,
        VariableInput(
            project_id=project_id,
            stage="translation",
            source_text=paragraph.original_text,
            previous_source=prev_paragraph.original_text if prev_paragraph else None,
            previous_target=prev_paragraph.latest_translation if prev_paragraph else None,
            paragraph_index=paragraph.paragraph_number,
            chapter_index=paragraph.chapter.chapter_number,
            chapter_title=paragraph.chapter.title,
        ),
    )

    # 4. Load and render prompts
    template = PromptLoader.load_for_project(project_id, "translation")
    system_prompt = PromptLoader.render(template.system_prompt, variables)
    user_prompt = PromptLoader.render(template.user_prompt_template, variables)

    # 5. Execute LLM call (config contains temperature, max_tokens)
    response = await LLMGateway.execute(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=llm_config,
    )

    return response.content
```

---

## Database Schema Changes

### Add max_tokens to LLMConfiguration

```python
# backend/app/models/database/llm_configuration.py

class LLMConfiguration(Base):
    __tablename__ = "llm_configurations"

    # ... existing fields ...

    # ADD: max_tokens field
    max_tokens = Column(Integer, nullable=True, default=4096)

    # ADD: Optional additional parameters
    top_p = Column(Float, nullable=True)
    frequency_penalty = Column(Float, nullable=True)
    presence_penalty = Column(Float, nullable=True)
```

**Migration:**
```python
# backend/migrations/versions/xxx_add_max_tokens_to_llm_config.py

def upgrade():
    op.add_column('llm_configurations', sa.Column('max_tokens', sa.Integer(), nullable=True, default=4096))
    op.add_column('llm_configurations', sa.Column('top_p', sa.Float(), nullable=True))
    op.add_column('llm_configurations', sa.Column('frequency_penalty', sa.Float(), nullable=True))
    op.add_column('llm_configurations', sa.Column('presence_penalty', sa.Float(), nullable=True))
```

---

## Files to Modify/Remove

### Phase 1: Add New Components

| Action | File | Description |
|--------|------|-------------|
| CREATE | `backend/app/core/llm/runtime_config.py` | LLMRuntimeConfig + LLMConfigResolver |
| CREATE | `backend/app/core/prompts/variable_builder.py` | UnifiedVariableBuilder |
| CREATE | `backend/app/core/llm/gateway.py` | Unified LLMGateway |

### Phase 2: Refactor Existing

| Action | File | Changes |
|--------|------|---------|
| MODIFY | `backend/app/models/database/llm_configuration.py` | Add max_tokens, top_p, etc. |
| MODIFY | `backend/app/core/llm/config_service.py` | Use LLMConfigResolver |
| MODIFY | `backend/app/core/analysis/service.py` | Use unified components |
| MODIFY | `backend/app/api/v1/routes/translation.py` | Use unified components |
| MODIFY | `backend/app/api/v1/routes/analysis.py` | Use unified components |
| MODIFY | `backend/app/api/v1/routes/proofreading.py` | Use unified components |

### Phase 3: Remove Deprecated

| Action | File | Reason |
|--------|------|--------|
| DEPRECATE | `backend/app/core/prompts/variables.py` | Replaced by variable_builder.py |
| DEPRECATE | `backend/app/core/translation/pipeline/context_builder.py` | Variable building moved to variable_builder.py |
| DEPRECATE | `backend/app/core/translation/models/context.py` | BookAnalysisContext extraction replaced |
| SIMPLIFY | `backend/app/core/translation/strategies/*.py` | Remove get_template_variables() |
| DEPRECATE | `backend/app/core/translation/pipeline/llm_gateway.py` | Replaced by llm/gateway.py |

---

## Variable Namespace Reference

After refactoring, all variables follow this consistent schema:

```
project.*
├── title                 # Book title
├── author                # Author name
├── author_background     # Author background info
├── source_language       # Source language code (e.g., "en")
├── target_language       # Target language code (e.g., "zh")
├── total_chapters        # Total chapter count
└── total_paragraphs      # Total paragraph count

content.*
├── source                # Source text to translate (canonical)
├── target                # Current translation (canonical)
├── source_text           # Legacy alias for source
├── translated_text       # Legacy alias for target
├── chapter_title         # Current chapter title
└── sample_paragraphs     # Sample paragraphs (analysis stage)

context.*
├── previous_source       # Previous paragraph source
├── previous_target       # Previous paragraph translation
├── next_source           # Next paragraph source
├── has_previous          # Boolean: has previous context
└── has_next              # Boolean: has next context

derived.*
├── writing_style         # Extracted writing style
├── tone                  # Extracted tone
├── target_audience       # Target audience description
├── genre_conventions     # Genre conventions
├── terminology_table     # Formatted terminology (markdown)
├── priority_order        # Translation priority order
├── faithfulness_boundary # Strict translation boundaries
├── permissible_adaptation# Allowed adaptations
├── style_constraints     # Style constraints
├── red_lines             # Prohibited actions
├── custom_guidelines     # Custom guidelines
├── author_name           # Author name from analysis
├── author_biography      # Author biography
├── has_analysis          # Boolean: analysis exists
├── has_writing_style     # Boolean: writing style defined
├── has_tone              # Boolean: tone defined
├── has_terminology       # Boolean: terminology defined
├── has_translation_principles # Boolean: principles defined
├── has_custom_guidelines # Boolean: custom guidelines exist
└── has_style_constraints # Boolean: style constraints exist

meta.*
├── stage                 # Current stage name
├── word_count            # Source text word count
├── char_count            # Source text character count
├── paragraph_index       # Current paragraph index
└── chapter_index         # Current chapter index

pipeline.*
├── reference_translation # Matched reference translation
├── suggested_changes     # User-provided suggestions
├── has_reference         # Boolean: has reference
└── has_suggestions       # Boolean: has suggestions

user.*
└── (any custom variables from variables.json)
```

---

## Migration Strategy

### Step 1: Create New Components (Non-Breaking)
- Add new files without removing old ones
- New code paths can use new components
- Old code continues to work

### Step 2: Migrate Stage by Stage
1. **Translation stage first** (most complex, validates design)
2. **Analysis stage** (simpler)
3. **Optimization stage** (shares with translation)
4. **Proofreading stage** (similar to optimization)

### Step 3: Remove Deprecated Code
- Only after all stages migrated
- Keep aliases for backward compatibility in templates
- Update documentation

---

## Testing Strategy

### Unit Tests
- `LLMConfigResolver.resolve()` - all priority scenarios
- `UnifiedVariableBuilder.build()` - all variable namespaces
- `LLMGateway.execute()` - success and error cases

### Integration Tests
- Full translation flow with new components
- Temperature/max_tokens actually used in LLM calls
- Variable consistency across stages

### Template Validation
- Ensure all existing templates work with new variable schema
- Test conditional blocks (`{{#if derived.has_analysis}}`)
- Test all type modifiers (`:list`, `:table`, `:inline`)

---

## Summary

This refactoring:

1. **Unifies LLM configuration** - One `LLMRuntimeConfig` carries all params from DB to LLM call
2. **Unifies variable building** - One `UnifiedVariableBuilder` for all stages
3. **Eliminates duplication** - Single derived extraction, single gateway
4. **Fixes the template issue** - `derived.*` variables properly populated in all code paths
5. **Makes temperature/max_tokens configurable** - Stored in DB, flows through to actual calls
6. **Simplifies stage services** - Each stage follows same simple 5-step pattern

The key insight: **configuration and variables should flow through the system, not be rebuilt at each layer**.
