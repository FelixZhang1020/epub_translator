"""Translation Orchestrator - Manages the translation workflow."""

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.database.base import async_session_maker
from app.models.database.project import Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.models.database.translation import Translation, TranslationTask, TaskStatus
from app.models.database.book_analysis import BookAnalysis
from app.core.llm.adapter import TranslationRequest
from app.core.llm.providers.factory import LLMProviderFactory
from app.core.prompts.variables import VariableService


class TranslationOrchestrator:
    """Orchestrates the translation process for a project."""

    def __init__(
        self,
        task_id: str,
        provider: str,
        model: str,
        api_key: str,
        resume: bool = False,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ):
        self.task_id = task_id
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.resume = resume
        self.custom_system_prompt = custom_system_prompt
        self.custom_user_prompt = custom_user_prompt
        self._should_stop = False

    async def run(self):
        """Run the translation task."""
        async with async_session_maker() as db:
            try:
                # Load task
                result = await db.execute(
                    select(TranslationTask).where(TranslationTask.id == self.task_id)
                )
                task = result.scalar_one()

                # Update status
                task.status = TaskStatus.PROCESSING.value
                task.started_at = datetime.utcnow()
                await db.commit()

                # Load project with chapters, paragraphs, and analysis
                result = await db.execute(
                    select(Project)
                    .where(Project.id == task.project_id)
                    .options(
                        selectinload(Project.chapters)
                        .selectinload(Chapter.paragraphs)
                        .selectinload(Paragraph.translations),
                        selectinload(Project.analysis)
                    )
                )
                project = result.scalar_one()

                # Extract analysis text if available
                # Convert raw_analysis dict to formatted text for prompt injection
                analysis_text = None
                if project.analysis and project.analysis.raw_analysis:
                    import json
                    analysis_text = json.dumps(
                        project.analysis.raw_analysis,
                        ensure_ascii=False,
                        indent=2
                    )

                # Build variable context using VariableService
                # This includes project vars, derived vars from analysis, and user-defined vars
                variable_context = await VariableService.build_context(
                    db=db,
                    project_id=task.project_id,
                )
                # Convert to flat dict for prompt rendering
                variable_context_dict = variable_context.to_flat_dict()

                # Create LLM adapter
                adapter = LLMProviderFactory.create(
                    provider=self.provider,
                    model=self.model,
                    api_key=self.api_key,
                )

                # Build author context
                author_context = task.author_context or {}

                # Process chapters
                chapters = sorted(project.chapters, key=lambda c: c.chapter_number)

                # Filter chapters if specified
                if task.selected_chapters:
                    chapters = [c for c in chapters if c.chapter_number in task.selected_chapters]

                # Find resume point if resuming
                start_chapter_idx = 0
                start_para_idx = 0
                if self.resume and task.current_paragraph_id:
                    for i, chapter in enumerate(chapters):
                        for j, para in enumerate(chapter.paragraphs):
                            if para.id == task.current_paragraph_id:
                                start_chapter_idx = i
                                start_para_idx = j
                                break

                # Process paragraphs
                for chapter_idx, chapter in enumerate(chapters[start_chapter_idx:], start=start_chapter_idx):
                    # Check for pause/cancel
                    result = await db.execute(
                        select(TranslationTask).where(TranslationTask.id == self.task_id)
                    )
                    task = result.scalar_one()

                    if task.status in [TaskStatus.PAUSED.value, TaskStatus.FAILED.value]:
                        return

                    task.current_chapter_id = chapter.id
                    await db.commit()

                    paragraphs = sorted(chapter.paragraphs, key=lambda p: p.paragraph_number)

                    # Determine start index for this chapter
                    para_start = start_para_idx if chapter_idx == start_chapter_idx else 0

                    prev_para = None
                    prev_translation = None
                    for para_idx, para in enumerate(paragraphs[para_start:], start=para_start):
                        # Check for pause/cancel
                        result = await db.execute(
                            select(TranslationTask).where(TranslationTask.id == self.task_id)
                        )
                        task = result.scalar_one()

                        if task.status in [TaskStatus.PAUSED.value, TaskStatus.FAILED.value]:
                            return

                        # Skip if already translated (for resume)
                        if self.resume and para.latest_translation:
                            prev_para = para
                            prev_translation = para.latest_translation
                            continue

                        # Translate paragraph
                        try:
                            translation_response = await self._translate_with_retry(
                                adapter=adapter,
                                paragraph=para,
                                mode=task.mode,
                                author_context=author_context,
                                analysis_text=analysis_text,
                                variable_context=variable_context_dict,
                                chapter_index=chapter.chapter_number,
                                paragraph_index=para.paragraph_number,
                                previous_original=prev_para.original_text if prev_para else None,
                                previous_translation=prev_translation,
                            )

                            # Save translation
                            translation = Translation(
                                paragraph_id=para.id,
                                translated_text=translation_response.translated_text,
                                mode=task.mode,
                                provider=self.provider,
                                model=self.model,
                                tokens_used=translation_response.tokens_used,
                            )
                            db.add(translation)

                            # Update progress
                            task.completed_paragraphs += 1
                            task.current_paragraph_id = para.id
                            task.update_progress()
                            await db.commit()

                            # Update previous paragraph context for next iteration
                            prev_para = para
                            prev_translation = translation_response.translated_text

                        except Exception as e:
                            task.error_message = str(e)
                            task.retry_count += 1
                            await db.commit()

                            if task.retry_count >= 3:
                                task.status = TaskStatus.FAILED.value
                                await db.commit()
                                return

                # Complete
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.utcnow()
                task.progress = 1.0

                # Mark project translation as completed
                project.translation_completed = True
                project.current_step = "proofreading"
                await db.commit()

            except Exception as e:
                # Mark as failed
                result = await db.execute(
                    select(TranslationTask).where(TranslationTask.id == self.task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.error_message = str(e)
                    await db.commit()
                raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _translate_with_retry(
        self,
        adapter,
        paragraph: Paragraph,
        mode: str,
        author_context: dict,
        analysis_text: str = None,
        variable_context: dict = None,
        chapter_index: int = None,
        paragraph_index: int = None,
        previous_original: str = None,
        previous_translation: str = None,
    ):
        """Translate a paragraph with retry logic."""
        request = TranslationRequest(
            source_text=paragraph.original_text,
            mode=mode,
            author_background=author_context.get("background"),
            custom_prompts=author_context.get("prompts"),
            existing_translation=paragraph.existing_translation,
            custom_system_prompt=self.custom_system_prompt,
            custom_user_prompt=self.custom_user_prompt,
            analysis_text=analysis_text,
            variable_context=variable_context,
            chapter_index=chapter_index,
            paragraph_index=paragraph_index,
            previous_original=previous_original,
            previous_translation=previous_translation,
        )
        return await adapter.translate(request)


class TranslationProgressTracker:
    """Track and broadcast translation progress."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to progress updates."""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from progress updates."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def broadcast(self, progress: dict):
        """Broadcast progress to all subscribers."""
        for queue in self._subscribers:
            await queue.put(progress)
