"""Book Analysis API routes."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.core.analysis.service import analysis_service
from app.core.llm.config_service import LLMConfigService

router = APIRouter()


class StartAnalysisRequest(BaseModel):
    """Request model for starting analysis."""
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None
    # Analysis options
    sample_count: int = 20
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None


class UpdateAnalysisRequest(BaseModel):
    """Request model for updating analysis - accepts dynamic fields."""
    updates: dict[str, Any] = {}  # Dynamic fields to update
    confirm: bool = False


class RegenerateFieldRequest(BaseModel):
    """Request model for regenerating a field."""
    field: str
    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None
    # Option 2: Direct parameters (for debugging/backwards compatibility)
    model: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response model for book analysis - dynamic structure."""
    id: str
    project_id: str
    raw_analysis: Optional[dict[str, Any]]  # Dynamic analysis data
    user_confirmed: bool
    provider: Optional[str]
    model: Optional[str]
    created_at: str
    confirmed_at: Optional[str]


@router.post("/analysis/{project_id}/start")
async def start_analysis(
    project_id: str,
    request: StartAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Start LLM analysis of book content.

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

    try:
        analysis = await analysis_service.analyze_book(
            db=db,
            project_id=project_id,
            llm_config=llm_config,
            sample_count=request.sample_count,
            custom_system_prompt=request.custom_system_prompt,
            custom_user_prompt=request.custom_user_prompt,
        )

        # Update last used timestamp if using stored config
        if llm_config.config_id:
            await LLMConfigService.update_last_used(db, llm_config.config_id)

        return AnalysisResponse(
            id=analysis.id,
            project_id=analysis.project_id,
            raw_analysis=analysis.raw_analysis,
            user_confirmed=analysis.user_confirmed,
            provider=analysis.provider,
            model=analysis.model,
            created_at=analysis.created_at.isoformat(),
            confirmed_at=analysis.confirmed_at.isoformat() if analysis.confirmed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analysis/{project_id}/start-stream")
async def start_analysis_stream(
    project_id: str,
    request: StartAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start LLM analysis with streaming progress updates.

    Returns Server-Sent Events (SSE) stream with progress updates.
    Each event is a JSON object with: step, progress (0-100), message, and optional data.
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

    async def event_generator():
        """Generate SSE events from the analysis stream."""
        try:
            async for event in analysis_service.analyze_book_streaming(
                db=db,
                project_id=project_id,
                llm_config=llm_config,
                sample_count=request.sample_count,
                custom_system_prompt=request.custom_system_prompt,
                custom_user_prompt=request.custom_user_prompt,
            ):
                # Format as SSE event
                yield f"data: {json.dumps(event)}\n\n"

            # Update last used timestamp if using stored config
            if llm_config.config_id:
                await LLMConfigService.update_last_used(db, llm_config.config_id)

        except Exception as e:
            error_event = {"step": "error", "progress": 0, "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/analysis/{project_id}")
async def get_analysis(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get existing analysis for a project."""
    analysis = await analysis_service.get_analysis(db, project_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this project")

    return AnalysisResponse(
        id=analysis.id,
        project_id=analysis.project_id,
        raw_analysis=analysis.raw_analysis,
        user_confirmed=analysis.user_confirmed,
        provider=analysis.provider,
        model=analysis.model,
        created_at=analysis.created_at.isoformat(),
        confirmed_at=analysis.confirmed_at.isoformat() if analysis.confirmed_at else None,
    )


@router.put("/analysis/{project_id}")
async def update_analysis(
    project_id: str,
    request: UpdateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Update analysis with user modifications."""
    try:
        analysis = await analysis_service.update_analysis(
            db=db,
            project_id=project_id,
            updates=request.updates,
            confirm=request.confirm,
        )
        return AnalysisResponse(
            id=analysis.id,
            project_id=analysis.project_id,
            raw_analysis=analysis.raw_analysis,
            user_confirmed=analysis.user_confirmed,
            provider=analysis.provider,
            model=analysis.model,
            created_at=analysis.created_at.isoformat(),
            confirmed_at=analysis.confirmed_at.isoformat() if analysis.confirmed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/analysis/{project_id}/regenerate")
async def regenerate_field(
    project_id: str,
    request: RegenerateFieldRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Regenerate a specific field of the analysis.

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

    try:
        analysis = await analysis_service.regenerate_field(
            db=db,
            project_id=project_id,
            field=request.field,
            llm_config=llm_config,
        )

        # Update last used timestamp if using stored config
        if llm_config.config_id:
            await LLMConfigService.update_last_used(db, llm_config.config_id)

        return AnalysisResponse(
            id=analysis.id,
            project_id=analysis.project_id,
            raw_analysis=analysis.raw_analysis,
            user_confirmed=analysis.user_confirmed,
            provider=analysis.provider,
            model=analysis.model,
            created_at=analysis.created_at.isoformat(),
            confirmed_at=analysis.confirmed_at.isoformat() if analysis.confirmed_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")
