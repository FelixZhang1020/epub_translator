"""Proofreading service for reviewing translations and generating suggestions."""

import json
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
)
from app.core.prompts.loader import PromptLoader


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

        # Count paragraphs to proofread
        if chapter_ids:
            result = await db.execute(
                select(func.count(Paragraph.id))
                .where(Paragraph.chapter_id.in_(chapter_ids))
            )
        else:
            result = await db.execute(
                select(func.count(Paragraph.id))
                .join(Chapter)
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

            # Get book analysis for context
            result = await db.execute(
                select(BookAnalysis).where(BookAnalysis.project_id == session.project_id)
            )
            analysis = result.scalar_one_or_none()
            # Extract style info from raw_analysis (dynamic JSON structure)
            raw = analysis.raw_analysis if analysis and analysis.raw_analysis else {}
            writing_style = raw.get("writing_style") or raw.get("style_and_register", {}).get("register") or "Unknown"
            tone = raw.get("tone") or raw.get("style_and_register", {}).get("overall_tone") or "Unknown"

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

            # Process each paragraph
            for para in paragraphs:
                # Get the latest translation
                if not para.translations:
                    continue

                latest_translation = max(
                    para.translations,
                    key=lambda t: t.created_at
                )

                if not latest_translation.translated_text:
                    continue

                # Build prompts using PromptLoader
                template = PromptLoader.load_template("proofreading")
                variables = {
                    "original_text": para.original_text,
                    "current_translation": latest_translation.translated_text,
                    "writing_style": writing_style,
                    "tone": tone,
                }

                system_prompt = custom_system_prompt or PromptLoader.render(
                    template.system_prompt, variables
                )
                user_prompt = PromptLoader.render(
                    custom_user_prompt or template.user_prompt_template,
                    variables
                )

                try:
                    # Call LLM
                    response = await acompletion(
                        model=litellm_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        api_key=api_key,
                    )

                    content = response.choices[0].message.content
                    result_data = self._parse_json_response(content)

                    # Only create suggestion if improvement is needed
                    if result_data.get("needs_improvement"):
                        suggestion = ProofreadingSuggestion(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            paragraph_id=para.id,
                            original_translation=latest_translation.translated_text,
                            suggested_translation=result_data.get("suggested_translation", ""),
                            explanation=result_data.get("explanation", ""),
                            status=SuggestionStatus.PENDING.value,
                        )
                        db.add(suggestion)

                except Exception as e:
                    # Log error but continue with other paragraphs
                    print(f"Error proofreading paragraph {para.id}: {e}")

                # Update progress
                session.completed_paragraphs += 1
                session.update_progress()
                await db.commit()

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
        """Parse JSON response from LLM."""
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
        except json.JSONDecodeError:
            return {"needs_improvement": False}

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
            .options(selectinload(ProofreadingSuggestion.paragraph))
            .where(ProofreadingSuggestion.session_id == session_id)
        )

        if status:
            query = query.where(ProofreadingSuggestion.status == status)

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        suggestions = result.scalars().all()

        return [
            {
                "id": s.id,
                "paragraph_id": s.paragraph_id,
                "original_text": s.paragraph.original_text if s.paragraph else None,
                "original_translation": s.original_translation,
                "suggested_translation": s.suggested_translation,
                "explanation": s.explanation,
                "status": s.status,
                "user_modified_text": s.user_modified_text,
                "created_at": s.created_at.isoformat(),
            }
            for s in suggestions
        ]

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
                if suggestion.status == SuggestionStatus.MODIFIED.value:
                    translation.translated_text = suggestion.user_modified_text
                else:
                    translation.translated_text = suggestion.suggested_translation

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


# Global service instance
proofreading_service = ProofreadingService()
