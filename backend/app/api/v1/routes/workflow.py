"""Workflow navigation API routes."""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Project, BookAnalysis, TranslationTask
from app.models.database.proofreading import ProofreadingSession, ProofreadingSuggestion, SuggestionStatus

router = APIRouter()


class WorkflowStep(str, Enum):
    """Workflow step enum."""
    UPLOAD = "upload"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    PROOFREADING = "proofreading"
    EXPORT = "export"


class WorkflowStatusResponse(BaseModel):
    """Response model for workflow status."""
    project_id: str
    current_step: str
    has_reference_epub: bool
    analysis_completed: bool
    translation_completed: bool
    proofreading_completed: bool
    analysis_progress: Optional[dict] = None
    translation_progress: Optional[dict] = None
    proofreading_progress: Optional[dict] = None


class UpdateStepRequest(BaseModel):
    """Request model for updating workflow step."""
    step: WorkflowStep


@router.get("/workflow/{project_id}/status")
async def get_workflow_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    """Get workflow status and progress for resume."""
    # Load project with analysis
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.analysis))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get analysis progress
    analysis_progress = None
    if project.analysis:
        analysis_progress = {
            "exists": True,
            "confirmed": project.analysis.user_confirmed,
        }
    else:
        analysis_progress = {
            "exists": False,
            "confirmed": False,
        }

    # Get translation progress
    translation_progress = await _get_translation_progress(db, project_id)

    # Get proofreading progress
    proofreading_progress = await _get_proofreading_progress(db, project_id)

    # Derive translation_completed from task status if not already set
    # This handles legacy projects that completed translation before the flag was added
    translation_completed = project.translation_completed
    if not translation_completed and translation_progress.get("status") == "completed":
        translation_completed = True
        # Also update the project in database for future queries
        project.translation_completed = True
        await db.commit()

    return WorkflowStatusResponse(
        project_id=project_id,
        current_step=project.current_step,
        has_reference_epub=project.has_reference_epub,
        analysis_completed=project.analysis_completed,
        translation_completed=translation_completed,
        proofreading_completed=project.proofreading_completed,
        analysis_progress=analysis_progress,
        translation_progress=translation_progress,
        proofreading_progress=proofreading_progress,
    )


@router.put("/workflow/{project_id}/step")
async def update_workflow_step(
    project_id: str,
    request: UpdateStepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update the current workflow step."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate step transition
    valid_transition = _validate_step_transition(project, request.step)
    if not valid_transition:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step transition from {project.current_step} to {request.step.value}"
        )

    project.current_step = request.step.value
    await db.commit()

    return {
        "project_id": project_id,
        "current_step": project.current_step,
    }


@router.get("/workflow/{project_id}/resume")
async def get_resume_position(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the recommended resume position based on workflow state."""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.analysis))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Determine recommended step
    if not project.analysis or not project.analysis.user_confirmed:
        recommended_step = WorkflowStep.ANALYSIS.value
        reason = "Book analysis not completed"
    elif not project.translation_completed:
        recommended_step = WorkflowStep.TRANSLATION.value
        reason = "Translation not completed"
        # Get last translated paragraph for context
        translation_progress = await _get_translation_progress(db, project_id)
        if translation_progress.get("last_paragraph_id"):
            reason = f"Resume translation from paragraph {translation_progress.get('completed_paragraphs', 0) + 1}"
    elif not project.proofreading_completed:
        # Check if there are pending suggestions
        proofreading_progress = await _get_proofreading_progress(db, project_id)
        if proofreading_progress.get("pending_suggestions", 0) > 0:
            recommended_step = WorkflowStep.PROOFREADING.value
            reason = f"Review {proofreading_progress['pending_suggestions']} pending proofreading suggestions"
        else:
            recommended_step = WorkflowStep.PROOFREADING.value
            reason = "Start proofreading"
    else:
        recommended_step = WorkflowStep.EXPORT.value
        reason = "Ready to export"

    return {
        "project_id": project_id,
        "recommended_step": recommended_step,
        "reason": reason,
        "current_step": project.current_step,
    }


async def _get_translation_progress(db: AsyncSession, project_id: str) -> dict:
    """Get translation progress details."""
    # Get the latest translation task
    result = await db.execute(
        select(TranslationTask)
        .where(TranslationTask.project_id == project_id)
        .order_by(TranslationTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()

    if not task:
        return {
            "has_task": False,
            "progress": 0.0,
            "completed_paragraphs": 0,
            "total_paragraphs": 0,
        }

    return {
        "has_task": True,
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "completed_paragraphs": task.completed_paragraphs,
        "total_paragraphs": task.total_paragraphs,
        "last_paragraph_id": task.current_paragraph_id,
    }


async def _get_proofreading_progress(db: AsyncSession, project_id: str) -> dict:
    """Get proofreading progress details."""
    # Get the latest proofreading session
    result = await db.execute(
        select(ProofreadingSession)
        .where(ProofreadingSession.project_id == project_id)
        .order_by(ProofreadingSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if not session:
        return {
            "has_session": False,
            "pending_suggestions": 0,
        }

    # Count pending suggestions
    result = await db.execute(
        select(ProofreadingSuggestion)
        .where(
            ProofreadingSuggestion.session_id == session.id,
            ProofreadingSuggestion.status == SuggestionStatus.PENDING.value
        )
    )
    pending_count = len(result.scalars().all())

    return {
        "has_session": True,
        "session_id": session.id,
        "status": session.status,
        "round_number": session.round_number,
        "progress": session.progress,
        "pending_suggestions": pending_count,
    }


def _validate_step_transition(project: Project, new_step: WorkflowStep) -> bool:
    """Validate if a step transition is allowed."""
    step_order = [
        WorkflowStep.UPLOAD,
        WorkflowStep.ANALYSIS,
        WorkflowStep.TRANSLATION,
        WorkflowStep.PROOFREADING,
        WorkflowStep.EXPORT,
    ]

    current_index = step_order.index(WorkflowStep(project.current_step))
    new_index = step_order.index(new_step)

    # Allow going back to any previous step
    if new_index <= current_index:
        return True

    # Allow moving forward by one step if prerequisites are met
    if new_index == current_index + 1:
        if new_step == WorkflowStep.ANALYSIS:
            return True  # Can always go to analysis after upload
        elif new_step == WorkflowStep.TRANSLATION:
            return project.analysis_completed  # Need completed analysis
        elif new_step == WorkflowStep.PROOFREADING:
            return project.translation_completed  # Need completed translation
        elif new_step == WorkflowStep.EXPORT:
            return True  # Can go to export at any time after proofreading

    return False
