"""Upload API routes."""

import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db, Project
from app.core.epub.parser_v2 import EPUBParserV2

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

    # Save file
    file_path = settings.upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Parse EPUB with V2 parser (lxml-based)
        parser = EPUBParserV2(file_path)
        metadata = await parser.get_metadata()
        chapters = await parser.extract_chapters()

        # Extract hierarchical TOC structure
        toc_structure = parser.extract_toc_structure()

        # Create project
        project = Project(
            name=metadata.get("title", file.filename),
            original_filename=file.filename,
            original_file_path=str(file_path),
            epub_title=metadata.get("title"),
            epub_author=metadata.get("author"),
            epub_language=metadata.get("language"),
            epub_metadata=metadata,
            toc_structure=toc_structure,
            total_chapters=len(chapters),
        )
        db.add(project)
        await db.flush()

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
        # Clean up file on error
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects."""
    from sqlalchemy import select
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "author": p.epub_author,
            "status": p.status,
            "total_chapters": p.total_chapters,
            "total_paragraphs": p.total_paragraphs,
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project details."""
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
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
    }


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a project."""
    from sqlalchemy import select, delete
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete file
    Path(project.original_file_path).unlink(missing_ok=True)

    # Delete from database (cascades to chapters, paragraphs, translations)
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()

    return {"status": "deleted"}


@router.post("/projects/{project_id}/reparse")
async def reparse_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Re-parse an existing project's EPUB file.

    This will delete all existing chapters and paragraphs, then re-parse
    the EPUB file with the latest parser logic.
    WARNING: This will also delete all translations!
    """
    from sqlalchemy import select, delete
    from app.models.database.chapter import Chapter

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
