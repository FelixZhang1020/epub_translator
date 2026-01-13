"""Proofreading service for reviewing translations and generating suggestions."""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from litellm import acompletion

from app.models.database import Project, BookAnalysis
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.models.database.translation import Translation
from app.models.database.proofreading import (
    ProofreadingSession,
    ProofreadingSuggestion,
    ProofreadingStatus,
    SuggestionStatus,
    ImprovementLevel,
)
from app.core.prompts.loader import PromptLoader


logger = logging.getLogger(__name__)


class ProofreadingService:
    """Service for managing proofreading sessions and suggestions."""

    async def start_session(
        self,
        db: AsyncSession,
        project_id: str,
        provider: str,
        model: str,
        chapter_ids: Optional[list[str]] = None,
    ) -> ProofreadingSession:
        """Start a new proofreading session.

        Args:
            db: Database session
            project_id: Project ID
            provider: LLM provider
            model: LLM model to use
            chapter_ids: Optional list of chapter IDs to proofread

        Returns:
            ProofreadingSession
        """
        # Verify project exists
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get existing round number
        result = await db.execute(
            select(func.max(ProofreadingSession.round_number))
            .where(ProofreadingSession.project_id == project_id)
        )
        max_round = result.scalar() or 0
        new_round = max_round + 1

        # Count paragraphs with translations (only these will be proofread)
        if chapter_ids:
            result = await db.execute(
                select(func.count(func.distinct(Paragraph.id)))
                .select_from(Paragraph)
                .join(Translation, Translation.paragraph_id == Paragraph.id)
                .where(Paragraph.chapter_id.in_(chapter_ids))
            )
        else:
            result = await db.execute(
                select(func.count(func.distinct(Paragraph.id)))
                .select_from(Paragraph)
                .join(Chapter)
                .join(Translation, Translation.paragraph_id == Paragraph.id)
                .where(Chapter.project_id == project_id)
            )
        total_paragraphs = result.scalar() or 0

        # Create session
        session = ProofreadingSession(
            id=str(uuid.uuid4()),
            project_id=project_id,
            provider=provider,
            model=model,
            round_number=new_round,
            total_paragraphs=total_paragraphs,
            status=ProofreadingStatus.PENDING.value,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        return session

    async def run_proofreading(
        self,
        db: AsyncSession,
        session_id: str,
        provider: str,
        model: str,
        api_key: str,
        chapter_ids: Optional[list[str]] = None,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Run the proofreading process for a session.

        Args:
            db: Database session
            session_id: Proofreading session ID
            provider: LLM provider
            model: LLM model
            api_key: API key for the provider
            chapter_ids: Optional list of chapter IDs to proofread
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt template
            temperature: LLM temperature override
            base_url: Custom API endpoint (for OpenRouter, Ollama, etc.)
        """
        # Get session
        result = await db.execute(
            select(ProofreadingSession).where(ProofreadingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        try:
            # Update status
            session.status = ProofreadingStatus.PROCESSING.value
            session.started_at = datetime.utcnow()
            await db.commit()

            # Get project for variables
            result = await db.execute(
                select(Project).where(Project.id == session.project_id)
            )
            project = result.scalar_one_or_none()

            # Get book analysis for context
            result = await db.execute(
                select(BookAnalysis).where(BookAnalysis.project_id == session.project_id)
            )
            analysis = result.scalar_one_or_none()
            # Extract style info from raw_analysis (dynamic JSON structure)
            raw = analysis.raw_analysis if analysis and analysis.raw_analysis else {}
            writing_style = raw.get("writing_style") or raw.get("style_and_register", {}).get("register") or ""
            tone = raw.get("tone") or raw.get("style_and_register", {}).get("overall_tone") or ""

            # Extract terminology table
            key_terminology = raw.get("key_terminology", [])
            terminology_text = ""
            if key_terminology:
                terminology_text = "\n".join(
                    f"- {term.get('english_term', '')}: {term.get('chinese_translation', '')}"
                    for term in key_terminology
                )

            # Get paragraphs to proofread (with translations)
            query = (
                select(Paragraph)
                .join(Chapter)
                .options(selectinload(Paragraph.translations))
                .where(Chapter.project_id == session.project_id)
            )
            if chapter_ids:
                query = query.where(Paragraph.chapter_id.in_(chapter_ids))

            result = await db.execute(query)
            paragraphs = result.scalars().all()

            # Build LiteLLM model string
            litellm_model = self._get_litellm_model(provider, model)

            # Track processing results
            success_count = 0
            failed_paragraphs = []
            skipped_no_translation = 0

            # Process each paragraph
            for para in paragraphs:
                # Check if session has been cancelled
                await db.refresh(session)
                if session.status == ProofreadingStatus.CANCELLED.value:
                    session.completed_at = datetime.utcnow()
                    await db.commit()
                    return

                # Get the latest translation
                if not para.translations:
                    skipped_no_translation += 1
                    continue

                latest_translation = max(
                    para.translations,
                    key=lambda t: t.created_at
                )

                if not latest_translation.translated_text:
                    skipped_no_translation += 1
                    continue

                # Build prompts using PromptLoader
                template = PromptLoader.load_template("proofreading")
                # Use flat dictionary structure with namespaced keys
                variables = {
                    # Content (required)
                    "content.source": para.original_text,
                    "content.target": latest_translation.translated_text,
                    # Project info
                    "project.title": project.epub_title or project.name if project else "",
                    "project.author": project.epub_author if project else "",
                    "project.author_background": project.author_background if project else "",
                    # Derived from analysis
                    "derived.writing_style": writing_style,
                    "derived.tone": tone,
                    "derived.terminology_table": terminology_text,
                    "derived.author_name": raw.get("author_name", ""),
                    "derived.author_biography": raw.get("author_biography", ""),
                    # Boolean flags for conditional rendering
                    "derived.has_analysis": analysis is not None,
                    "derived.has_writing_style": bool(writing_style),
                    "derived.has_tone": bool(tone),
                    "derived.has_terminology": bool(terminology_text),
                }

                # Render both system and user prompts with variables
                # If custom prompts provided, they contain template markers that need substitution
                system_prompt = PromptLoader.render(
                    custom_system_prompt or template.system_prompt, variables
                )
                user_prompt = PromptLoader.render(
                    custom_user_prompt or template.user_prompt_template,
                    variables
                )

                try:
                    # Call LLM with optional temperature and base_url
                    llm_kwargs = {
                        "model": litellm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "api_key": api_key,
                        "response_format": {"type": "json_object"},
                    }
                    if temperature is not None:
                        llm_kwargs["temperature"] = temperature
                    if base_url:
                        llm_kwargs["base_url"] = base_url
                    response = await acompletion(**llm_kwargs)

                    content = response.choices[0].message.content
                    logger.info(f"Proofreading paragraph {para.id} raw response: {content}")
                    try:
                        result_data = self._parse_json_response(content)
                    except ValueError as parse_error:
                        # Fail fast on invalid JSON to avoid silent "no-op" suggestions
                        session.status = ProofreadingStatus.FAILED.value
                        session.error_message = (
                            f"Invalid LLM response for paragraph {para.id}: {parse_error}"
                        )
                        await db.commit()
                        logger.error(
                            "Proofreading JSON parse failed for paragraph %s: %s. Raw response: %s",
                            para.id,
                            parse_error,
                            content,
                        )
                        raise

                    # Create suggestion for all responses (including "none" level)
                    # This allows users to see LLM feedback even when no changes are needed
                    improvement_level = result_data.get("improvement_level", "none")

                    # suggested_translation is now optional (comment-only workflow)
                    # Only use it if provided by the LLM
                    suggested_translation = result_data.get("suggested_translation")

                    suggestion = ProofreadingSuggestion(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        paragraph_id=para.id,
                        original_translation=latest_translation.translated_text,
                        suggested_translation=suggested_translation,
                        explanation=result_data.get("explanation", ""),
                        improvement_level=improvement_level,
                        issue_types=result_data.get("issue_types", []),
                        status=SuggestionStatus.PENDING.value,
                    )
                    db.add(suggestion)
                    success_count += 1

                except Exception as e:
                    # Log error with proper logging and track failed paragraph
                    error_msg = f"Error proofreading paragraph {para.id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    failed_paragraphs.append({
                        "paragraph_id": para.id,
                        "error": str(e)
                    })

                # Update progress
                session.completed_paragraphs += 1
                session.update_progress()
                await db.commit()

            # Check if all paragraphs failed
            processed_count = success_count + len(failed_paragraphs)
            if processed_count > 0 and success_count == 0:
                # All paragraphs failed - mark session as failed
                session.status = ProofreadingStatus.FAILED.value
                error_summary = f"All {len(failed_paragraphs)} paragraphs failed. "
                if failed_paragraphs:
                    # Show first few errors
                    sample_errors = failed_paragraphs[:3]
                    error_details = "; ".join([f"{e['paragraph_id']}: {e['error']}" for e in sample_errors])
                    error_summary += f"Sample errors: {error_details}"
                session.error_message = error_summary
                await db.commit()
                logger.error(
                    "Proofreading session %s failed: all %d paragraphs failed",
                    session_id,
                    len(failed_paragraphs),
                )
                return
            elif len(failed_paragraphs) > 0:
                # Some paragraphs failed - log warning but continue
                logger.warning(
                    "Proofreading session %s completed with %d successes, %d failures, %d skipped",
                    session_id,
                    success_count,
                    len(failed_paragraphs),
                    skipped_no_translation,
                )

            # Log summary
            logger.info(
                "Proofreading session %s completed: %d successes, %d failures, %d skipped (no translation)",
                session_id,
                success_count,
                len(failed_paragraphs),
                skipped_no_translation,
            )

            # Mark as completed
            session.status = ProofreadingStatus.COMPLETED.value
            session.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            session.status = ProofreadingStatus.FAILED.value
            session.error_message = str(e)
            await db.commit()
            raise

    def _get_litellm_model(self, provider: str, model: str) -> str:
        """Get model string in LiteLLM format."""
        provider_prefixes = {
            "openai": "",  # No prefix for OpenAI
            "anthropic": "anthropic/",
            "gemini": "gemini/",
            "qwen": "qwen/",
            "deepseek": "deepseek/",
            "ollama": "ollama/",
            "openrouter": "openrouter/",
        }
        prefix = provider_prefixes.get(provider, f"{provider}/")

        if provider == "openai":
            return model
        return f"{prefix}{model}"

    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON response from LLM.

        Raises ValueError on failure instead of silently falling back, so we
        surface bad model outputs and stop the session.
        """
        raw_content = content
        try:
            # Try to extract JSON from markdown code block
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON response: {exc}") from exc

    async def get_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> ProofreadingSession:
        """Get a proofreading session by ID."""
        result = await db.execute(
            select(ProofreadingSession)
            .options(selectinload(ProofreadingSession.suggestions))
            .where(ProofreadingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        return session

    async def get_project_sessions(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> list[ProofreadingSession]:
        """Get all proofreading sessions for a project."""
        result = await db.execute(
            select(ProofreadingSession)
            .where(ProofreadingSession.project_id == project_id)
            .order_by(ProofreadingSession.round_number.desc())
        )
        return result.scalars().all()

    async def get_suggestions(
        self,
        db: AsyncSession,
        session_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get suggestions for a session.

        Args:
            db: Database session
            session_id: Proofreading session ID
            status: Optional status filter
            limit: Max results
            offset: Pagination offset

        Returns:
            List of suggestion dicts with paragraph info
        """
        query = (
            select(ProofreadingSuggestion)
            .options(
                selectinload(ProofreadingSuggestion.paragraph)
                .selectinload(Paragraph.translations)
            )
            .where(ProofreadingSuggestion.session_id == session_id)
        )

        if status:
            query = query.where(ProofreadingSuggestion.status == status)

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        suggestions = result.scalars().all()

        suggestion_list = []
        for s in suggestions:
            # Get current translation info from latest version
            is_confirmed = False
            current_translation = s.original_translation  # Default to snapshot
            if s.paragraph and s.paragraph.translations:
                latest_translation = max(s.paragraph.translations, key=lambda t: t.version)
                is_confirmed = latest_translation.is_confirmed
                current_translation = latest_translation.translated_text or s.original_translation

            suggestion_list.append({
                "id": s.id,
                "paragraph_id": s.paragraph_id,
                "original_text": s.paragraph.original_text if s.paragraph else None,
                "original_translation": s.original_translation,  # Snapshot when suggestion was created
                "current_translation": current_translation,  # Actual current translation (may be edited)
                "suggested_translation": s.suggested_translation,
                "explanation": s.explanation,
                "improvement_level": s.improvement_level,
                "issue_types": s.issue_types or [],
                "status": s.status,
                "user_modified_text": s.user_modified_text,
                "created_at": s.created_at.isoformat(),
                "is_confirmed": is_confirmed,
            })

        return suggestion_list

    async def update_suggestion(
        self,
        db: AsyncSession,
        suggestion_id: str,
        action: str,
        modified_text: Optional[str] = None,
    ) -> ProofreadingSuggestion:
        """Update a suggestion with user action.

        Args:
            db: Database session
            suggestion_id: Suggestion ID
            action: "accept", "reject", or "modify"
            modified_text: Modified translation text (for "modify" action)

        Returns:
            Updated suggestion
        """
        result = await db.execute(
            select(ProofreadingSuggestion).where(ProofreadingSuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()
        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found")

        if action == "accept":
            suggestion.status = SuggestionStatus.ACCEPTED.value
        elif action == "reject":
            suggestion.status = SuggestionStatus.REJECTED.value
        elif action == "modify":
            suggestion.status = SuggestionStatus.MODIFIED.value
            suggestion.user_modified_text = modified_text
        else:
            raise ValueError(f"Invalid action: {action}")

        suggestion.resolved_at = datetime.utcnow()
        await db.commit()
        await db.refresh(suggestion)
        return suggestion

    async def apply_suggestions(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict:
        """Apply accepted/modified suggestions to translations.

        Args:
            db: Database session
            session_id: Proofreading session ID

        Returns:
            Dict with counts of applied suggestions
        """
        # Get all accepted/modified suggestions
        result = await db.execute(
            select(ProofreadingSuggestion)
            .options(selectinload(ProofreadingSuggestion.paragraph))
            .where(ProofreadingSuggestion.session_id == session_id)
            .where(ProofreadingSuggestion.status.in_([
                SuggestionStatus.ACCEPTED.value,
                SuggestionStatus.MODIFIED.value,
            ]))
        )
        suggestions = result.scalars().all()

        applied_count = 0
        for suggestion in suggestions:
            # Skip suggestions without a replacement text (comment-only mode)
            new_text = None
            if suggestion.status == SuggestionStatus.MODIFIED.value:
                new_text = suggestion.user_modified_text
            else:
                new_text = suggestion.suggested_translation

            if not new_text:
                # Skip comment-only suggestions
                continue

            # Get the latest translation for the paragraph
            result = await db.execute(
                select(Translation)
                .where(Translation.paragraph_id == suggestion.paragraph_id)
                .order_by(Translation.created_at.desc())
                .limit(1)
            )
            translation = result.scalar_one_or_none()

            if translation:
                # Apply the suggested or modified text
                translation.translated_text = new_text
                translation.is_manual_edit = True
                applied_count += 1

        await db.commit()

        return {
            "applied": applied_count,
            "total": len(suggestions),
        }

    async def get_project_pending_count(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> int:
        """Get count of pending suggestions for a project."""
        result = await db.execute(
            select(func.count(ProofreadingSuggestion.id))
            .join(ProofreadingSession)
            .where(ProofreadingSession.project_id == project_id)
            .where(ProofreadingSuggestion.status == SuggestionStatus.PENDING.value)
        )
        return result.scalar() or 0

    async def cancel_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> ProofreadingSession:
        """Cancel a running proofreading session."""
        result = await db.execute(
            select(ProofreadingSession).where(ProofreadingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status == ProofreadingStatus.PROCESSING.value:
            session.status = ProofreadingStatus.CANCELLED.value
            session.completed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(session)

        return session


# Global service instance
proofreading_service = ProofreadingService()
