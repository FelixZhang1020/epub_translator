"""Translation Orchestrator - Manages the translation workflow using pipeline architecture."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

from app.models.database.base import async_session_maker
from app.models.database.project import Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.models.database.translation import Translation, TranslationTask, TaskStatus

from .models import TranslationMode
from .pipeline import (
    ContextBuilder,
    TranslationPipeline,
    PipelineConfig,
)


class TranslationOrchestrator:
    """Orchestrates the translation workflow for a project.

    Uses the pipeline architecture with:
    - ContextBuilder: For assembling translation context from database
    - TranslationPipeline: For executing translations with proper prompt engineering
    - Structured models: TranslationContext, PromptBundle, TranslationResult
    """

    def __init__(
        self,
        task_id: str,
        provider: str,
        model: str,
        api_key: str,
        resume: bool = False,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
        use_iterative: bool = False,
        temperature: Optional[float] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize the orchestrator.

        Args:
            task_id: Translation task ID
            provider: LLM provider name
            model: Model identifier
            api_key: API key for provider
            resume: Whether to resume from checkpoint
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt
            use_iterative: Whether to use iterative (2-step) translation
            temperature: LLM temperature override
            base_url: Custom API endpoint (for OpenRouter, Ollama, etc.)
        """
        self.task_id = task_id
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.base_url = base_url
        self.resume = resume
        self.custom_system_prompt = custom_system_prompt
        self.custom_user_prompt = custom_user_prompt
        self.use_iterative = use_iterative
        self._should_stop = False

        # Log configuration for debugging
        logger.info(f"[Orchestrator] Initialized: task_id={task_id}, provider={provider}, model={model}, temperature={temperature}, base_url={base_url}")

    async def run(self):
        """Run the translation task."""
        async with async_session_maker() as db:
            try:
                # Load and update task
                task = await self._load_task(db)
                task.status = TaskStatus.PROCESSING.value
                task.started_at = datetime.utcnow()
                await db.commit()

                # Load project with all relationships
                project = await self._load_project(db, task.project_id)

                # Determine translation mode
                mode = self._determine_mode(task.mode)

                # Create pipeline
                config = PipelineConfig(
                    provider=self.provider,
                    model=self.model,
                    api_key=self.api_key,
                    mode=mode,
                    temperature=self.temperature,
                    base_url=self.base_url,
                )
                pipeline = TranslationPipeline(config)

                # Create context builder
                context_builder = ContextBuilder(db)

                # Get chapters to process
                chapters = self._get_chapters_to_process(project, task)

                # Find resume point if needed
                start_chapter_idx, start_para_idx = await self._find_resume_point(
                    chapters, task
                )

                # Process paragraphs
                await self._process_chapters(
                    db=db,
                    task=task,
                    project=project,
                    chapters=chapters,
                    pipeline=pipeline,
                    context_builder=context_builder,
                    mode=mode,
                    start_chapter_idx=start_chapter_idx,
                    start_para_idx=start_para_idx,
                )

                # Mark task as completed
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.utcnow()
                task.progress = 1.0

                # Check if ALL chapters in project are translated
                # Only mark project as completed if every chapter has translations
                all_chapters_translated = await self._check_all_chapters_translated(db, project.id)

                if all_chapters_translated:
                    project.translation_completed = True
                    project.current_step = "proofreading"
                    logger.info(f"Project {project.id} translation fully completed")
                else:
                    logger.info(f"Project {project.id} task completed, but some chapters remain untranslated")

                await db.commit()

            except Exception as e:
                await self._handle_failure(db, str(e))
                raise

    async def _load_task(self, db: AsyncSession) -> TranslationTask:
        """Load the translation task from database."""
        result = await db.execute(
            select(TranslationTask).where(TranslationTask.id == self.task_id)
        )
        return result.scalar_one()

    async def _load_project(self, db: AsyncSession, project_id: str) -> Project:
        """Load project with all relationships."""
        result = await db.execute(
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.chapters)
                .selectinload(Chapter.paragraphs)
                .selectinload(Paragraph.translations),
                selectinload(Project.analysis),
            )
        )
        return result.scalar_one()

    def _determine_mode(self, mode_str: str) -> TranslationMode:
        """Convert mode string to TranslationMode enum."""
        mode_mapping = {
            "author_based": TranslationMode.AUTHOR_AWARE,
            "author_aware": TranslationMode.AUTHOR_AWARE,
            "optimization": TranslationMode.OPTIMIZATION,
            "direct": TranslationMode.DIRECT,
            "iterative": TranslationMode.ITERATIVE,
        }
        return mode_mapping.get(mode_str, TranslationMode.AUTHOR_AWARE)

    def _get_chapters_to_process(
        self, project: Project, task: TranslationTask
    ) -> list[Chapter]:
        """Get sorted and filtered list of chapters to process."""
        chapters = sorted(project.chapters, key=lambda c: c.chapter_number)

        if task.selected_chapters:
            chapters = [
                c for c in chapters if c.chapter_number in task.selected_chapters
            ]

        return chapters

    async def _find_resume_point(
        self, chapters: list[Chapter], task: TranslationTask
    ) -> tuple[int, int]:
        """Find the resume point if resuming a paused task."""
        if not self.resume or not task.current_paragraph_id:
            return 0, 0

        for i, chapter in enumerate(chapters):
            for j, para in enumerate(chapter.paragraphs):
                if para.id == task.current_paragraph_id:
                    return i, j

        return 0, 0

    async def _process_chapters(
        self,
        db: AsyncSession,
        task: TranslationTask,
        project: Project,
        chapters: list[Chapter],
        pipeline: TranslationPipeline,
        context_builder: ContextBuilder,
        mode: TranslationMode,
        start_chapter_idx: int,
        start_para_idx: int,
    ):
        """Process all chapters and paragraphs."""
        for chapter_idx, chapter in enumerate(
            chapters[start_chapter_idx:], start=start_chapter_idx
        ):
            # Check for pause/cancel
            if await self._should_stop_processing(db, task):
                return

            # Update current chapter
            task.current_chapter_id = chapter.id
            await db.commit()

            # Get sorted paragraphs
            paragraphs = sorted(chapter.paragraphs, key=lambda p: p.paragraph_number)

            # Determine start index for this chapter
            para_start = start_para_idx if chapter_idx == start_chapter_idx else 0

            for para in paragraphs[para_start:]:
                # Check for pause/cancel
                if await self._should_stop_processing(db, task):
                    return

                # Skip if already translated (for resume)
                if self.resume and para.latest_translation:
                    continue

                # Skip confirmed translations - they should never be changed
                if para.latest_translation and para.latest_translation.is_confirmed:
                    logger.info(f"[Orchestrator] Skipping confirmed translation for paragraph {para.id}")
                    task.completed_paragraphs += 1
                    task.progress = task.completed_paragraphs / task.total_paragraphs
                    await db.commit()
                    continue

                # Translate paragraph
                await self._translate_paragraph(
                    db=db,
                    task=task,
                    project=project,
                    paragraph=para,
                    pipeline=pipeline,
                    context_builder=context_builder,
                    mode=mode,
                )

                # Add configurable delay between requests to avoid overloading API
                await asyncio.sleep(settings.translation_throttle_delay)

    async def _should_stop_processing(
        self, db: AsyncSession, task: TranslationTask
    ) -> bool:
        """Check if processing should stop (pause/cancel)."""
        result = await db.execute(
            select(TranslationTask).where(TranslationTask.id == self.task_id)
        )
        current_task = result.scalar_one()
        return current_task.status in [
            TaskStatus.PAUSED.value,
            TaskStatus.FAILED.value,
        ]

    @retry(
        stop=stop_after_attempt(5),  # Increase retry attempts for 503 errors
        wait=wait_exponential(multiplier=2, min=4, max=60),  # Longer waits for overloaded servers
        reraise=True,
    )
    async def _translate_paragraph(
        self,
        db: AsyncSession,
        task: TranslationTask,
        project: Project,
        paragraph: Paragraph,
        pipeline: TranslationPipeline,
        context_builder: ContextBuilder,
        mode: TranslationMode,
    ):
        """Translate a single paragraph with retry logic."""
        try:
            # Build context
            context = await context_builder.build(
                paragraph=paragraph,
                project=project,
                mode=mode,
                include_adjacent=True,
                custom_system_prompt=self.custom_system_prompt,
                custom_user_prompt=self.custom_user_prompt,
            )

            # Execute translation
            if self.use_iterative:
                result = await pipeline.translate_iterative(context)
            else:
                result = await pipeline.translate(context)

            # Save translation
            translation = Translation(
                paragraph_id=paragraph.id,
                translated_text=result.translated_text,
                mode=mode.value,
                provider=result.provider,
                model=result.model,
                tokens_used=result.tokens_used,
            )
            db.add(translation)

            # Update progress
            task.completed_paragraphs += 1
            task.current_paragraph_id = paragraph.id
            task.update_progress()
            await db.commit()

        except Exception as e:
            error_msg = str(e)
            task.error_message = error_msg
            task.retry_count += 1
            await db.commit()

            logger.error(f"[Orchestrator] Translation error for paragraph {paragraph.id}: {error_msg}, retry_count={task.retry_count}")

            if task.retry_count >= 5:
                task.status = TaskStatus.FAILED.value
                await db.commit()
                logger.error(f"[Orchestrator] Task {self.task_id} failed after 5 retries")

            raise

    async def _check_all_chapters_translated(
        self, db: AsyncSession, project_id: str
    ) -> bool:
        """Check if all chapters in the project have at least one translation.

        Args:
            db: Database session
            project_id: Project ID

        Returns:
            True if all chapters have translations, False otherwise
        """
        # Count total chapters
        result = await db.execute(
            select(func.count(Chapter.id)).where(Chapter.project_id == project_id)
        )
        total_chapters = result.scalar() or 0

        if total_chapters == 0:
            return False

        # Count chapters with at least one translated paragraph
        result = await db.execute(
            select(func.count(func.distinct(Paragraph.chapter_id)))
            .select_from(Paragraph)
            .join(Chapter)
            .join(Translation, Translation.paragraph_id == Paragraph.id)
            .where(Chapter.project_id == project_id)
        )
        chapters_with_translations = result.scalar() or 0

        logger.info(
            f"Project {project_id}: {chapters_with_translations}/{total_chapters} chapters translated"
        )

        return chapters_with_translations == total_chapters

    async def _handle_failure(self, db: AsyncSession, error_message: str):
        """Handle task failure."""
        result = await db.execute(
            select(TranslationTask).where(TranslationTask.id == self.task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = error_message
            await db.commit()
