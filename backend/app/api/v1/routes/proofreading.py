"""Proofreading API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import LLMTaskRequest
from app.core.proofreading.service import proofreading_service
from app.core.llm.config_service import LLMConfigService
from app.core.llm.runtime_config import LLMConfigResolver, LLMRuntimeConfig
from app.core.prompts.loader import PromptLoader


router = APIRouter()


class StartProofreadingRequest(LLMTaskRequest):
    """Request to start a proofreading session."""

    chapter_ids: Optional[list[str]] = None
    include_non_main: bool = False  # Include non-main content (images, publishing, etc.)


class ProofreadingSessionResponse(BaseModel):
    """Response model for proofreading session."""
    id: str
    project_id: str
    provider: str
    model: str
    status: str
    round_number: int
    progress: float
    total_paragraphs: int
    completed_paragraphs: int
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SuggestionResponse(BaseModel):
    """Response model for proofreading suggestion."""
    id: str
    paragraph_id: str
    original_text: Optional[str] = None
    original_translation: str  # Snapshot when suggestion was created
    current_translation: Optional[str] = None  # Actual current translation (may be edited)
    suggested_translation: Optional[str] = None  # Nullable for comment-only workflow
    explanation: Optional[str] = None
    status: str
    user_modified_text: Optional[str] = None
    created_at: str
    improvement_level: Optional[str] = None
    issue_types: Optional[list[str]] = None
    is_confirmed: bool = False  # Whether the translation is locked


class UpdateSuggestionRequest(BaseModel):
    """Request to update a suggestion."""
    action: str  # "accept", "reject", or "modify"
    modified_text: Optional[str] = None


class QuickRecommendationRequest(BaseModel):
    """Request for a quick LLM recommendation."""
    original_text: str
    current_translation: str
    feedback: str
    config_id: Optional[str] = None


class QuickRecommendationResponse(BaseModel):
    """Response with LLM recommendation."""
    recommended_translation: str


class ApplyResult(BaseModel):
    """Result of applying suggestions."""
    applied: int
    total: int


async def run_proofreading_background(
    session_id: str,
    provider: str,
    model: str,
    api_key: str,
    config_id: Optional[str],
    chapter_ids: Optional[list[str]],
    include_non_main: bool = False,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    base_url: Optional[str] = None,
):
    """Run proofreading in background."""
    from app.models.database.base import async_session_maker
    async with async_session_maker() as db:
        await proofreading_service.run_proofreading(
            db=db,
            session_id=session_id,
            provider=provider,
            model=model,
            api_key=api_key,
            chapter_ids=chapter_ids,
            include_non_main=include_non_main,
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
            temperature=temperature,
            base_url=base_url,
        )
        # Update last used timestamp if using stored config
        if config_id:
            await LLMConfigService.update_last_used(db, config_id)


@router.post("/proofreading/{project_id}/start")
async def start_proofreading(
    project_id: str,
    request: StartProofreadingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ProofreadingSessionResponse:
    """Start a new proofreading session.

    Supports two ways to specify LLM configuration:
    1. config_id: Reference a stored configuration (recommended)
    2. provider + model + api_key: Direct parameters (for debugging)
    """
    # Resolve LLM configuration with stage-specific defaults
    try:
        if request.api_key or request.model:
            # Direct parameters provided - use old service for backward compatibility
            old_config = await LLMConfigService.resolve_config(
                db,
                api_key=request.api_key,
                model=request.model,
                provider=request.provider,
                config_id=request.config_id,
            )
            llm_config = LLMRuntimeConfig(
                provider=old_config.provider,
                model=old_config.model,
                api_key=old_config.api_key,
                base_url=old_config.base_url,
                temperature=old_config.temperature,
                config_id=old_config.config_id,
                config_name=old_config.config_name,
            )
        else:
            # Use new resolver with stage-specific defaults
            llm_config = await LLMConfigResolver.resolve(
                db,
                config_id=request.config_id,
                stage="proofreading",
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await proofreading_service.start_session(
            db=db,
            project_id=project_id,
            provider=llm_config.provider,
            model=llm_config.model,
            chapter_ids=request.chapter_ids,
            include_non_main=request.include_non_main,
        )

        # Run proofreading in background
        background_tasks.add_task(
            run_proofreading_background,
            session_id=session.id,
            provider=llm_config.provider,
            model=llm_config.model,
            api_key=llm_config.api_key,
            config_id=llm_config.config_id,
            chapter_ids=request.chapter_ids,
            include_non_main=request.include_non_main,
            custom_system_prompt=request.custom_system_prompt,
            custom_user_prompt=request.custom_user_prompt,
            temperature=llm_config.temperature,
            base_url=llm_config.base_url,
        )

        return ProofreadingSessionResponse(
            id=session.id,
            project_id=session.project_id,
            provider=session.provider,
            model=session.model,
            status=session.status,
            round_number=session.round_number,
            progress=session.progress,
            total_paragraphs=session.total_paragraphs,
            completed_paragraphs=session.completed_paragraphs,
            error_message=session.error_message,
            created_at=session.created_at.isoformat(),
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start proofreading: {str(e)}")


@router.get("/proofreading/session/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProofreadingSessionResponse:
    """Get proofreading session status."""
    try:
        session = await proofreading_service.get_session(db, session_id)
        return ProofreadingSessionResponse(
            id=session.id,
            project_id=session.project_id,
            provider=session.provider,
            model=session.model,
            status=session.status,
            round_number=session.round_number,
            progress=session.progress,
            total_paragraphs=session.total_paragraphs,
            completed_paragraphs=session.completed_paragraphs,
            error_message=session.error_message,
            created_at=session.created_at.isoformat(),
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/proofreading/{project_id}/sessions")
async def list_sessions(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ProofreadingSessionResponse]:
    """List all proofreading sessions for a project."""
    sessions = await proofreading_service.get_project_sessions(db, project_id)
    return [
        ProofreadingSessionResponse(
            id=s.id,
            project_id=s.project_id,
            provider=s.provider,
            model=s.model,
            status=s.status,
            round_number=s.round_number,
            progress=s.progress,
            total_paragraphs=s.total_paragraphs,
            completed_paragraphs=s.completed_paragraphs,
            error_message=s.error_message,
            created_at=s.created_at.isoformat(),
            started_at=s.started_at.isoformat() if s.started_at else None,
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
        )
        for s in sessions
    ]


@router.get("/proofreading/{session_id}/suggestions")
async def get_suggestions(
    session_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[SuggestionResponse]:
    """Get suggestions for a proofreading session."""
    suggestions = await proofreading_service.get_suggestions(
        db=db,
        session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [SuggestionResponse(**s) for s in suggestions]


@router.put("/proofreading/suggestion/{suggestion_id}")
async def update_suggestion(
    suggestion_id: str,
    request: UpdateSuggestionRequest,
    db: AsyncSession = Depends(get_db),
) -> SuggestionResponse:
    """Update a suggestion with user action."""
    try:
        suggestion = await proofreading_service.update_suggestion(
            db=db,
            suggestion_id=suggestion_id,
            action=request.action,
            modified_text=request.modified_text,
        )
        return SuggestionResponse(
            id=suggestion.id,
            paragraph_id=suggestion.paragraph_id,
            original_text=None,  # Not loaded
            original_translation=suggestion.original_translation,
            suggested_translation=suggestion.suggested_translation,
            explanation=suggestion.explanation,
            status=suggestion.status,
            user_modified_text=suggestion.user_modified_text,
            created_at=suggestion.created_at.isoformat(),
            improvement_level=suggestion.improvement_level,
            issue_types=suggestion.issue_types,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/proofreading/{session_id}/apply")
async def apply_suggestions(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApplyResult:
    """Apply accepted/modified suggestions to translations."""
    result = await proofreading_service.apply_suggestions(db, session_id)
    return ApplyResult(**result)


@router.get("/proofreading/{project_id}/pending-count")
async def get_pending_count(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get count of pending suggestions for a project."""
    count = await proofreading_service.get_project_pending_count(db, project_id)
    return {"pending_count": count}


@router.post("/proofreading/session/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProofreadingSessionResponse:
    """Cancel a running proofreading session."""
    try:
        session = await proofreading_service.cancel_session(db, session_id)
        return ProofreadingSessionResponse(
            id=session.id,
            project_id=session.project_id,
            provider=session.provider,
            model=session.model,
            status=session.status,
            round_number=session.round_number,
            progress=session.progress,
            total_paragraphs=session.total_paragraphs,
            completed_paragraphs=session.completed_paragraphs,
            error_message=session.error_message,
            created_at=session.created_at.isoformat(),
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/proofreading/quick-recommendation")
async def get_quick_recommendation(
    request: QuickRecommendationRequest,
    db: AsyncSession = Depends(get_db),
) -> QuickRecommendationResponse:
    """Get a quick LLM recommendation for improving a translation.

    Uses a simple prompt with original text, current translation, and feedback
    to generate an improved translation.
    """
    from litellm import acompletion

    # Resolve LLM configuration with stage-specific defaults
    try:
        # Use new resolver with stage-specific defaults for proofreading
        llm_config = await LLMConfigResolver.resolve(
            db,
            config_id=request.config_id,
            stage="proofreading",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Load prompt template (uses optimization/ for unified prompts)
    template = PromptLoader.load_template("optimization")

    # Prepare variables for the prompt
    variables = {
        "content": {
            "source": request.original_text,
            "target": request.current_translation,
        },
        "pipeline": {
            "feedback": request.feedback,
        },
    }

    # Render prompts
    system_prompt = PromptLoader.render(template.system_prompt, variables)
    user_prompt = PromptLoader.render(template.user_prompt_template, variables)

    # Use LLMRuntimeConfig's built-in methods for litellm call
    try:
        response = await acompletion(
            model=llm_config.get_litellm_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            api_key=llm_config.api_key,
            temperature=llm_config.temperature,  # Uses stage-specific default from resolver
        )

        recommended_translation = response.choices[0].message.content.strip()

        return QuickRecommendationResponse(
            recommended_translation=recommended_translation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendation: {str(e)}")

