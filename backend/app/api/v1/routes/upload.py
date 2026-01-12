"""Upload API routes."""

import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db, Project
from app.models.database.chapter import Chapter
from app.core.epub import EPUBParserV2
from app.core.project_storage import ProjectStorage
from app.api.dependencies import ValidatedProject

router = APIRouter()


@router.post("/upload")
async def upload_epub(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an EPUB file and create a new project."""
    # Validate file type
    if not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only EPUB files are allowed")

    # Save to temporary location first (need project_id for final location)
    temp_path = settings.upload_dir / f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Parse EPUB with V2 parser (lxml-based)
        parser = EPUBParserV2(temp_path)
        metadata = await parser.get_metadata()
        chapters = await parser.extract_chapters()

        # Extract hierarchical TOC structure
        toc_structure = parser.extract_toc_structure()

        # Create project (without final file path yet)
        project = Project(
            name=metadata.get("title", file.filename),
            original_filename=file.filename,
            original_file_path="",  # Will be set after moving file
            epub_title=metadata.get("title"),
            epub_author=metadata.get("author"),
            epub_language=metadata.get("language"),
            epub_metadata=metadata,
            toc_structure=toc_structure,
            total_chapters=len(chapters),
        )
        db.add(project)
        await db.flush()  # Get project.id

        # Initialize project directory structure
        ProjectStorage.initialize_project_structure(project.id)

        # Move file to project-scoped location
        final_path = ProjectStorage.get_original_epub_path(project.id)
        shutil.move(str(temp_path), str(final_path))

        # Update project with final file path
        project.original_file_path = str(final_path)

        # Save chapters and paragraphs
        total_paragraphs = await parser.save_to_db(db, project.id, chapters)
        project.total_paragraphs = total_paragraphs

        await db.commit()

        return {
            "project_id": project.id,
            "name": project.name,
            "author": project.epub_author,
            "total_chapters": project.total_chapters,
            "total_paragraphs": project.total_paragraphs,
        }

    except Exception as e:
        # Clean up temporary file on error
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects, favorites first."""
    from sqlalchemy import select
    result = await db.execute(
        select(Project).order_by(Project.is_favorite.desc(), Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "author": p.epub_author,
            "status": p.status,
            "total_chapters": p.total_chapters,
            "total_paragraphs": p.total_paragraphs,
            "is_favorite": p.is_favorite,
            "created_at": p.created_at.isoformat(),
            "epub_title": p.epub_title,
            "epub_author": p.epub_author,
            "epub_language": p.epub_language,
            "author_background": p.author_background,
        }
        for p in projects
    ]


@router.get("/projects/{project_id}")
async def get_project(project: ValidatedProject):
    """Get project details."""
    return {
        "id": project.id,
        "name": project.name,
        "author": project.epub_author,
        "status": project.status,
        "total_chapters": project.total_chapters,
        "total_paragraphs": project.total_paragraphs,
        "author_background": project.author_background,
        "custom_prompts": project.custom_prompts,
        "created_at": project.created_at.isoformat(),
        "epub_title": project.epub_title,
        "epub_author": project.epub_author,
        "epub_language": project.epub_language,
        "is_favorite": project.is_favorite,
    }


@router.delete("/projects/{project_id}")
async def delete_project(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and all its files."""
    project_id = project.id

    # Delete from database first (cascades to chapters, paragraphs, translations)
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()

    # Delete all project files and directories
    ProjectStorage.delete_project(project_id)

    return {"status": "deleted"}


@router.post("/projects/{project_id}/favorite")
async def toggle_favorite(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Toggle the favorite status of a project."""
    project.is_favorite = not project.is_favorite
    await db.commit()

    return {"id": project.id, "is_favorite": project.is_favorite}


@router.post("/projects/{project_id}/reparse")
async def reparse_project(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Re-parse an existing project's EPUB file.

    This will delete all existing chapters and paragraphs, then re-parse
    the EPUB file with the latest parser logic.
    WARNING: This will also delete all translations!
    """
    project_id = project.id

    # Check if file exists
    file_path = Path(project.original_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="EPUB file not found")

    try:
        # Delete existing chapters (cascades to paragraphs and translations)
        await db.execute(delete(Chapter).where(Chapter.project_id == project_id))

        # Re-parse EPUB with V2 parser
        parser = EPUBParserV2(file_path)
        metadata = await parser.get_metadata()
        chapters = await parser.extract_chapters()
        toc_structure = parser.extract_toc_structure()

        # Update project metadata
        project.epub_title = metadata.get("title")
        project.epub_author = metadata.get("author")
        project.epub_language = metadata.get("language")
        project.epub_metadata = metadata
        project.toc_structure = toc_structure
        project.total_chapters = len(chapters)

        # Save chapters and paragraphs
        total_paragraphs = await parser.save_to_db(db, project.id, chapters)
        project.total_paragraphs = total_paragraphs

        await db.commit()

        return {
            "status": "reparsed",
            "project_id": project.id,
            "name": project.name,
            "total_chapters": project.total_chapters,
            "total_paragraphs": project.total_paragraphs,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
