"""Unified Variable Builder for Prompt Templates.

This module provides a SINGLE SOURCE OF TRUTH for all template variables.
All stages (analysis, translation, optimization, proofreading) use this
builder to ensure consistent variable availability.

Key components:
- VariableInput: Collects all input data for variable building
- UnifiedVariableBuilder: Builds complete flat variable dictionary

Output is always a FLAT dictionary with namespaced keys:
- project.title, project.author, ...
- content.source, content.target, ...
- context.previous_source, context.previous_target, ...
- derived.writing_style, derived.tone, derived.has_analysis, ...
- meta.word_count, meta.stage, ...
- pipeline.reference_translation, pipeline.suggested_changes, ...
- user.* (custom user variables from variables.json)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Stage type
StageType = Literal["analysis", "translation", "optimization", "proofreading"]


@dataclass
class VariableInput:
    """Input data for variable building.

    Collects all possible inputs; builder extracts what's needed per stage.
    All fields are optional - pass only what's available for the current context.
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

    # Pipeline data (from previous processing steps)
    reference_translation: Optional[str] = None
    suggested_changes: Optional[str] = None

    # Position metadata
    paragraph_index: Optional[int] = None
    chapter_index: Optional[int] = None
    total_paragraphs: Optional[int] = None
    total_chapters: Optional[int] = None


class UnifiedVariableBuilder:
    """Builds template variables for all stages consistently.

    This is the SINGLE SOURCE OF TRUTH for template variables.
    All stages use this builder to ensure:
    1. Consistent variable names across all stages
    2. All derived.* variables properly populated
    3. All boolean flags (has_*) correctly set
    4. Single extraction logic for analysis data

    Output is always a FLAT dictionary with namespaced keys.
    """

    # =========================================================================
    # Derived Variable Extraction Mappings
    # =========================================================================
    # Format: (source_path, target_key, transform_function)
    # source_path: dot-notation path in raw_analysis JSON
    # target_key: key in derived.* namespace
    # transform_function: optional transform to apply

    DERIVED_MAPPINGS: List[Tuple[str, str, Optional[str]]] = [
        # ----- Author info -----
        ("author_name", "author_name", None),
        ("author_biography", "author_biography", "format_multiline"),
        ("author_background", "author_biography", "format_multiline"),  # Fallback

        # ----- Work profile (top level in default schema) -----
        ("writing_style", "writing_style", None),
        ("tone", "tone", None),
        ("target_audience", "target_audience", None),
        ("genre_conventions", "genre_conventions", None),

        # ----- Work profile (nested in reformed-theology schema) -----
        ("work_profile.writing_style", "writing_style", None),
        ("work_profile.tone", "tone", None),
        ("work_profile.target_audience", "target_audience", None),
        ("work_profile.genre", "genre_conventions", None),

        # ----- Terminology -----
        ("key_terminology", "terminology_table", "format_terminology"),
        ("key_terminology", "key_terminology_raw", None),  # Raw dict for programmatic use

        # ----- Translation principles (nested in default schema) -----
        ("translation_principles.priority_order", "priority_order", "format_inline_list"),
        ("translation_principles.faithfulness_boundary", "faithfulness_boundary", None),
        ("translation_principles.permissible_adaptation", "permissible_adaptation", None),
        ("translation_principles.style_constraints", "style_constraints", None),
        ("translation_principles.red_lines", "red_lines", None),

        # ----- Translation principles (top level in some schemas) -----
        ("priority_order", "priority_order", "format_inline_list"),
        ("faithfulness_boundary", "faithfulness_boundary", None),
        ("permissible_adaptation", "permissible_adaptation", None),
        ("style_constraints", "style_constraints", None),
        ("red_lines", "red_lines", None),

        # ----- Custom guidelines -----
        ("custom_guidelines", "custom_guidelines", "format_bullet_list"),

        # ----- Meta section (reformed-theology schema) -----
        ("meta.author", "author_name", None),
        ("meta.book_title", "book_title", None),
        ("meta.assumed_tradition", "assumed_tradition", None),
        ("meta.target_chinese_bible_version", "bible_version", None),

        # ----- Author biography nested (reformed-theology schema) -----
        ("author_biography.theological_identity", "author_theological_identity", None),
        ("author_biography.historical_context", "author_historical_context", None),
        ("author_biography.influence_on_translation", "author_influence", None),

        # ----- Bible reference policy -----
        ("bible_reference_policy", "bible_reference_policy", "format_bible_policy"),

        # ----- Syntax and logic -----
        ("syntax_and_logic.sentence_splitting_rules", "sentence_splitting_rules", None),
        ("syntax_and_logic.logical_connectors", "logical_connectors", None),

        # ----- Notes policy -----
        ("notes_policy.allowed", "notes_allowed", "format_bullet_list"),
        ("notes_policy.forbidden", "notes_forbidden", "format_bullet_list"),

        # ----- Custom watchlist (alternate name for custom_guidelines) -----
        ("custom_watchlist", "custom_guidelines", "format_bullet_list"),
    ]

    # Placeholder values to filter out from terminology
    INVALID_PLACEHOLDERS = {"undefined", "null", "n/a", "none", "tbd", ""}

    # =========================================================================
    # Main Build Method
    # =========================================================================

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

        # 1. Load project variables from database
        project_vars = await cls._build_project_vars(db, input_data.project_id)
        variables.update(project_vars)

        # 2. Build content variables (stage-aware)
        content_vars = cls._build_content_vars(input_data)
        variables.update(content_vars)

        # 3. Build context variables (for translation coherence)
        context_vars = cls._build_context_vars(input_data)
        variables.update(context_vars)

        # 4. Build derived variables (from analysis) - SINGLE EXTRACTION LOGIC
        derived_vars = await cls._build_derived_vars(db, input_data.project_id)
        variables.update(derived_vars)

        # 5. Build meta variables (computed at runtime)
        meta_vars = cls._build_meta_vars(input_data)
        variables.update(meta_vars)

        # 6. Build pipeline variables
        pipeline_vars = cls._build_pipeline_vars(input_data)
        variables.update(pipeline_vars)

        # 7. Load user-defined variables from variables.json
        user_vars = await cls._load_user_vars(input_data.project_id)
        variables.update(user_vars)

        logger.debug(
            f"Built {len(variables)} variables for stage={input_data.stage}, "
            f"project_id={input_data.project_id}"
        )

        return variables

    # =========================================================================
    # Variable Building Methods
    # =========================================================================

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
            logger.warning(f"Project not found: {project_id}")
            return {
                "project.title": "",
                "project.author": "",
                "project.author_background": "",
                "project.name": "",
                "project.source_language": "en",
                "project.target_language": "zh",
                "project.total_chapters": 0,
                "project.total_paragraphs": 0,
            }

        return {
            "project.title": project.epub_title or project.name or "",
            "project.author": project.epub_author or "",
            "project.author_background": project.author_background or "",
            "project.name": project.name or "",
            "project.source_language": project.epub_language or "en",
            "project.target_language": "zh",  # TODO: Make configurable via project config
            "project.total_chapters": project.total_chapters or 0,
            "project.total_paragraphs": project.total_paragraphs or 0,
        }

    @classmethod
    def _build_content_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build content.* variables from input."""
        variables: Dict[str, Any] = {}

        # Source text (canonical + legacy aliases)
        if input_data.source_text:
            variables["content.source"] = input_data.source_text
            variables["content.source_text"] = input_data.source_text  # Legacy
            variables["content.original_text"] = input_data.source_text  # Legacy

        # Target text (canonical + legacy aliases)
        if input_data.target_text:
            variables["content.target"] = input_data.target_text
            variables["content.translated_text"] = input_data.target_text  # Legacy
            variables["content.existing_translation"] = input_data.target_text  # Legacy
            variables["content.current_translation"] = input_data.target_text  # Legacy

        # Chapter title
        if input_data.chapter_title:
            variables["content.chapter_title"] = input_data.chapter_title

        # Sample paragraphs (for analysis stage)
        if input_data.sample_paragraphs:
            variables["content.sample_paragraphs"] = input_data.sample_paragraphs

        return variables

    @classmethod
    def _build_context_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build context.* variables for translation coherence."""
        variables: Dict[str, Any] = {}

        # Previous paragraph context
        if input_data.previous_source:
            variables["context.previous_source"] = input_data.previous_source
            # Legacy aliases
            variables["context.previous_original"] = input_data.previous_source

        if input_data.previous_target:
            variables["context.previous_target"] = input_data.previous_target
            # Legacy aliases
            variables["context.previous_translation"] = input_data.previous_target

        # Next paragraph context (lookahead)
        if input_data.next_source:
            variables["context.next_source"] = input_data.next_source

        # Boolean flags for conditional rendering in templates
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
        All boolean flags are computed here to ensure consistency.
        """
        from app.models.database.book_analysis import BookAnalysis

        # Default empty state - ensures all variables are defined
        variables: Dict[str, Any] = {
            # Core derived values
            "derived.author_name": "",
            "derived.author_biography": "",
            "derived.book_title": "",
            "derived.writing_style": "",
            "derived.tone": "",
            "derived.target_audience": "",
            "derived.genre_conventions": "",
            "derived.terminology_table": "",
            "derived.key_terminology_raw": {},
            "derived.priority_order": "",
            "derived.faithfulness_boundary": "",
            "derived.permissible_adaptation": "",
            "derived.style_constraints": "",
            "derived.red_lines": "",
            "derived.custom_guidelines": "",
            # Extended fields (reformed-theology schema)
            "derived.assumed_tradition": "",
            "derived.bible_version": "",
            "derived.author_theological_identity": "",
            "derived.author_historical_context": "",
            "derived.author_influence": "",
            "derived.bible_reference_policy": "",
            "derived.sentence_splitting_rules": "",
            "derived.logical_connectors": "",
            "derived.notes_allowed": "",
            "derived.notes_forbidden": "",
            # Boolean flags - all default to False
            "derived.has_analysis": False,
            "derived.has_writing_style": False,
            "derived.has_tone": False,
            "derived.has_terminology": False,
            "derived.has_target_audience": False,
            "derived.has_genre_conventions": False,
            "derived.has_translation_principles": False,
            "derived.has_custom_guidelines": False,
            "derived.has_style_constraints": False,
            "derived.has_author_biography": False,
            "derived.has_bible_policy": False,
        }

        # Load analysis from database
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        analysis = result.scalar_one_or_none()

        if not analysis or not analysis.raw_analysis:
            logger.debug(f"No analysis found for project {project_id}")
            return variables

        raw = analysis.raw_analysis
        variables["derived.has_analysis"] = True

        # Extract values using mappings
        for source_path, target_key, transform in cls.DERIVED_MAPPINGS:
            value = cls._get_nested_value(raw, source_path)
            if value is not None:
                # Apply transform if specified
                if transform:
                    value = cls._apply_transform(value, transform)
                # Only set if we have a value (don't overwrite with empty)
                if value:
                    variables[f"derived.{target_key}"] = value

        # Compute boolean flags based on extracted values
        variables["derived.has_writing_style"] = bool(
            variables.get("derived.writing_style")
        )
        variables["derived.has_tone"] = bool(
            variables.get("derived.tone")
        )
        variables["derived.has_terminology"] = bool(
            variables.get("derived.terminology_table")
        )
        variables["derived.has_target_audience"] = bool(
            variables.get("derived.target_audience")
        )
        variables["derived.has_genre_conventions"] = bool(
            variables.get("derived.genre_conventions")
        )
        variables["derived.has_translation_principles"] = bool(
            variables.get("derived.priority_order")
            or variables.get("derived.faithfulness_boundary")
            or variables.get("derived.permissible_adaptation")
        )
        variables["derived.has_custom_guidelines"] = bool(
            variables.get("derived.custom_guidelines")
        )
        variables["derived.has_style_constraints"] = bool(
            variables.get("derived.style_constraints")
        )
        variables["derived.has_author_biography"] = bool(
            variables.get("derived.author_biography")
        )
        variables["derived.has_bible_policy"] = bool(
            variables.get("derived.bible_reference_policy")
        )

        logger.debug(
            f"Extracted derived variables: has_analysis=True, "
            f"has_writing_style={variables['derived.has_writing_style']}, "
            f"has_terminology={variables['derived.has_terminology']}"
        )

        return variables

    @classmethod
    def _build_meta_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build meta.* variables computed at runtime."""
        variables: Dict[str, Any] = {
            "meta.stage": input_data.stage,
        }

        # Word/character counts from source text
        if input_data.source_text:
            variables["meta.word_count"] = len(input_data.source_text.split())
            variables["meta.char_count"] = len(input_data.source_text)

        # Position information
        if input_data.paragraph_index is not None:
            variables["meta.paragraph_index"] = input_data.paragraph_index

        if input_data.chapter_index is not None:
            variables["meta.chapter_index"] = input_data.chapter_index

        # Totals (if provided)
        if input_data.total_paragraphs is not None:
            variables["meta.total_paragraphs"] = input_data.total_paragraphs

        if input_data.total_chapters is not None:
            variables["meta.total_chapters"] = input_data.total_chapters

        return variables

    @classmethod
    def _build_pipeline_vars(cls, input_data: VariableInput) -> Dict[str, Any]:
        """Build pipeline.* variables from previous processing steps."""
        variables: Dict[str, Any] = {}

        # Reference translation (from reference ePub matching)
        if input_data.reference_translation:
            variables["pipeline.reference_translation"] = input_data.reference_translation
            variables["pipeline.has_reference"] = True
        else:
            variables["pipeline.has_reference"] = False

        # Suggested changes (for optimization stage)
        if input_data.suggested_changes:
            variables["pipeline.suggested_changes"] = input_data.suggested_changes
            variables["pipeline.has_suggestions"] = True
        else:
            variables["pipeline.has_suggestions"] = False

        return variables

    @classmethod
    async def _load_user_vars(cls, project_id: str) -> Dict[str, Any]:
        """Load user-defined variables from project's variables.json."""
        from app.core.prompts.loader import PromptLoader

        try:
            user_vars = PromptLoader.load_project_variables(project_id)
            # Prefix with user. namespace (except macros which are handled separately)
            result = {}
            for k, v in user_vars.items():
                if k != "macros":
                    result[f"user.{k}"] = v
            return result
        except Exception as e:
            logger.debug(f"No user variables for project {project_id}: {e}")
            return {}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @classmethod
    def _get_nested_value(cls, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation.

        Args:
            data: Source dictionary
            path: Dot-separated path (e.g., "translation_principles.priority_order")

        Returns:
            Value at path, or None if not found
        """
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
        """Apply transform function to value.

        Supported transforms:
        - format_terminology: Convert terminology dict/list to markdown table
        - format_bullet_list: Convert list to bullet points
        - format_inline_list: Convert list to comma-separated inline
        - format_multiline: Convert structured value to readable text
        - format_bible_policy: Format bible reference policy object
        """
        if transform == "format_terminology":
            return cls._format_terminology(value)
        elif transform == "format_bullet_list":
            return cls._format_bullet_list(value)
        elif transform == "format_inline_list":
            return cls._format_inline_list(value)
        elif transform == "format_multiline":
            return cls._format_multiline(value)
        elif transform == "format_bible_policy":
            return cls._format_bible_policy(value)
        return value

    @classmethod
    def _format_terminology(cls, terms: Any) -> str:
        """Format terminology as markdown list.

        Handles both dict format and list-of-dicts format.
        Filters out invalid/placeholder values.
        """
        if isinstance(terms, dict):
            lines = []
            for en, zh in terms.items():
                if en and cls._is_valid_translation(zh):
                    lines.append(f"- **{en}**: {zh}")
            return "\n".join(lines)

        elif isinstance(terms, list):
            lines = []
            for term in terms:
                if isinstance(term, dict):
                    # Support multiple field name formats
                    en = (
                        term.get("english_term")
                        or term.get("english")
                        or term.get("term")
                        or ""
                    )
                    zh = (
                        term.get("chinese_translation")
                        or term.get("recommended_chinese")
                        or term.get("chinese")
                        or ""
                    )
                    usage = term.get("usage_rule") or term.get("notes") or ""
                    fallbacks = term.get("fallback_options", [])

                    if en and cls._is_valid_translation(zh):
                        line = f"- **{en}**: {zh}"
                        if fallbacks and isinstance(fallbacks, list):
                            fallback_str = ", ".join(str(f) for f in fallbacks[:2])
                            line += f" (alt: {fallback_str})"
                        if usage:
                            # Truncate long usage rules
                            usage_short = usage[:100] + "..." if len(usage) > 100 else usage
                            line += f"\n  - Usage: {usage_short}"
                        lines.append(line)
                elif term:
                    lines.append(f"- {term}")
            return "\n".join(lines)

        return str(terms) if terms else ""

    @classmethod
    def _is_valid_translation(cls, value: Any) -> bool:
        """Check if a translation value is valid (not a placeholder)."""
        if value is None:
            return False
        if not isinstance(value, str):
            return bool(value)
        return value.strip().lower() not in cls.INVALID_PLACEHOLDERS

    @classmethod
    def _format_bullet_list(cls, items: Any) -> str:
        """Format as bullet list."""
        if isinstance(items, list):
            return "\n".join(f"- {item}" for item in items if item)
        return str(items) if items else ""

    @classmethod
    def _format_inline_list(cls, items: Any) -> str:
        """Format as comma-separated inline list."""
        if isinstance(items, list):
            return ", ".join(str(item) for item in items if item)
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

    @classmethod
    def _format_bible_policy(cls, policy: Any) -> str:
        """Format bible_reference_policy object as readable string."""
        if isinstance(policy, str):
            return policy
        if not isinstance(policy, dict):
            return str(policy) if policy else ""

        parts = []

        # Detection rules
        detection = policy.get("detection", {})
        if detection:
            parts.append("**Detection Rules**:")
            if detection.get("explicit_markers"):
                markers = ", ".join(str(m) for m in detection["explicit_markers"][:3])
                parts.append(f"- Explicit markers: {markers}")
            if detection.get("implicit_signals"):
                signals = ", ".join(str(s) for s in detection["implicit_signals"][:3])
                parts.append(f"- Implicit signals: {signals}")

        # Rendering rules
        rendering = policy.get("rendering", {})
        if rendering:
            parts.append("\n**Rendering Rules**:")
            if rendering.get("in_text"):
                parts.append(f"- In text: {rendering['in_text']}")
            if rendering.get("citation_format"):
                parts.append(f"- Citation format: {rendering['citation_format']}")

        # Obligation
        obligation = policy.get("obligation", {})
        if obligation and obligation.get("burden_of_action"):
            parts.append(f"\n**Obligation**: {obligation['burden_of_action']}")

        return "\n".join(parts) if parts else ""


# =========================================================================
# Convenience Function
# =========================================================================

async def build_variables(
    db: AsyncSession,
    project_id: str,
    stage: StageType,
    **kwargs,
) -> Dict[str, Any]:
    """Convenience function to build variables.

    This is the recommended way to build variables in service code.

    Example:
        variables = await build_variables(
            db,
            project_id="abc123",
            stage="translation",
            source_text="Hello world",
            previous_source="Previous paragraph...",
            previous_target="Previous translation...",
        )
    """
    input_data = VariableInput(
        project_id=project_id,
        stage=stage,
        source_text=kwargs.get("source_text"),
        target_text=kwargs.get("target_text"),
        chapter_title=kwargs.get("chapter_title"),
        sample_paragraphs=kwargs.get("sample_paragraphs"),
        previous_source=kwargs.get("previous_source"),
        previous_target=kwargs.get("previous_target"),
        next_source=kwargs.get("next_source"),
        reference_translation=kwargs.get("reference_translation"),
        suggested_changes=kwargs.get("suggested_changes"),
        paragraph_index=kwargs.get("paragraph_index"),
        chapter_index=kwargs.get("chapter_index"),
        total_paragraphs=kwargs.get("total_paragraphs"),
        total_chapters=kwargs.get("total_chapters"),
    )
    return await UnifiedVariableBuilder.build(db, input_data)

