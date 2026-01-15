"""Workflow navigation API routes."""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Project, BookAnalysis, TranslationTask, AnalysisTask
from app.models.database.translation import TaskStatus
from app.models.database.proofreading import ProofreadingSession, ProofreadingSuggestion, SuggestionStatus
from app.api.dependencies import ValidatedProject

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
    validated_project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    """Get workflow status and progress for resume."""
    project_id = validated_project.id

    # Load project with analysis (eager loading)
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.analysis))
        .where(Project.id == project_id)
    )
    project = result.scalar_one()

    # Get analysis progress (includes task status)
    analysis_progress = await _get_analysis_progress(db, project_id)

    # Get translation progress
    translation_progress = await _get_translation_progress(db, project_id)

    # Get proofreading progress
    proofreading_progress = await _get_proofreading_progress(db, project_id)

    return WorkflowStatusResponse(
        project_id=project_id,
        current_step=project.current_step,
        has_reference_epub=project.has_reference_epub,
        analysis_completed=project.analysis_completed,
        translation_completed=project.translation_completed,
        proofreading_completed=project.proofreading_completed,
        analysis_progress=analysis_progress,
        translation_progress=translation_progress,
        proofreading_progress=proofreading_progress,
    )


@router.put("/workflow/{project_id}/step")
async def update_workflow_step(
    project: ValidatedProject,
    request: UpdateStepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update the current workflow step."""
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
        "project_id": project.id,
        "current_step": project.current_step,
    }


@router.get("/workflow/{project_id}/resume")
async def get_resume_position(
    validated_project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Get the recommended resume position based on workflow state."""
    # Load project with analysis (eager loading)
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.analysis))
        .where(Project.id == validated_project.id)
    )
    project = result.scalar_one()
    project_id = project.id

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


async def _get_analysis_progress(db: AsyncSession, project_id: str) -> dict:
    """Get analysis progress details."""
    # Get the latest analysis task
    result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.project_id == project_id)
        .order_by(AnalysisTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()

    if not task:
        return {
            "has_task": False,
            "exists": False,
            "confirmed": False,
        }

    # Check if there's an analysis record
    analysis_result = await db.execute(
        select(BookAnalysis).where(BookAnalysis.project_id == project_id)
    )
    analysis = analysis_result.scalar_one_or_none()

    return {
        "has_task": True,
        "task_id": task.id,
        "status": task.status,  # processing, completed, failed, cancelled
        "progress": task.progress,
        "current_step": task.current_step,
        "step_message": task.step_message,
        "exists": analysis is not None,
        "confirmed": analysis.user_confirmed if analysis else False,
    }


async def _get_translation_progress(db: AsyncSession, project_id: str) -> dict:
    """Get translation progress details."""
    from sqlalchemy import func
    from app.models.database import Translation, Paragraph, Chapter

    # Get the latest translation task
    result = await db.execute(
        select(TranslationTask)
        .where(TranslationTask.project_id == project_id)
        .order_by(TranslationTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()

    # Always check actual translations count from database
    # This ensures button state reflects reality even if task tracking fails
    actual_count_result = await db.execute(
        select(func.count(Translation.id))
        .join(Paragraph, Translation.paragraph_id == Paragraph.id)
        .join(Chapter, Paragraph.chapter_id == Chapter.id)
        .where(Chapter.project_id == project_id)
    )
    actual_completed = actual_count_result.scalar() or 0

    if not task:
        return {
            "has_task": False,
            "progress": 0.0,
            "completed_paragraphs": actual_completed,
            "total_paragraphs": 0,
        }

    # Use actual count if it's higher than task's tracked count
    # This handles cases where task fails but translations were saved
    completed_count = max(task.completed_paragraphs, actual_completed)

    return {
        "has_task": True,
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress if task.total_paragraphs > 0 else (100.0 if actual_completed > 0 else 0.0),
        "completed_paragraphs": completed_count,
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


@router.post("/workflow/{project_id}/confirm-translation")
async def confirm_translation(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Confirm translation completion and advance to proofreading step."""
    project_id = project.id

    # Check if there's any translation content
    translation_progress = await _get_translation_progress(db, project_id)
    if not translation_progress.get("has_task") or translation_progress.get("completed_paragraphs", 0) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot confirm translation: no translated content found"
        )

    status = translation_progress.get("status")
    completed_paragraphs = translation_progress.get("completed_paragraphs", 0) or 0
    total_paragraphs = translation_progress.get("total_paragraphs", 0) or 0
    progress = translation_progress.get("progress", 0.0) or 0.0

    # Block confirmation while translation tasks are still running or incomplete
    if status in (TaskStatus.PROCESSING.value, TaskStatus.PENDING.value):
        raise HTTPException(
            status_code=400,
            detail="Translation is still in progress. Please wait until it finishes."
        )

    if total_paragraphs > 0 and completed_paragraphs < total_paragraphs:
        raise HTTPException(
            status_code=400,
            detail="Translation task has not finished all assigned paragraphs."
        )

    # Progress is on 0-100 scale (percentage)
    if total_paragraphs == 0 and progress < 99.9:
        raise HTTPException(
            status_code=400,
            detail="Translation task is not complete yet."
        )

    # Mark translation as completed
    project.translation_completed = True
    project.current_step = "proofreading"
    await db.commit()

    return {
        "project_id": project_id,
        "translation_completed": True,
        "current_step": project.current_step,
    }


@router.post("/workflow/{project_id}/reset-translation-status")
async def reset_translation_status(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Reset translation completion status back to in-progress."""
    # Reset translation and proofreading completed status
    # Going back to translation invalidates any proofreading work
    project.translation_completed = False
    project.proofreading_completed = False
    project.current_step = "translation"
    await db.commit()
    await db.refresh(project)

    return {
        "project_id": project.id,
        "translation_completed": False,
        "proofreading_completed": False,
        "current_step": project.current_step,
    }


@router.post("/workflow/{project_id}/confirm-proofreading")
async def confirm_proofreading(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Confirm proofreading completion and advance to export step."""
    # Verify translation is completed first
    if not project.translation_completed:
        raise HTTPException(
            status_code=400,
            detail="Cannot confirm proofreading: translation must be completed first"
        )

    # Mark proofreading as completed
    project.proofreading_completed = True
    project.current_step = "export"
    await db.commit()

    return {
        "project_id": project.id,
        "proofreading_completed": True,
        "current_step": project.current_step,
    }


@router.post("/workflow/{project_id}/cancel-stuck-tasks")
async def cancel_stuck_translation_tasks(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Cancel any stuck translation tasks (processing or pending) for the project."""
    project_id = project.id

    # Find all tasks in processing or pending state
    from app.models.database.translation import TaskStatus
    result = await db.execute(
        select(TranslationTask).where(
            TranslationTask.project_id == project_id,
            TranslationTask.status.in_([TaskStatus.PROCESSING.value, TaskStatus.PENDING.value])
        )
    )
    stuck_tasks = result.scalars().all()

    # Cancel each stuck task
    cancelled_count = 0
    for task in stuck_tasks:
        task.status = TaskStatus.FAILED.value
        task.error_message = "Task cancelled by user due to being stuck"
        cancelled_count += 1

    await db.commit()

    return {
        "project_id": project_id,
        "cancelled_tasks": cancelled_count,
        "message": f"Cancelled {cancelled_count} stuck translation task(s)",
    }


@router.post("/workflow/{project_id}/cancel-analysis-task")
async def cancel_analysis_task(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Cancel any active analysis task for the project."""
    project_id = project.id

    # Find active analysis task (processing status)
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.project_id == project_id,
            AnalysisTask.status == "processing"
        ).order_by(AnalysisTask.created_at.desc()).limit(1)
    )
    task = result.scalar_one_or_none()

    if task:
        task.status = "cancelled"
        task.error_message = "Analysis cancelled by user"
        from datetime import datetime, timezone
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "project_id": project_id,
            "cancelled": True,
            "message": "Analysis task cancelled successfully",
        }
    else:
        return {
            "project_id": project_id,
            "cancelled": False,
            "message": "No active analysis task found",
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
            return project.proofreading_completed  # Need completed proofreading

    return False

