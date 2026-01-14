"""Context builder for translation pipeline.

This module provides the ContextBuilder class that constructs
TranslationContext objects from database entities.
"""

from typing import Optional, Dict, Any
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.context import (
    AdjacentContext,
    BookAnalysisContext,
    ExistingTranslation,
    SourceMaterial,
    TranslationContext,
    TranslationMode,
    ProjectMetadata,
)
from app.core.prompts.loader import PromptLoader

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds TranslationContext from database entities.

    This class is responsible for assembling all the context needed
    for translation from database models, including:
    - Source paragraph text
    - Book analysis data
    - Adjacent paragraphs for coherence
    - Existing translations for optimization mode
    """

    def __init__(self, session: AsyncSession):
        """Initialize context builder.

        Args:
            session: Async database session
        """
        self.session = session

    async def build(
        self,
        paragraph,  # Paragraph model
        project,  # Project model
        mode: TranslationMode,
        *,
        include_adjacent: bool = True,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> TranslationContext:
        """Build complete translation context for a paragraph.

        Args:
            paragraph: Paragraph database model
            project: Project database model (should have analysis loaded)
            mode: Translation mode to use
            include_adjacent: Whether to include adjacent paragraph context
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt

        Returns:
            Complete TranslationContext ready for pipeline

        Raises:
            ValueError: If paragraph.original_text is None or cannot be recovered
        """
        source_text = await self._validate_and_get_source_text(paragraph)

        # 1. Build source material
        source = SourceMaterial(
            text=source_text,
            language="en",
            paragraph_index=paragraph.paragraph_number,
            chapter_index=(
                paragraph.chapter.chapter_number
                if hasattr(paragraph, "chapter") and paragraph.chapter
                else None
            ),
        )

        # 2. Build book analysis context
        book_analysis = None
        if project.analysis and project.analysis.raw_analysis:
            book_analysis = BookAnalysisContext.from_raw_analysis(
                project.analysis.raw_analysis
            )

        # 3. Build adjacent context if requested
        adjacent = None
        if include_adjacent:
            adjacent = await self._build_adjacent_context(paragraph)

        # 4. Get existing translation for optimization mode
        existing = None
        if mode == TranslationMode.OPTIMIZATION:
            existing = await self._get_existing_translation(paragraph)

        # 5. Load prompts from file system if custom prompts not provided
        if not custom_system_prompt or not custom_user_prompt:
            loaded_system, loaded_user = await self._load_prompts_from_files(
                project=project,
                mode=mode,
                paragraph=paragraph,
                book_analysis=book_analysis,
                adjacent=adjacent,
                existing=existing,
            )
            # Use loaded prompts if custom ones not provided
            if not custom_system_prompt:
                custom_system_prompt = loaded_system
            if not custom_user_prompt:
                custom_user_prompt = loaded_user

        # 6. Assemble final context
        return TranslationContext(
            source=source,
            target_language="zh",
            mode=mode,
            book_analysis=book_analysis,
            adjacent=adjacent,
            existing=existing,
            project=ProjectMetadata(
                title=getattr(project, "title", None) or getattr(project, "epub_title", "") or "",
                author=getattr(project, "author", None) or getattr(project, "epub_author", "") or "",
                source_language=getattr(project, "source_language", "en"),
                target_language=getattr(project, "target_language", "zh"),
                author_background=getattr(project, "author_background", None),
            ),
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

    async def build_from_text(
        self,
        source_text: str,
        mode: TranslationMode,
        *,
        book_analysis_dict: Optional[dict] = None,
        previous_text: Optional[str] = None,
        previous_translation: Optional[str] = None,
        existing_translation: Optional[str] = None,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> TranslationContext:
        """Build context from raw text (without database models).

        Useful for ad-hoc translations or testing.

        Args:
            source_text: Text to translate
            mode: Translation mode
            book_analysis_dict: Optional analysis data as dict
            previous_text: Previous paragraph for context
            previous_translation: Translation of previous paragraph
            existing_translation: Existing translation for optimization
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt

        Returns:
            TranslationContext for the text
        """
        # Build source
        source = SourceMaterial(text=source_text, language="en")

        # Build book analysis if provided
        book_analysis = None
        if book_analysis_dict:
            book_analysis = BookAnalysisContext.from_raw_analysis(book_analysis_dict)

        # Build adjacent context
        adjacent = None
        if previous_text:
            adjacent = AdjacentContext(
                previous_original=previous_text,
                previous_translation=previous_translation,
            )

        # Build existing translation
        existing = None
        if existing_translation and mode == TranslationMode.OPTIMIZATION:
            existing = ExistingTranslation(text=existing_translation)

        return TranslationContext(
            source=source,
            target_language="zh",
            mode=mode,
            book_analysis=book_analysis,
            adjacent=adjacent,
            existing=existing,
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

    async def _build_adjacent_context(self, paragraph) -> Optional[AdjacentContext]:
        """Get surrounding paragraphs for context.

        Args:
            paragraph: Current paragraph model

        Returns:
            AdjacentContext with previous paragraph info, or None
        """
        # Import here to avoid circular imports
        from app.models.database import Paragraph

        # Get previous paragraph in same chapter
        prev_para_query = (
            select(Paragraph)
            .where(Paragraph.chapter_id == paragraph.chapter_id)
            .where(Paragraph.paragraph_number == paragraph.paragraph_number - 1)
            .options(selectinload(Paragraph.translations))
        )

        result = await self.session.execute(prev_para_query)
        prev_paragraph = result.scalar_one_or_none()

        if not prev_paragraph:
            return None

        # Get latest translation of previous paragraph
        prev_translation = None
        if prev_paragraph.translations:
            # Get the most recent translation
            sorted_translations = sorted(
                prev_paragraph.translations,
                key=lambda t: t.version,
                reverse=True,
            )
            if sorted_translations:
                prev_translation = sorted_translations[0].translated_text

        return AdjacentContext(
            previous_original=prev_paragraph.original_text,
            previous_translation=prev_translation,
        )

    async def _get_existing_translation(
        self, paragraph
    ) -> Optional[ExistingTranslation]:
        """Get latest translation for optimization mode.

        Args:
            paragraph: Paragraph model

        Returns:
            ExistingTranslation if available, None otherwise
        """
        # Check if paragraph has translations relationship loaded
        if hasattr(paragraph, "translations") and paragraph.translations:
            # Get the most recent translation
            sorted_translations = sorted(
                paragraph.translations,
                key=lambda t: t.version,
                reverse=True,
            )
            if sorted_translations:
                t = sorted_translations[0]
                return ExistingTranslation(
                    text=t.translated_text,
                    provider=t.provider,
                    model=t.model,
                    version=t.version,
                )

        # If not loaded, query for it
        from app.models.database import Translation

        query = (
            select(Translation)
            .where(Translation.paragraph_id == paragraph.id)
            .order_by(Translation.version.desc())
            .limit(1)
        )

        result = await self.session.execute(query)
        translation = result.scalar_one_or_none()

        if translation:
            return ExistingTranslation(
                text=translation.translated_text,
                provider=translation.provider,
                model=translation.model,
                version=translation.version,
            )

        return None

    async def _validate_and_get_source_text(self, paragraph) -> str:
        """Validate paragraph has source text, attempting recovery if needed.

        Args:
            paragraph: Paragraph model to validate

        Returns:
            The validated source text

        Raises:
            ValueError: If source text is None and cannot be recovered
        """
        paragraph_id = getattr(paragraph, "id", "unknown")
        paragraph_num = getattr(paragraph, "paragraph_number", "unknown")
        source_text = getattr(paragraph, "original_text", None)

        if source_text is None:
            logger.warning(
                f"paragraph.original_text is None for paragraph_id={paragraph_id}, "
                f"paragraph_number={paragraph_num}, attempting database refresh"
            )
            try:
                await self.session.refresh(paragraph, ["original_text"])
                source_text = paragraph.original_text
                if source_text is not None:
                    logger.info(
                        f"Successfully refreshed paragraph {paragraph_id}, "
                        f"original_text length={len(source_text)}"
                    )
            except Exception as e:
                logger.error(f"Failed to refresh paragraph {paragraph_id}: {e}")

        if source_text is None:
            raise ValueError(
                f"Source text is None for paragraph {paragraph_id}. "
                "Cannot build translation context without source text."
            )

        if not source_text.strip():
            logger.warning(f"Source text is empty for paragraph_id={paragraph_id}")

        logger.debug(
            f"Building context for paragraph_id={paragraph_id}, "
            f"source_text_len={len(source_text)}"
        )

        return source_text

    async def _load_prompts_from_files(
        self,
        project,
        mode: TranslationMode,
        paragraph,
        book_analysis: Optional[BookAnalysisContext],
        adjacent: Optional[AdjacentContext],
        existing: Optional[ExistingTranslation],
    ) -> tuple[str, str]:
        """Load and render prompts from file system templates.

        Args:
            project: Project model
            mode: Translation mode
            paragraph: Paragraph model
            book_analysis: Book analysis context
            adjacent: Adjacent context
            existing: Existing translation

        Returns:
            Tuple of (rendered_system_prompt, rendered_user_prompt)
        """
        # Map mode to prompt type
        prompt_type_map = {
            TranslationMode.DIRECT: "translation",
            TranslationMode.AUTHOR_AWARE: "translation",
            TranslationMode.OPTIMIZATION: "optimization",
        }
        prompt_type = prompt_type_map.get(mode, "translation")

        try:
            # Load template from project configuration
            template = PromptLoader.load_for_project(project.id, prompt_type)

            # Build variables dictionary for template rendering
            variables = self._build_template_variables(
                project=project,
                paragraph=paragraph,
                book_analysis=book_analysis,
                adjacent=adjacent,
                existing=existing,
                prompt_type=prompt_type,
            )

            # Render templates with variables
            rendered_system = PromptLoader.render(
                template.system_prompt,
                variables
            )
            rendered_user = PromptLoader.render(
                template.user_prompt_template,
                variables
            )

            logger.info(
                f"Loaded prompts from files for project {project.id}, "
                f"type={prompt_type}, template={template.template_name}"
            )

            return rendered_system, rendered_user

        except Exception as e:
            logger.warning(
                f"Failed to load prompts from files for project {project.id}: {e}. "
                f"Falling back to empty prompts (strategy will use defaults)."
            )
            # Return empty strings to let strategy use its built-in prompts
            return "", ""

    def _build_template_variables(
        self,
        project,
        paragraph,
        book_analysis: Optional[BookAnalysisContext],
        adjacent: Optional[AdjacentContext],
        existing: Optional[ExistingTranslation],
        prompt_type: str,
    ) -> Dict[str, Any]:
        """Build variables dictionary for template rendering.

        Note: This method assumes paragraph.original_text has been validated
        by the caller (build() method). It will not re-validate.

        Args:
            project: Project model
            paragraph: Paragraph model (must have validated original_text)
            book_analysis: Book analysis context
            adjacent: Adjacent context
            existing: Existing translation
            prompt_type: Type of prompt (translation/optimization/etc)

        Returns:
            Dictionary with all template variables
        """
        source_text = paragraph.original_text

        # Project variables
        variables: Dict[str, Any] = {
            "project": {
                "title": getattr(project, "title", None) or getattr(project, "epub_title", ""),
                "author": getattr(project, "author", None) or getattr(project, "epub_author", ""),
                "author_background": getattr(project, "author_background", ""),
                "source_language": getattr(project, "source_language", "en"),
                "target_language": getattr(project, "target_language", "zh"),
            }
        }

        # Content variables
        variables["content"] = {
            "source": source_text,
            "source_text": source_text,  # legacy alias
        }

        # Add target for optimization/proofreading
        if existing:
            variables["content"]["target"] = existing.text
            variables["content"]["translated_text"] = existing.text  # legacy alias

        # Add chapter title if available
        if hasattr(paragraph, "chapter") and paragraph.chapter:
            variables["content"]["chapter_title"] = getattr(
                paragraph.chapter, "title", ""
            )

        # Context variables (adjacent paragraphs)
        if adjacent:
            variables["context"] = {
                "previous_source": adjacent.previous_original or "",
                "previous_target": adjacent.previous_translation or "",
            }

        # Pipeline variables
        variables["pipeline"] = {}
        # Add existing translation under pipeline namespace too (legacy)
        if existing:
            variables["pipeline"]["existing_translation"] = existing.text

        # Derived variables (from book analysis)
        if book_analysis:
            derived: Dict[str, Any] = {
                "author_name": book_analysis.author_name,
                "author_biography": book_analysis.author_biography,
                "writing_style": book_analysis.writing_style,
                "tone": book_analysis.tone,
                "target_audience": book_analysis.target_audience,
                "genre_conventions": book_analysis.genre_conventions,
            }

            # Format terminology as table, filtering out invalid translations
            if book_analysis.key_terminology:
                # Placeholder values to filter out
                invalid_placeholders = {"undefined", "null", "n/a", "none", "tbd", ""}
                term_lines = [
                    f"- {en}: {zh}"
                    for en, zh in book_analysis.key_terminology.items()
                    if zh and str(zh).strip().lower() not in invalid_placeholders
                ]
                derived["terminology_table"] = "\n".join(term_lines)

            # Translation principles
            if book_analysis.translation_principles:
                tp = book_analysis.translation_principles
                derived["priority_order"] = tp.priority_order or []
                derived["faithfulness_boundary"] = tp.faithfulness_boundary or ""
                derived["permissible_adaptation"] = tp.permissible_adaptation or ""
                derived["red_lines"] = tp.red_lines or ""
                derived["style_constraints"] = tp.style_constraints or ""

            # Custom guidelines
            if book_analysis.custom_guidelines:
                derived["custom_guidelines"] = book_analysis.custom_guidelines

            # Boolean flags for conditionals
            derived["has_analysis"] = True
            derived["has_writing_style"] = bool(book_analysis.writing_style)
            derived["has_tone"] = bool(book_analysis.tone)
            derived["has_terminology"] = bool(book_analysis.key_terminology)
            derived["has_target_audience"] = bool(book_analysis.target_audience)
            derived["has_genre_conventions"] = bool(book_analysis.genre_conventions)
            derived["has_translation_principles"] = bool(book_analysis.translation_principles)
            derived["has_custom_guidelines"] = bool(book_analysis.custom_guidelines)
            derived["has_style_constraints"] = bool(
                book_analysis.translation_principles
                and book_analysis.translation_principles.style_constraints
            )

            variables["derived"] = derived

        # Meta variables
        variables["meta"] = {
            "word_count": len(source_text.split()),
            "char_count": len(source_text),
            "paragraph_index": getattr(paragraph, "paragraph_number", 0),
            "stage": prompt_type,
        }
        if hasattr(paragraph, "chapter") and paragraph.chapter:
            variables["meta"]["chapter_index"] = paragraph.chapter.chapter_number

        # User-defined variables (load from project variables.json)
        try:
            user_vars = PromptLoader.load_project_variables(project.id)
            if user_vars:
                variables["user"] = user_vars
        except Exception as e:
            logger.debug(f"No user variables for project {project.id}: {e}")
            variables["user"] = {}

        return variables
