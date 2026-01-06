"""Translation API routes."""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Project, TranslationTask, TranslationReasoning
from app.models.database.translation import TaskStatus, Translation
from app.models.database.translation_conversation import (
    TranslationConversation,
    ConversationMessage,
)
from app.models.database.paragraph import Paragraph
from app.models.database.chapter import Chapter
from app.core.translation.orchestrator import TranslationOrchestrator
from app.core.llm.service import LLMService
from app.core.llm.config_service import LLMConfigService
from app.core.prompts.loader import PromptLoader
from app.core.llm.prompts import CONVERSATION_SYSTEM_PROMPT
from app.core.translation.models import (
    TranslationMode,
    TranslationContext,
    SourceMaterial,
    BookAnalysisContext,
    AdjacentContext,
    ExistingTranslation,
)
from app.core.translation.pipeline import PromptEngine, ContextBuilder
from litellm import acompletion
import uuid

router = APIRouter()


class StartTranslationRequest(BaseModel):
    """Request to start translation."""
    project_id: str
    mode: str  # "author_aware" | "optimization"
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    provider: Optional[str] = None  # "openai" | "anthropic" | "gemini" | "qwen"
    model: Optional[str] = None
    api_key: Optional[str] = None  # API key for the provider
    # Translation options
    author_background: Optional[str] = None
    custom_prompts: Optional[list[str]] = None
    chapters: Optional[list[int]] = None  # None = all chapters
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None


class TranslationStatus(BaseModel):
    """Translation status response."""
    task_id: str
    project_id: str
    status: str
    progress: float
    completed_paragraphs: int
    total_paragraphs: int
    current_chapter_id: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/translation/start")
async def start_translation(
    request: StartTranslationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new translation task.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    # Resolve LLM configuration
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=request.model,
            provider=request.provider,
            config_id=request.config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == request.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update project with author context if provided
    if request.author_background:
        project.author_background = request.author_background
    if request.custom_prompts:
        project.custom_prompts = request.custom_prompts

    # Calculate total paragraphs based on selected chapters
    if request.chapters:
        # Get paragraph count for selected chapters only
        result = await db.execute(
            select(Chapter)
            .where(
                Chapter.project_id == request.project_id,
                Chapter.chapter_number.in_(request.chapters)
            )
        )
        selected_chapters = result.scalars().all()
        total_paragraphs = sum(ch.paragraph_count for ch in selected_chapters)
    else:
        # All chapters
        total_paragraphs = project.total_paragraphs

    # Create translation task
    task = TranslationTask(
        project_id=request.project_id,
        mode=request.mode,
        provider=llm_config.provider,
        model=llm_config.model,
        status=TaskStatus.PENDING.value,
        total_paragraphs=total_paragraphs,
        author_context={
            "background": request.author_background,
            "prompts": request.custom_prompts,
            "custom_system_prompt": request.custom_system_prompt,
            "custom_user_prompt": request.custom_user_prompt,
        },
        selected_chapters=request.chapters,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Update last used timestamp if using stored config
    if llm_config.config_id:
        await LLMConfigService.update_last_used(db, llm_config.config_id)

    # Start translation in background
    orchestrator = TranslationOrchestrator(
        task_id=task.id,
        provider=llm_config.provider,
        model=llm_config.model,
        api_key=llm_config.api_key,
        custom_system_prompt=request.custom_system_prompt,
        custom_user_prompt=request.custom_user_prompt,
    )
    background_tasks.add_task(orchestrator.run)

    return {"task_id": task.id, "status": "started"}


@router.get("/translation/status/{task_id}")
async def get_translation_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TranslationStatus:
    """Get translation task status."""
    result = await db.execute(
        select(TranslationTask).where(TranslationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TranslationStatus(
        task_id=task.id,
        project_id=task.project_id,
        status=task.status,
        progress=task.progress,
        completed_paragraphs=task.completed_paragraphs,
        total_paragraphs=task.total_paragraphs,
        current_chapter_id=task.current_chapter_id,
        error_message=task.error_message,
    )


@router.post("/translation/pause/{task_id}")
async def pause_translation(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Pause a running translation task."""
    result = await db.execute(
        select(TranslationTask).where(TranslationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PROCESSING.value:
        raise HTTPException(status_code=400, detail="Task is not running")

    task.status = TaskStatus.PAUSED.value
    task.paused_at = datetime.utcnow()
    await db.commit()

    return {"status": "paused"}


class ResumeTranslationRequest(BaseModel):
    """Request to resume a paused translation task."""
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    api_key: Optional[str] = None


@router.post("/translation/resume/{task_id}")
async def resume_translation(
    task_id: str,
    request: ResumeTranslationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused translation task.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. api_key: Direct API key (for debugging)
    """
    result = await db.execute(
        select(TranslationTask).where(TranslationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PAUSED.value:
        raise HTTPException(status_code=400, detail="Task is not paused")

    # Resolve LLM configuration (use task's provider/model, just need API key)
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=task.model,
            provider=task.provider,
            config_id=request.config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task.status = TaskStatus.PROCESSING.value
    await db.commit()

    # Update last used timestamp if using stored config
    if llm_config.config_id:
        await LLMConfigService.update_last_used(db, llm_config.config_id)

    # Resume translation in background
    orchestrator = TranslationOrchestrator(
        task_id=task.id,
        provider=task.provider,
        model=task.model,
        api_key=llm_config.api_key,
        resume=True,
    )
    background_tasks.add_task(orchestrator.run)

    return {"status": "resumed"}


@router.post("/translation/cancel/{task_id}")
async def cancel_translation(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a translation task."""
    result = await db.execute(
        select(TranslationTask).where(TranslationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = TaskStatus.FAILED.value
    task.error_message = "Cancelled by user"
    await db.commit()

    return {"status": "cancelled"}


@router.get("/translation/tasks/{project_id}")
async def list_project_tasks(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all translation tasks for a project."""
    result = await db.execute(
        select(TranslationTask)
        .where(TranslationTask.project_id == project_id)
        .order_by(TranslationTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "mode": t.mode,
            "provider": t.provider,
            "model": t.model,
            "status": t.status,
            "progress": t.progress,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.delete("/translation/chapter/{chapter_id}")
async def clear_chapter_translations(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear all translations for a specific chapter.

    This deletes all translation records for paragraphs in the specified chapter.
    Use this before re-translating a chapter to start fresh.
    """
    from sqlalchemy import delete
    from app.models.database.translation_conversation import TranslationConversation

    # Verify chapter exists
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Get all paragraph IDs for this chapter
    result = await db.execute(
        select(Paragraph.id).where(Paragraph.chapter_id == chapter_id)
    )
    paragraph_ids = [row[0] for row in result.fetchall()]

    if not paragraph_ids:
        return {"deleted_count": 0, "chapter_id": chapter_id}

    # Get all translation IDs for these paragraphs (needed for deleting related records)
    result = await db.execute(
        select(Translation.id).where(Translation.paragraph_id.in_(paragraph_ids))
    )
    translation_ids = [row[0] for row in result.fetchall()]

    if translation_ids:
        # First delete related records (conversations and reasonings)
        delete_conv_stmt = delete(TranslationConversation).where(
            TranslationConversation.translation_id.in_(translation_ids)
        )
        await db.execute(delete_conv_stmt)

        delete_reasoning_stmt = delete(TranslationReasoning).where(
            TranslationReasoning.translation_id.in_(translation_ids)
        )
        await db.execute(delete_reasoning_stmt)

    # Now delete the translations themselves
    delete_stmt = delete(Translation).where(
        Translation.paragraph_id.in_(paragraph_ids)
    )
    result = await db.execute(delete_stmt)
    deleted_count = result.rowcount

    await db.commit()

    return {"deleted_count": deleted_count, "chapter_id": chapter_id}


class ReasoningRequest(BaseModel):
    """Request for translation reasoning."""
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None


class ReasoningResponse(BaseModel):
    """Response with translation reasoning."""
    translation_id: str
    reasoning_text: str
    provider: str
    model: str


@router.post("/translation/reasoning/{translation_id}")
async def request_reasoning(
    translation_id: str,
    request: ReasoningRequest,
    db: AsyncSession = Depends(get_db),
) -> ReasoningResponse:
    """Request reasoning for a translation (on-demand).

    This generates an explanation for why the translation was made.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    # Resolve LLM configuration
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=request.model,
            provider=request.provider,
            config_id=request.config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get translation with paragraph
    result = await db.execute(
        select(Translation)
        .options(selectinload(Translation.paragraph))
        .where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    if not translation:
        raise HTTPException(status_code=404, detail="Translation not found")

    # Check if reasoning already exists
    result = await db.execute(
        select(TranslationReasoning).where(
            TranslationReasoning.translation_id == translation_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return ReasoningResponse(
            translation_id=translation_id,
            reasoning_text=existing.reasoning_text,
            provider=existing.provider,
            model=existing.model,
        )

    # Build prompts using PromptLoader
    template = PromptLoader.load_template("reasoning")
    variables = {
        "original_text": translation.paragraph.original_text,
        "translated_text": translation.translated_text,
    }
    system_prompt = PromptLoader.render(template.system_prompt, variables)
    user_prompt = PromptLoader.render(template.user_prompt_template, variables)

    # Build kwargs for LiteLLM
    kwargs = {"api_key": llm_config.api_key}
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url

    try:
        response = await acompletion(
            model=llm_config.get_litellm_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )

        reasoning_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Update last used timestamp if using stored config
        if llm_config.config_id:
            await LLMConfigService.update_last_used(db, llm_config.config_id)

        # Save reasoning
        reasoning = TranslationReasoning(
            id=str(uuid.uuid4()),
            translation_id=translation_id,
            reasoning_text=reasoning_text,
            provider=llm_config.provider,
            model=llm_config.model,
            tokens_used=tokens_used,
        )
        db.add(reasoning)
        await db.commit()

        return ReasoningResponse(
            translation_id=translation_id,
            reasoning_text=reasoning_text,
            provider=llm_config.provider,
            model=llm_config.model,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@router.get("/translation/reasoning/{translation_id}")
async def get_reasoning(
    translation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReasoningResponse:
    """Get existing reasoning for a translation."""
    result = await db.execute(
        select(TranslationReasoning).where(
            TranslationReasoning.translation_id == translation_id
        )
    )
    reasoning = result.scalar_one_or_none()
    if not reasoning:
        raise HTTPException(status_code=404, detail="No reasoning found for this translation")

    return ReasoningResponse(
        translation_id=translation_id,
        reasoning_text=reasoning.reasoning_text,
        provider=reasoning.provider,
        model=reasoning.model,
    )


# =============================================================================
# Single Paragraph Retranslation
# =============================================================================


class RetranslateRequest(BaseModel):
    """Request to retranslate a single paragraph."""
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None
    # Translation mode
    mode: str = "author_aware"  # "author_aware" | "optimization"


class RetranslateResponse(BaseModel):
    """Response from retranslation."""
    paragraph_id: str
    translation_id: str
    translated_text: str
    provider: str
    model: str
    tokens_used: int


@router.post("/translation/retranslate/{paragraph_id}")
async def retranslate_paragraph(
    paragraph_id: str,
    request: RetranslateRequest,
    db: AsyncSession = Depends(get_db),
) -> RetranslateResponse:
    """Retranslate a single paragraph.

    This creates a new translation version for the specified paragraph.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    import logging
    import traceback
    logger = logging.getLogger(__name__)

    from app.core.translation.pipeline import TranslationPipeline, PipelineConfig

    # Resolve LLM configuration
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=request.model,
            provider=request.provider,
            config_id=request.config_id,
        )
        logger.info(f"Retranslate: resolved LLM config for provider={llm_config.provider}, model={llm_config.model}")
    except ValueError as e:
        logger.error(f"Retranslate: failed to resolve LLM config: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Load paragraph with chapter and project
    try:
        result = await db.execute(
            select(Paragraph)
            .options(
                selectinload(Paragraph.chapter),
                selectinload(Paragraph.translations),
            )
            .where(Paragraph.id == paragraph_id)
        )
        paragraph = result.scalar_one_or_none()
        if not paragraph:
            raise HTTPException(status_code=404, detail="Paragraph not found")
        logger.info(f"Retranslate: loaded paragraph {paragraph_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retranslate: failed to load paragraph: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to load paragraph: {str(e)}")

    # Load project with analysis
    try:
        result = await db.execute(
            select(Project)
            .options(selectinload(Project.analysis))
            .where(Project.id == paragraph.chapter.project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        logger.info(f"Retranslate: loaded project {project.id}, has_analysis={project.analysis is not None}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retranslate: failed to load project: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to load project: {str(e)}")

    # Parse mode
    try:
        translation_mode = TranslationMode(request.mode)
        logger.info(f"Retranslate: using mode {translation_mode}")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {request.mode}",
        )

    # Build context
    try:
        context_builder = ContextBuilder(db)
        context = await context_builder.build(
            paragraph=paragraph,
            project=project,
            mode=translation_mode,
            include_adjacent=True,
        )
        logger.info(f"Retranslate: built context, source_text_len={len(context.source.text)}")
    except Exception as e:
        logger.error(f"Retranslate: failed to build context: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to build context: {str(e)}")

    # Create pipeline config and translate
    config = PipelineConfig(
        provider=llm_config.provider,
        model=llm_config.model,
        api_key=llm_config.api_key,
        mode=translation_mode,
        temperature=llm_config.temperature,
    )
    pipeline = TranslationPipeline(config)

    try:
        logger.info(f"Retranslate: calling LLM...")
        translation_result = await pipeline.translate(context)
        logger.info(f"Retranslate: translation complete, result_len={len(translation_result.translated_text)}")
    except Exception as e:
        logger.error(f"Retranslate: translation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

    # Update last used timestamp if using stored config
    if llm_config.config_id:
        await LLMConfigService.update_last_used(db, llm_config.config_id)

    # Get current max version for this paragraph
    try:
        max_version = 0
        for t in paragraph.translations:
            if t.version > max_version:
                max_version = t.version
        logger.info(f"Retranslate: current max_version={max_version}")

        # Save new translation
        new_translation = Translation(
            id=str(uuid.uuid4()),
            paragraph_id=paragraph_id,
            translated_text=translation_result.translated_text,
            mode=translation_mode.value,
            provider=translation_result.provider,
            model=translation_result.model,
            tokens_used=translation_result.tokens_used,
            version=max_version + 1,
        )
        db.add(new_translation)
        await db.commit()
        await db.refresh(new_translation)
        logger.info(f"Retranslate: saved new translation {new_translation.id}, version={new_translation.version}")
    except Exception as e:
        logger.error(f"Retranslate: failed to save translation: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to save translation: {str(e)}")

    return RetranslateResponse(
        paragraph_id=paragraph_id,
        translation_id=new_translation.id,
        translated_text=translation_result.translated_text,
        provider=translation_result.provider,
        model=translation_result.model,
        tokens_used=translation_result.tokens_used,
    )


# =============================================================================
# Translation Conversation Endpoints
# =============================================================================


class StartConversationRequest(BaseModel):
    """Request to start a conversation."""
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message in conversation."""
    message: str
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None


class ConversationMessageResponse(BaseModel):
    """Response for a single message."""
    id: str
    role: str
    content: str
    suggested_translation: Optional[str] = None
    suggestion_applied: bool = False
    tokens_used: int = 0
    created_at: str


class ConversationResponse(BaseModel):
    """Response for a conversation."""
    id: str
    translation_id: str
    original_text: str
    initial_translation: str
    current_translation: str
    messages: List[ConversationMessageResponse]
    provider: str
    model: str
    total_tokens_used: int
    created_at: str


class ApplyTranslationRequest(BaseModel):
    """Request to apply a suggested translation."""
    message_id: str


def _extract_suggested_translation(content: str) -> Optional[str]:
    """Extract suggested translation from LLM response."""
    patterns = [
        # Pattern: **Suggested translation:** "translation here"
        r'\*\*Suggested translation:\*\*\s*["\u201c]([^"\u201d]+)["\u201d]',
        # Pattern: Suggested translation: "translation here"
        r'(?:Suggested|Recommended|Improved|New)\s+translation[:\s]*["\u201c]([^"\u201d]+)["\u201d]',
        # Pattern: 建议译文: "translation here"
        r'[\u5efa\u8bae\u8bd1\u6587\u63a8\u8350\u8bd1\u6cd5][:\uff1a]\s*["\u201c]([^"\u201d]+)["\u201d]',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def _build_conversation_messages(
    conversation: TranslationConversation,
    current_translation: str,
    new_user_message: str,
) -> List[dict]:
    """Build message list for LLM including context and history."""
    messages = [
        {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Context for this conversation:

Original text (English):
{conversation.original_text}

Current translation (Chinese):
{current_translation}

Please help me understand and improve this translation."""
        },
        {
            "role": "assistant",
            "content": "I understand. I can help you analyze, discuss, or improve this translation. Feel free to ask questions about translation choices, request alternatives, or suggest modifications."
        }
    ]

    # Add conversation history
    for msg in conversation.messages:
        messages.append({
            "role": msg.role,
            "content": msg.content,
        })

    # Add new user message
    messages.append({
        "role": "user",
        "content": new_user_message,
    })

    return messages


@router.post("/translation/conversation/{translation_id}/start")
async def start_conversation(
    translation_id: str,
    request: StartConversationRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Start or resume a conversation for a translation.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    # Check for existing conversation
    result = await db.execute(
        select(TranslationConversation)
        .options(selectinload(TranslationConversation.messages))
        .where(TranslationConversation.translation_id == translation_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        # Get current translation
        result = await db.execute(
            select(Translation).where(Translation.id == translation_id)
        )
        translation = result.scalar_one_or_none()
        current_translation = translation.translated_text if translation else conversation.initial_translation

        return ConversationResponse(
            id=conversation.id,
            translation_id=translation_id,
            original_text=conversation.original_text,
            initial_translation=conversation.initial_translation,
            current_translation=current_translation,
            messages=[
                ConversationMessageResponse(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    suggested_translation=msg.suggested_translation,
                    suggestion_applied=msg.suggestion_applied,
                    tokens_used=msg.tokens_used,
                    created_at=msg.created_at.isoformat(),
                )
                for msg in conversation.messages
            ],
            provider=conversation.provider,
            model=conversation.model,
            total_tokens_used=conversation.total_tokens_used,
            created_at=conversation.created_at.isoformat(),
        )

    # Resolve LLM configuration for new conversation
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=request.model,
            provider=request.provider,
            config_id=request.config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get translation with paragraph
    result = await db.execute(
        select(Translation)
        .options(selectinload(Translation.paragraph))
        .where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    if not translation:
        raise HTTPException(status_code=404, detail="Translation not found")

    # Create new conversation
    conversation = TranslationConversation(
        id=str(uuid.uuid4()),
        translation_id=translation_id,
        provider=llm_config.provider,
        model=llm_config.model,
        original_text=translation.paragraph.original_text,
        initial_translation=translation.translated_text,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse(
        id=conversation.id,
        translation_id=translation_id,
        original_text=conversation.original_text,
        initial_translation=conversation.initial_translation,
        current_translation=translation.translated_text,
        messages=[],
        provider=conversation.provider,
        model=conversation.model,
        total_tokens_used=0,
        created_at=conversation.created_at.isoformat(),
    )


@router.get("/translation/conversation/{translation_id}")
async def get_conversation(
    translation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Get existing conversation for a translation."""
    result = await db.execute(
        select(TranslationConversation)
        .options(selectinload(TranslationConversation.messages))
        .where(TranslationConversation.translation_id == translation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="No conversation found for this translation")

    # Get current translation
    result = await db.execute(
        select(Translation).where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    current_translation = translation.translated_text if translation else conversation.initial_translation

    return ConversationResponse(
        id=conversation.id,
        translation_id=translation_id,
        original_text=conversation.original_text,
        initial_translation=conversation.initial_translation,
        current_translation=current_translation,
        messages=[
            ConversationMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                suggested_translation=msg.suggested_translation,
                suggestion_applied=msg.suggestion_applied,
                tokens_used=msg.tokens_used,
                created_at=msg.created_at.isoformat(),
            )
            for msg in conversation.messages
        ],
        provider=conversation.provider,
        model=conversation.model,
        total_tokens_used=conversation.total_tokens_used,
        created_at=conversation.created_at.isoformat(),
    )


@router.post("/translation/conversation/{translation_id}/message")
async def send_message(
    translation_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationMessageResponse:
    """Send a message in the conversation.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    # Resolve LLM configuration
    try:
        llm_config = await LLMConfigService.resolve_config(
            db,
            api_key=request.api_key,
            model=request.model,
            provider=request.provider,
            config_id=request.config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get conversation
    result = await db.execute(
        select(TranslationConversation)
        .options(selectinload(TranslationConversation.messages))
        .where(TranslationConversation.translation_id == translation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found. Start a conversation first.")

    # Get current translation
    result = await db.execute(
        select(Translation).where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    current_translation = translation.translated_text if translation else conversation.initial_translation

    # Build messages for LLM
    messages = _build_conversation_messages(
        conversation,
        current_translation,
        request.message,
    )

    # Save user message
    user_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)

    # Build kwargs for LiteLLM
    kwargs = {"api_key": llm_config.api_key}
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url

    try:
        response = await acompletion(
            model=llm_config.get_litellm_model(),
            messages=messages,
            **kwargs,
        )

        response_content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Update last used timestamp if using stored config
        if llm_config.config_id:
            await LLMConfigService.update_last_used(db, llm_config.config_id)

        # Parse for suggested translation
        suggested = _extract_suggested_translation(response_content)

        # Save assistant message
        assistant_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            suggested_translation=suggested,
            tokens_used=tokens_used,
        )
        db.add(assistant_msg)

        # Update conversation stats
        conversation.total_tokens_used += tokens_used
        conversation.message_count += 2

        await db.commit()
        await db.refresh(assistant_msg)

        return ConversationMessageResponse(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            suggested_translation=assistant_msg.suggested_translation,
            suggestion_applied=assistant_msg.suggestion_applied,
            tokens_used=assistant_msg.tokens_used,
            created_at=assistant_msg.created_at.isoformat(),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Message failed: {str(e)}")


@router.post("/translation/conversation/{translation_id}/apply")
async def apply_suggestion(
    translation_id: str,
    request: ApplyTranslationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply a suggested translation from the conversation."""
    # Get the message with suggestion
    result = await db.execute(
        select(ConversationMessage).where(ConversationMessage.id == request.message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not message.suggested_translation:
        raise HTTPException(status_code=400, detail="No suggestion in this message")

    if message.suggestion_applied:
        raise HTTPException(status_code=400, detail="Suggestion already applied")

    # Get the translation to find paragraph_id
    result = await db.execute(
        select(Translation)
        .options(selectinload(Translation.paragraph))
        .where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    if not translation:
        raise HTTPException(status_code=404, detail="Translation not found")

    # Create new translation version
    new_translation = Translation(
        id=str(uuid.uuid4()),
        paragraph_id=translation.paragraph_id,
        translated_text=message.suggested_translation,
        mode="conversation",
        provider="conversation",
        model="conversation",
        version=translation.version + 1,
        is_manual_edit=True,
    )
    db.add(new_translation)

    # Mark suggestion as applied
    message.suggestion_applied = True

    await db.commit()

    return {"status": "applied", "new_translation": message.suggested_translation}


@router.delete("/translation/conversation/{translation_id}")
async def clear_conversation(
    translation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear conversation history for a translation."""
    result = await db.execute(
        select(TranslationConversation).where(
            TranslationConversation.translation_id == translation_id
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="No conversation found")

    await db.delete(conversation)
    await db.commit()

    return {"status": "cleared"}


# =============================================================================
# Prompt Preview Endpoints
# =============================================================================


class PromptPreviewRequest(BaseModel):
    """Request for prompt preview."""

    source_text: str = Field(..., description="Source text to translate")
    mode: str = Field(default="direct", description="Translation mode")
    target_language: str = Field(default="zh", description="Target language")

    # Book analysis context (optional)
    author_biography: Optional[str] = None
    writing_style: Optional[str] = None
    tone: Optional[str] = None
    target_audience: Optional[str] = None
    key_terminology: Optional[Dict[str, str]] = None
    translation_principles: Optional[Dict[str, Any]] = None

    # Adjacent context (optional)
    previous_original: Optional[str] = None
    previous_translation: Optional[str] = None

    # For optimization mode
    existing_translation: Optional[str] = None

    # Custom prompts
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None


class VariableInfo(BaseModel):
    """Information about a template variable."""

    value: str
    type: str
    used_in: List[str]


class PromptPreviewResponse(BaseModel):
    """Response with rendered prompts and variable information."""

    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    variables: Dict[str, VariableInfo] = Field(default_factory=dict)
    mode: str
    estimated_tokens: int = 0
    temperature: float = 0.3
    max_tokens: int = 4096


@router.post("/translation/preview")
async def preview_prompts(
    request: PromptPreviewRequest,
) -> PromptPreviewResponse:
    """Preview rendered prompts with variables highlighted.

    This endpoint allows you to see exactly what prompts will be sent to the LLM
    before starting a translation. All template variables are shown with their
    values and where they are used.

    Use this to:
    - Verify prompt content before translation
    - Debug custom prompts
    - Understand how book analysis affects prompts
    """
    # Convert mode string to enum
    try:
        mode = TranslationMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {request.mode}. Valid modes: {[m.value for m in TranslationMode]}",
        )

    # Build source material
    source = SourceMaterial(text=request.source_text)

    # Build book analysis context if any fields provided
    book_analysis = None
    if any([
        request.author_biography,
        request.writing_style,
        request.tone,
        request.key_terminology,
        request.translation_principles,
    ]):
        from app.core.translation.models.context import TranslationPrinciples

        principles = None
        if request.translation_principles:
            principles = TranslationPrinciples(**request.translation_principles)

        book_analysis = BookAnalysisContext(
            author_biography=request.author_biography,
            writing_style=request.writing_style,
            tone=request.tone,
            target_audience=request.target_audience,
            key_terminology=request.key_terminology or {},
            translation_principles=principles,
        )

    # Build adjacent context if provided
    adjacent = None
    if request.previous_original:
        adjacent = AdjacentContext(
            previous_original=request.previous_original,
            previous_translation=request.previous_translation,
        )

    # Build existing translation for optimization mode
    existing = None
    if mode == TranslationMode.OPTIMIZATION and request.existing_translation:
        existing = ExistingTranslation(text=request.existing_translation)

    # Create context
    context = TranslationContext(
        source=source,
        target_language=request.target_language,
        mode=mode,
        book_analysis=book_analysis,
        adjacent=adjacent,
        existing=existing,
        custom_system_prompt=request.custom_system_prompt,
        custom_user_prompt=request.custom_user_prompt,
    )

    # Get preview with highlights
    preview = PromptEngine.preview_with_highlights(context)

    # Convert to response format
    variables = {}
    for name, info in preview.get("variables", {}).items():
        variables[name] = VariableInfo(
            value=info.get("value", ""),
            type=info.get("type", "str"),
            used_in=info.get("used_in", []),
        )

    return PromptPreviewResponse(
        system_prompt=preview.get("system_prompt"),
        user_prompt=preview.get("user_prompt"),
        variables=variables,
        mode=preview.get("mode", request.mode),
        estimated_tokens=preview.get("estimated_tokens", 0),
        temperature=preview.get("temperature", 0.3),
        max_tokens=preview.get("max_tokens", 4096),
    )


@router.post("/translation/preview/paragraph/{paragraph_id}")
async def preview_paragraph_prompts(
    paragraph_id: str,
    mode: str = "author_aware",
    include_adjacent: bool = True,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> PromptPreviewResponse:
    """Preview prompts for a specific paragraph from the database.

    This endpoint loads the paragraph and its associated project/analysis
    from the database and generates a preview of the prompts that would
    be used for translation.
    """
    # Load paragraph with chapter and project
    result = await db.execute(
        select(Paragraph)
        .options(
            selectinload(Paragraph.chapter),
            selectinload(Paragraph.translations),
        )
        .where(Paragraph.id == paragraph_id)
    )
    paragraph = result.scalar_one_or_none()
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    # Load project with analysis
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.analysis))
        .where(Project.id == paragraph.chapter.project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Convert mode
    try:
        translation_mode = TranslationMode(mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}. Valid modes: {[m.value for m in TranslationMode]}",
        )

    # Build context using ContextBuilder
    context_builder = ContextBuilder(db)
    context = await context_builder.build(
        paragraph=paragraph,
        project=project,
        mode=translation_mode,
        include_adjacent=include_adjacent,
        custom_system_prompt=custom_system_prompt,
        custom_user_prompt=custom_user_prompt,
    )

    # Get preview
    preview = PromptEngine.preview_with_highlights(context)

    # Convert to response format
    variables = {}
    for name, info in preview.get("variables", {}).items():
        variables[name] = VariableInfo(
            value=info.get("value", ""),
            type=info.get("type", "str"),
            used_in=info.get("used_in", []),
        )

    return PromptPreviewResponse(
        system_prompt=preview.get("system_prompt"),
        user_prompt=preview.get("user_prompt"),
        variables=variables,
        mode=preview.get("mode", mode),
        estimated_tokens=preview.get("estimated_tokens", 0),
        temperature=preview.get("temperature", 0.3),
        max_tokens=preview.get("max_tokens", 4096),
    )


@router.get("/translation/modes")
async def list_translation_modes() -> List[Dict[str, str]]:
    """List available translation modes with descriptions."""
    return [
        {
            "value": TranslationMode.DIRECT.value,
            "name": "Direct Translation",
            "description": "Simple, direct translation without extensive context",
        },
        {
            "value": TranslationMode.AUTHOR_AWARE.value,
            "name": "Author-Aware Translation",
            "description": "Style-preserving translation with book analysis and author context",
        },
        {
            "value": TranslationMode.OPTIMIZATION.value,
            "name": "Translation Optimization",
            "description": "Improve an existing translation for naturalness and accuracy",
        },
        {
            "value": TranslationMode.ITERATIVE.value,
            "name": "Iterative Translation",
            "description": "Two-step process: literal translation followed by refinement",
        },
    ]
