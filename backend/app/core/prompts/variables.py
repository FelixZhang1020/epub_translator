"""Variable management for prompt templates.

This module provides a centralized variable context builder that aggregates:
- Project variables (book title, author, etc.)
- Content variables (source text, paragraph index, etc.)
- Pipeline variables (analysis result, reference matching, etc.)
- Derived variables (extracted from analysis: writing_style, tone, etc.)
- User-defined variables (custom key-value pairs)
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.project import Project
from app.models.database.book_analysis import BookAnalysis
from app.models.database.prompt_template import ProjectVariable


class VariableContext:
    """Complete variable context for prompt rendering."""

    def __init__(self):
        """Initialize empty variable context."""
        self.project: Dict[str, Any] = {}
        self.content: Dict[str, Any] = {}
        self.pipeline: Dict[str, Any] = {}
        self.derived: Dict[str, Any] = {}
        self.user: Dict[str, Any] = {}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to a flat dictionary with namespaced keys.

        Returns:
            Dictionary with keys like 'project.title', 'derived.writing_style', etc.
        """
        result: Dict[str, Any] = {}

        for key, value in self.project.items():
            result[f"project.{key}"] = value

        for key, value in self.content.items():
            result[f"content.{key}"] = value

        for key, value in self.pipeline.items():
            result[f"pipeline.{key}"] = value

        for key, value in self.derived.items():
            result[f"derived.{key}"] = value

        for key, value in self.user.items():
            result[f"user.{key}"] = value

        return result

    def to_nested_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert to nested dictionary structure.

        Returns:
            Dictionary with namespaces as top-level keys.
        """
        return {
            "project": self.project,
            "content": self.content,
            "pipeline": self.pipeline,
            "derived": self.derived,
            "user": self.user,
        }


class VariableService:
    """Service for building and managing variable contexts."""

    # Fields to extract from analysis as derived variables
    DERIVED_FIELDS = [
        "author_biography",
        "writing_style",
        "tone",
        "target_audience",
        "genre_conventions",
        "key_terminology",
        "translation_principles",
    ]

    @classmethod
    async def build_context(
        cls,
        db: AsyncSession,
        project_id: str,
        source_text: Optional[str] = None,
        paragraph_index: Optional[int] = None,
        chapter_index: Optional[int] = None,
        existing_translation: Optional[str] = None,
        reference_translation: Optional[str] = None,
        previous_original: Optional[str] = None,
        previous_translation: Optional[str] = None,
    ) -> VariableContext:
        """Build a complete variable context for prompt rendering.

        Args:
            db: Database session
            project_id: Project ID
            source_text: Source text to translate
            paragraph_index: Current paragraph index
            chapter_index: Current chapter index
            existing_translation: Existing translation (for optimization mode)
            reference_translation: Reference translation if available
            previous_original: Previous paragraph in source language
            previous_translation: Previous paragraph translation

        Returns:
            Complete VariableContext instance
        """
        context = VariableContext()

        # Load project data
        project = await cls._load_project(db, project_id)
        if project:
            context.project = cls._extract_project_vars(project)

        # Load analysis and extract derived variables
        analysis = await cls._load_analysis(db, project_id)
        if analysis and analysis.raw_analysis:
            context.derived = cls._extract_derived_vars(analysis.raw_analysis)

        # Load user-defined variables
        user_vars = await cls._load_user_variables(db, project_id)
        context.user = user_vars

        # Set content variables
        if source_text:
            context.content["source_text"] = source_text
            context.content["word_count"] = len(source_text.split())
        if paragraph_index is not None:
            context.content["paragraph_index"] = paragraph_index
        if chapter_index is not None:
            context.content["chapter_index"] = chapter_index

        # Set pipeline variables
        if existing_translation:
            context.pipeline["existing_translation"] = existing_translation
        if reference_translation:
            context.pipeline["reference_translation"] = reference_translation
        if previous_original:
            context.pipeline["previous_original"] = previous_original
        if previous_translation:
            context.pipeline["previous_translation"] = previous_translation

        return context

    @classmethod
    async def _load_project(
        cls, db: AsyncSession, project_id: str
    ) -> Optional[Project]:
        """Load project from database."""
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def _load_analysis(
        cls, db: AsyncSession, project_id: str
    ) -> Optional[BookAnalysis]:
        """Load book analysis from database."""
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def _load_user_variables(
        cls, db: AsyncSession, project_id: str
    ) -> Dict[str, Any]:
        """Load user-defined variables from database.

        Returns:
            Dictionary mapping variable names to their values.
        """
        result = await db.execute(
            select(ProjectVariable).where(ProjectVariable.project_id == project_id)
        )
        variables = result.scalars().all()

        user_vars: Dict[str, Any] = {}
        for var in variables:
            # Parse value based on type
            value = cls._parse_variable_value(var.value, var.value_type)
            user_vars[var.name] = value

        return user_vars

    @classmethod
    def _extract_project_vars(cls, project: Project) -> Dict[str, Any]:
        """Extract project-level variables.

        Args:
            project: Project database model

        Returns:
            Dictionary with project variables
        """
        return {
            "title": project.epub_title or project.name or "",
            "author": project.epub_author or "",
            "name": project.name or "",
            "source_language": project.epub_language or "en",
            "target_language": "zh",  # Currently hardcoded
            "total_chapters": project.total_chapters or 0,
            "total_paragraphs": project.total_paragraphs or 0,
        }

    @classmethod
    def _extract_derived_vars(cls, raw_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract derived variables from analysis result.

        Args:
            raw_analysis: Raw analysis dictionary from BookAnalysis.raw_analysis

        Returns:
            Dictionary with derived variables
        """
        derived: Dict[str, Any] = {}

        # Direct field extractions
        for field in cls.DERIVED_FIELDS:
            if field in raw_analysis:
                derived[field] = raw_analysis[field]

        # Format terminology as a table string for direct insertion
        if "key_terminology" in raw_analysis and raw_analysis["key_terminology"]:
            terms = raw_analysis["key_terminology"]
            if isinstance(terms, dict):
                term_lines = [f"- {en}: {zh}" for en, zh in terms.items()]
                derived["terminology_table"] = "\n".join(term_lines)
            elif isinstance(terms, list):
                # Handle if it's a list of dicts with 'english' and 'chinese' keys
                term_lines = []
                for term in terms:
                    if isinstance(term, dict):
                        en = term.get("english_term") or term.get("english", "")
                        zh = term.get("chinese_translation") or term.get("chinese", "")
                        if en and zh:
                            term_lines.append(f"- {en}: {zh}")
                derived["terminology_table"] = "\n".join(term_lines)

        # Format translation principles
        if "translation_principles" in raw_analysis and raw_analysis["translation_principles"]:
            tp = raw_analysis["translation_principles"]
            if isinstance(tp, dict):
                derived["priority_order"] = tp.get("priority_order", [])
                derived["faithfulness_boundary"] = tp.get("faithfulness_boundary", "")
                derived["permissible_adaptation"] = tp.get("permissible_adaptation", "")
                derived["style_constraints"] = tp.get("style_constraints", "")
                derived["red_lines"] = tp.get("red_lines", "")

        # Add has_* flags for conditional blocks
        derived["has_analysis"] = bool(raw_analysis)
        derived["has_writing_style"] = bool(derived.get("writing_style"))
        derived["has_tone"] = bool(derived.get("tone"))
        derived["has_terminology"] = bool(derived.get("key_terminology"))

        return derived

    @classmethod
    def _parse_variable_value(cls, value: str, value_type: str) -> Any:
        """Parse variable value based on its type.

        Args:
            value: String value from database
            value_type: Type of the variable

        Returns:
            Parsed value of appropriate type
        """
        if value_type == "number":
            try:
                return float(value) if "." in value else int(value)
            except (ValueError, TypeError):
                return 0
        elif value_type == "boolean":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            import json
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            return value

    @classmethod
    async def get_available_variables(
        cls,
        db: AsyncSession,
        project_id: str,
        stage: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get list of available variables for a project.

        Args:
            db: Database session
            project_id: Project ID
            stage: Optional stage filter (analysis, translation, etc.)

        Returns:
            Dictionary with variable categories and their variables
        """
        # Build context to get actual values
        context = await cls.build_context(db, project_id)

        result: Dict[str, List[Dict[str, Any]]] = {
            "project": [],
            "content": [],
            "pipeline": [],
            "derived": [],
            "user": [],
        }

        # Project variables (always available)
        for key, value in context.project.items():
            result["project"].append({
                "name": f"project.{key}",
                "description": f"Project {key}",
                "current_value": value,
                "type": "string" if isinstance(value, str) else "number",
            })

        # Content variables (depend on stage)
        content_vars = [
            ("source_text", "Source text to translate", ["translation", "optimization"]),
            ("word_count", "Word count of source text", ["translation", "optimization"]),
            ("paragraph_index", "Current paragraph index", ["translation", "proofreading"]),
            ("chapter_index", "Current chapter index", ["translation", "proofreading"]),
        ]
        for name, desc, stages in content_vars:
            if stage is None or stage in stages:
                result["content"].append({
                    "name": f"content.{name}",
                    "description": desc,
                    "current_value": context.content.get(name),
                    "stages": stages,
                })

        # Pipeline variables
        pipeline_vars = [
            ("existing_translation", "Existing translation for optimization", ["optimization"]),
            ("reference_translation", "Matched reference translation", ["translation"]),
            ("previous_original", "Previous paragraph source text", ["translation"]),
            ("previous_translation", "Previous paragraph translation", ["translation"]),
        ]
        for name, desc, stages in pipeline_vars:
            if stage is None or stage in stages:
                result["pipeline"].append({
                    "name": f"pipeline.{name}",
                    "description": desc,
                    "current_value": context.pipeline.get(name),
                    "stages": stages,
                })

        # Derived variables
        for key, value in context.derived.items():
            result["derived"].append({
                "name": f"derived.{key}",
                "description": f"Derived from analysis: {key}",
                "current_value": value if not isinstance(value, (dict, list)) else str(value)[:100],
                "type": "object" if isinstance(value, (dict, list)) else "string",
            })

        # User variables
        for key, value in context.user.items():
            result["user"].append({
                "name": f"user.{key}",
                "description": "User-defined variable",
                "current_value": value if not isinstance(value, (dict, list)) else str(value)[:100],
                "editable": True,
            })

        return result
