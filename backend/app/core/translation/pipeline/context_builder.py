"""Context builder for translation pipeline.

This module provides the ContextBuilder class that constructs
TranslationContext objects from database entities.
"""

from typing import Optional

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
)


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
        """
        # 1. Build source material
        source = SourceMaterial(
            text=paragraph.original_text,
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

        # 5. Assemble final context
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
        from app.models.database import Paragraph, Translation

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
