"""API dependencies for project validation and cleanup.

This module provides self-healing dependencies that automatically clean up
orphaned database records when project folders are missing.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.base import get_db, async_session_maker
from app.models.database.project import Project
from app.core.project_storage import ProjectStorage

logger = logging.getLogger(__name__)


async def get_validated_project(
    project_id: Annotated[str, Path(description="Project ID")],
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Get a project with automatic orphan cleanup.

    This dependency validates that both the database record AND the project
    folder exist. If the folder is missing, the database record is automatically
    deleted (self-healing behavior).

    Args:
        project_id: The project UUID from the URL path
        db: Database session

    Returns:
        Project: The validated project

    Raises:
        HTTPException: 404 if project not found or was orphaned
    """
    # Fetch project from database
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project folder exists
    if not ProjectStorage.project_exists(project_id):
        # Self-healing: delete orphaned database record
        logger.warning(
            "Orphaned project detected: %s (%s). Auto-deleting DB record.",
            project.name,
            project_id,
        )
        await db.execute(delete(Project).where(Project.id == project_id))
        await db.commit()
        raise HTTPException(
            status_code=404,
            detail="Project files not found. Orphaned record has been cleaned up.",
        )

    return project


async def sync_projects_on_startup() -> dict:
    """Synchronize database projects with filesystem on startup.

    This function reconciles the database with the filesystem:
    - Deletes DB records for projects whose folders are missing
    - Logs folders that exist without DB records (doesn't auto-delete for safety)

    Returns:
        dict: Summary of cleanup actions taken
    """
    # Get all project folders from filesystem
    projects_base = ProjectStorage.PROJECTS_BASE
    folder_ids = set()
    if projects_base.exists():
        for folder in projects_base.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                folder_ids.add(folder.name)

    # Get all project IDs from database
    async with async_session_maker() as db:
        result = await db.execute(select(Project.id, Project.name))
        db_projects = {row[0]: row[1] for row in result.fetchall()}
        db_ids = set(db_projects.keys())

        # Find orphaned DB records (DB exists, folder missing)
        orphaned_db_records = db_ids - folder_ids
        deleted_count = 0

        for project_id in orphaned_db_records:
            project_name = db_projects.get(project_id, "Unknown")
            logger.warning(
                "Startup sync: Deleting orphaned DB record for project '%s' (%s)",
                project_name,
                project_id,
            )
            await db.execute(delete(Project).where(Project.id == project_id))
            deleted_count += 1

        if deleted_count > 0:
            await db.commit()

        # Find orphaned folders (folder exists, DB missing)
        orphaned_folders = folder_ids - db_ids

        for folder_id in orphaned_folders:
            logger.warning(
                "Startup sync: Orphaned folder detected (no DB record): %s. "
                "Consider manual cleanup.",
                folder_id,
            )

    summary = {
        "db_records_deleted": deleted_count,
        "orphaned_folders_found": len(orphaned_folders),
        "orphaned_folder_ids": list(orphaned_folders),
    }

    if deleted_count > 0 or orphaned_folders:
        logger.info("Startup sync complete: %s", summary)

    return summary


async def validate_project_exists(
    project_id: str,
    db: AsyncSession,
) -> Project:
    """Validate project exists and has folder, with auto-cleanup.

    Use this function for manual validation (e.g., when project_id comes
    from request body instead of URL path).

    Args:
        project_id: The project UUID
        db: Database session

    Returns:
        Project: The validated project

    Raises:
        HTTPException: 404 if project not found or was orphaned
    """
    # Fetch project from database
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project folder exists
    if not ProjectStorage.project_exists(project_id):
        # Self-healing: delete orphaned database record
        logger.warning(
            "Orphaned project detected: %s (%s). Auto-deleting DB record.",
            project.name,
            project_id,
        )
        await db.execute(delete(Project).where(Project.id == project_id))
        await db.commit()
        raise HTTPException(
            status_code=404,
            detail="Project files not found. Orphaned record has been cleaned up.",
        )

    return project


# Type alias for cleaner dependency injection
ValidatedProject = Annotated[Project, Depends(get_validated_project)]
