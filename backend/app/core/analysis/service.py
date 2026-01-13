"""Book Analysis Service - Analyze book content for translation context."""

import json
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from litellm import acompletion

from app.models.database import Project, BookAnalysis, AnalysisTask
from app.models.database.paragraph import Paragraph
from app.models.database.chapter import Chapter
from app.core.prompts.loader import PromptLoader
from app.core.prompts.variables import VariableService

if TYPE_CHECKING:
    from app.core.llm.config_service import ResolvedLLMConfig


class BookAnalysisService:
    """Service for analyzing book content to extract translation context."""

    async def _update_analysis_task(
        self,
        db: AsyncSession,
        task: AnalysisTask,
        step: str,
        progress: float,
        message: str,
        status: str = "processing"
    ):
        """Helper to update analysis task progress."""
        task.status = status
        task.current_step = step
        task.progress = progress
        task.step_message = message
        if status == "completed":
            task.completed_at = datetime.utcnow()
        elif status == "failed":
            task.error_message = message
        await db.commit()

    async def _check_task_cancelled(
        self,
        db: AsyncSession,
        task_id: str
    ) -> bool:
        """Check if the analysis task has been cancelled."""
        result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        return task is not None and task.status == "cancelled"

    async def analyze_book(
        self,
        db: AsyncSession,
        project_id: str,
        llm_config: "ResolvedLLMConfig",
        sample_count: int = 20,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> BookAnalysis:
        """Analyze book content and create/update BookAnalysis record.

        Args:
            db: Database session
            project_id: Project ID
            llm_config: Resolved LLM configuration
            sample_count: Number of sample paragraphs to analyze
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt

        Returns:
            BookAnalysis record with extracted information
        """
        # Get project with chapters
        result = await db.execute(
            select(Project)
            .options(selectinload(Project.chapters))
            .where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get sample paragraphs from across the book
        sample_paragraphs = await self._get_sample_paragraphs(
            db, project_id, sample_count
        )

        if not sample_paragraphs:
            raise ValueError("No paragraphs found in project")

        # Build variable context using VariableService (includes user-defined variables)
        variable_context = await VariableService.build_context(db, project_id)

        # Build the analysis prompt using PromptLoader
        sample_text = "\n\n".join([p.original_text for p in sample_paragraphs])

        # Merge variable context with analysis-specific variables
        variables = variable_context.to_flat_dict()
        variables.update({
            "title": project.epub_title or project.name,
            "author": project.epub_author or "Unknown",
            "sample_paragraphs": sample_text,
            # Also add flat versions for backwards compatibility
            "project.title": project.epub_title or project.name,
            "project.author": project.epub_author or "Unknown",
            "content.sample_paragraphs": sample_text,
        })

        # Load and render prompts from template files
        if custom_system_prompt or custom_user_prompt:
            # Use custom prompts if provided, or fall back to defaults
            system_template = custom_system_prompt or PromptLoader.load_template("analysis").system_prompt
            user_template = custom_user_prompt or PromptLoader.load_template("analysis").user_prompt_template
            # Always render both prompts with variables
            system_prompt = PromptLoader.render(system_template, variables)
            user_prompt = PromptLoader.render(user_template, variables)
        else:
            # Use prompts from template files
            rendered = PromptLoader.preview("analysis", variables)
            system_prompt = rendered["system_prompt"]
            user_prompt = rendered["user_prompt"]

        # Build kwargs for LiteLLM
        kwargs = {"api_key": llm_config.api_key}
        if llm_config.base_url:
            kwargs["api_base"] = llm_config.base_url

        response = await acompletion(
            model=llm_config.get_litellm_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )

        # Parse the response
        response_text = response.choices[0].message.content
        analysis_data = self._parse_analysis_response(response_text)

        # Check if analysis already exists
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        existing_analysis = result.scalar_one_or_none()

        if existing_analysis:
            # Update existing analysis with raw JSON data
            existing_analysis.raw_analysis = analysis_data
            existing_analysis.provider = llm_config.provider
            existing_analysis.model = llm_config.model
            existing_analysis.updated_at = datetime.utcnow()
            existing_analysis.user_confirmed = False  # Reset confirmation
            # Also reset project's analysis_completed flag
            project.analysis_completed = False
            analysis = existing_analysis
        else:
            # Create new analysis with raw JSON data
            analysis = BookAnalysis(
                id=str(uuid.uuid4()),
                project_id=project_id,
                raw_analysis=analysis_data,
                provider=llm_config.provider,
                model=llm_config.model,
            )
            db.add(analysis)

        # Also save author_background to Project model if present
        if analysis_data.get("author_background"):
            project.author_background = analysis_data["author_background"]

        await db.commit()
        await db.refresh(analysis)
        return analysis

    async def analyze_book_streaming(
        self,
        db: AsyncSession,
        project_id: str,
        llm_config: "ResolvedLLMConfig",
        sample_count: int = 20,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """Analyze book content with streaming progress updates.

        Yields progress events during the analysis process.

        Args:
            db: Database session
            project_id: Project ID
            llm_config: Resolved LLM configuration
            sample_count: Number of sample paragraphs to analyze
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt

        Yields:
            Progress events with status and data
        """
        # Step 0: Create analysis task and clear old data
        # This ensures progress persists across page refreshes
        task_id = str(uuid.uuid4())
        task = AnalysisTask(
            id=task_id,
            project_id=project_id,
            status="processing",
            progress=0.0,
            current_step="loading",
            step_message="Starting analysis...",
            provider=llm_config.provider,
            model=llm_config.model,
            started_at=datetime.utcnow(),
        )
        db.add(task)

        # Clear old analysis data immediately
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        existing_analysis = result.scalar_one_or_none()

        if existing_analysis:
            # Clear the old analysis data and reset flags immediately
            existing_analysis.raw_analysis = {}
            existing_analysis.user_confirmed = False
            existing_analysis.updated_at = datetime.utcnow()

        # Commit task creation and data clearing
        await db.commit()

        # Step 1: Loading project
        task.current_step = "loading"
        task.progress = 0.0
        task.step_message = "Loading project..."
        await db.commit()
        yield {"step": "loading", "progress": 0, "message": "Loading project..."}

        result = await db.execute(
            select(Project)
            .options(selectinload(Project.chapters))
            .where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        # Also reset project's analysis_completed flag immediately
        if project:
            project.analysis_completed = False

        # Commit all changes (clear analysis + reset project flag)
        await db.commit()
        if not project:
            yield {"step": "error", "progress": 0, "message": f"Project {project_id} not found"}
            return

        task.progress = 10.0
        task.step_message = "Project loaded"
        await db.commit()
        yield {"step": "loading", "progress": 10, "message": "Project loaded"}

        # Check if cancelled
        if await self._check_task_cancelled(db, task_id):
            yield {"step": "error", "progress": 10, "message": "Analysis cancelled by user"}
            return

        # Step 2: Sampling paragraphs
        task.current_step = "sampling"
        task.progress = 15.0
        task.step_message = "Sampling paragraphs..."
        await db.commit()
        yield {"step": "sampling", "progress": 15, "message": "Sampling paragraphs..."}

        sample_paragraphs = await self._get_sample_paragraphs(
            db, project_id, sample_count
        )

        if not sample_paragraphs:
            yield {"step": "error", "progress": 15, "message": "No paragraphs found in project"}
            return

        task.progress = 25.0
        task.step_message = f"Sampled {len(sample_paragraphs)} paragraphs"
        await db.commit()
        yield {"step": "sampling", "progress": 25, "message": f"Sampled {len(sample_paragraphs)} paragraphs"}

        # Step 3: Building prompts
        task.current_step = "building_prompt"
        task.progress = 30.0
        task.step_message = "Building analysis prompt..."
        await db.commit()
        yield {"step": "building_prompt", "progress": 30, "message": "Building analysis prompt..."}

        # Build variable context using VariableService (includes user-defined variables)
        variable_context = await VariableService.build_context(db, project_id)

        sample_text = "\n\n".join([p.original_text for p in sample_paragraphs])

        # Merge variable context with analysis-specific variables
        variables = variable_context.to_flat_dict()
        variables.update({
            "title": project.epub_title or project.name,
            "author": project.epub_author or "Unknown",
            "sample_paragraphs": sample_text,
            "project.title": project.epub_title or project.name,
            "project.author": project.epub_author or "Unknown",
            "content.sample_paragraphs": sample_text,
        })

        # Load and render prompts from template files
        if custom_system_prompt or custom_user_prompt:
            # Use custom prompts if provided, or fall back to defaults
            system_template = custom_system_prompt or PromptLoader.load_template("analysis").system_prompt
            user_template = custom_user_prompt or PromptLoader.load_template("analysis").user_prompt_template
            # Always render both prompts with variables
            system_prompt = PromptLoader.render(system_template, variables)
            user_prompt = PromptLoader.render(user_template, variables)
        else:
            rendered = PromptLoader.preview("analysis", variables)
            system_prompt = rendered["system_prompt"]
            user_prompt = rendered["user_prompt"]

        task.progress = 35.0
        task.step_message = "Prompt ready"
        await db.commit()
        yield {"step": "building_prompt", "progress": 35, "message": "Prompt ready"}

        # Check if cancelled before calling LLM
        if await self._check_task_cancelled(db, task_id):
            yield {"step": "error", "progress": 35, "message": "Analysis cancelled by user"}
            return

        # Step 4: Calling LLM
        task.current_step = "analyzing"
        task.progress = 40.0
        task.step_message = f"Calling {llm_config.model}..."
        await db.commit()
        yield {"step": "analyzing", "progress": 40, "message": f"Calling {llm_config.model}..."}

        kwargs = {"api_key": llm_config.api_key}
        if llm_config.base_url:
            kwargs["api_base"] = llm_config.base_url

        # Use streaming to get incremental updates
        accumulated_text = ""
        try:
            response = await acompletion(
                model=llm_config.get_litellm_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
                **kwargs,
            )

            chunk_count = 0
            async for chunk in response:
                # Check if cancelled every 10 chunks
                if chunk_count % 10 == 0 and await self._check_task_cancelled(db, task_id):
                    yield {"step": "error", "progress": min(40 + (chunk_count * 2), 85), "message": "Analysis cancelled by user"}
                    return

                if chunk.choices and chunk.choices[0].delta.content:
                    accumulated_text += chunk.choices[0].delta.content
                    chunk_count += 1
                    # Update progress (40-85%)
                    progress = min(40 + (chunk_count * 2), 85)

                    # Update database task every 10 chunks so progress persists on refresh
                    if chunk_count % 10 == 0:
                        await self._update_analysis_task(
                            db, task, "analyzing", progress,
                            f"Receiving response... ({len(accumulated_text)} chars)"
                        )

                    yield {
                        "step": "analyzing",
                        "progress": progress,
                        "message": f"Receiving response... ({len(accumulated_text)} chars)",
                        "partial_content": accumulated_text[-500:] if len(accumulated_text) > 500 else accumulated_text
                    }

        except Exception as e:
            # Update task status to failed
            await self._update_analysis_task(db, task, "error", 40, f"LLM error: {str(e)}", "failed")
            yield {"step": "error", "progress": 40, "message": f"LLM error: {str(e)}"}
            return

        task.progress = 85.0
        task.step_message = "Response received"
        await db.commit()
        yield {"step": "analyzing", "progress": 85, "message": "Response received"}

        # Check if cancelled before parsing
        if await self._check_task_cancelled(db, task_id):
            yield {"step": "error", "progress": 85, "message": "Analysis cancelled by user"}
            return

        # Step 5: Parsing response
        task.current_step = "parsing"
        task.progress = 88.0
        task.step_message = "Parsing JSON response..."
        await db.commit()
        yield {"step": "parsing", "progress": 88, "message": "Parsing JSON response..."}

        analysis_data = self._parse_analysis_response(accumulated_text)

        if "_parse_error" in analysis_data:
            task.progress = 90.0
            task.step_message = "JSON parsing had issues, raw response preserved"
            await db.commit()
            yield {
                "step": "warning",
                "progress": 90,
                "message": "JSON parsing had issues, raw response preserved"
            }
        else:
            task.progress = 92.0
            task.step_message = "JSON parsed successfully"
            await db.commit()
            yield {"step": "parsing", "progress": 92, "message": "JSON parsed successfully"}

        # Step 6: Saving to database
        task.current_step = "saving"
        task.progress = 95.0
        task.step_message = "Saving analysis..."
        await db.commit()
        yield {"step": "saving", "progress": 95, "message": "Saving analysis..."}

        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        existing_analysis = result.scalar_one_or_none()

        if existing_analysis:
            existing_analysis.raw_analysis = analysis_data
            existing_analysis.provider = llm_config.provider
            existing_analysis.model = llm_config.model
            existing_analysis.updated_at = datetime.utcnow()
            existing_analysis.user_confirmed = False
            # Also reset project's analysis_completed flag
            project.analysis_completed = False
            analysis = existing_analysis
        else:
            analysis = BookAnalysis(
                id=str(uuid.uuid4()),
                project_id=project_id,
                raw_analysis=analysis_data,
                provider=llm_config.provider,
                model=llm_config.model,
            )
            db.add(analysis)

        # Also save author_background to Project model if present
        if analysis_data.get("author_background"):
            project.author_background = analysis_data["author_background"]

        await db.commit()
        await db.refresh(analysis)

        # Update task status to completed
        await self._update_analysis_task(db, task, "complete", 100, "Analysis complete", "completed")

        # Step 7: Complete
        yield {
            "step": "complete",
            "progress": 100,
            "message": "Analysis complete",
            "analysis_id": analysis.id,
            "raw_analysis": analysis_data
        }

    async def get_analysis(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> Optional[BookAnalysis]:
        """Get existing analysis for a project."""
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def update_analysis(
        self,
        db: AsyncSession,
        project_id: str,
        updates: dict,
        confirm: bool = False,
    ) -> BookAnalysis:
        """Update analysis with user modifications.

        Args:
            db: Database session
            project_id: Project ID
            updates: Fields to update (will be merged into raw_analysis)
            confirm: Whether to mark as confirmed

        Returns:
            Updated BookAnalysis
        """
        result = await db.execute(
            select(BookAnalysis).where(BookAnalysis.project_id == project_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise ValueError(f"No analysis found for project {project_id}")

        # Track user modifications
        modifications = analysis.user_modifications or {}
        current_analysis = analysis.raw_analysis or {}

        # Update raw_analysis with provided fields
        for field, new_value in updates.items():
            old_value = current_analysis.get(field)
            if old_value != new_value:
                modifications[field] = {
                    "old": old_value,
                    "new": new_value,
                    "modified_at": datetime.utcnow().isoformat(),
                }
            current_analysis[field] = new_value

        analysis.raw_analysis = current_analysis
        analysis.user_modifications = modifications
        analysis.updated_at = datetime.utcnow()

        if confirm:
            analysis.user_confirmed = True
            analysis.confirmed_at = datetime.utcnow()
            # Also update project workflow status
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if project:
                project.analysis_completed = True
                project.current_step = "translation"

        await db.commit()
        await db.refresh(analysis)
        return analysis

    async def regenerate_field(
        self,
        db: AsyncSession,
        project_id: str,
        field: str,
        llm_config: "ResolvedLLMConfig",
    ) -> BookAnalysis:
        """Regenerate a specific field of the analysis.

        Args:
            db: Database session
            project_id: Project ID
            field: Field to regenerate
            llm_config: Resolved LLM configuration

        Returns:
            Updated BookAnalysis
        """
        # For now, just re-run the full analysis
        # In the future, we could have field-specific prompts
        return await self.analyze_book(db, project_id, llm_config)

    async def _get_sample_paragraphs(
        self,
        db: AsyncSession,
        project_id: str,
        count: int,
    ) -> list[Paragraph]:
        """Get sample paragraphs from across the book.

        Selects paragraphs from beginning, middle, and end of the book
        to get a representative sample.
        """
        # Get all chapters ordered
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()

        if not chapters:
            return []

        # Distribute samples across chapters
        paragraphs = []
        per_chapter = max(1, count // len(chapters))

        for chapter in chapters:
            result = await db.execute(
                select(Paragraph)
                .where(Paragraph.chapter_id == chapter.id)
                .order_by(Paragraph.paragraph_number)
                .limit(per_chapter)
            )
            chapter_paragraphs = result.scalars().all()
            paragraphs.extend(chapter_paragraphs)

            if len(paragraphs) >= count:
                break

        return paragraphs[:count]

    def _parse_analysis_response(self, response_text: str) -> dict:
        """Parse LLM response into structured analysis data."""
        # Try to extract JSON from the response
        try:
            # Look for JSON in the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback: try to parse the entire response as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # If JSON parsing fails, return the raw response
        return {
            "_parse_error": "Failed to parse JSON from LLM response",
            "_raw_response": response_text,
        }


# Global service instance
analysis_service = BookAnalysisService()
