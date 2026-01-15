"""Upload API routes."""

import asyncio
import re
import shutil
import uuid
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


def secure_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.

    - Removes directory components (path separal)
    - Removes potentially dangerous characters
    - Limits length to prevent filesystem issues
    - Falls back to a UUID if filename becomes empty
    """
    # Get only the filename, not any directory components
    filename = Path(filename).name

    # Remove any characters that aren't alphanumeric, dash, underscore, or dot
    # Allow Unicode letters for international filenames
    filename = re.sub(r'[^\w\-.]', '_', filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    # Collapse multiple underscores/dots
    filename = re.sub(r'[_.]+', lambda m: m.group(0)[0], filename)

    # Limit length (preserve extension)
    max_length = 200
    if len(filename) > max_length:
        name_part = Path(filename).stem[:max_length - 10]
        ext_part = Path(filename).suffix[:10]
        filename = f"{name_part}{ext_part}"

    # If filename is empty or just an extension, generate a safe name
    if not filename or filename.startswith('.'):
        filename = f"upload_{uuid.uuid4().hex[:8]}.epub"

    return filename


def _save_upload_file(file_obj, dest_path: Path) -> None:
    """Save uploaded file to disk (blocking, run in executor)."""
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file_obj, buffer)


def _save_upload_file_with_limit(file_obj, dest_path: Path, max_size: int) -> None:
    """Save uploaded file with size limit validation.

    Reads the file in chunks and enforces max size during the read.
    This protects against clients that lie about Content-Length.
    """
    chunk_size = 1024 * 1024  # 1MB chunks
    total_read = 0

    with open(dest_path, "wb") as buffer:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_size:
                # Clean up partial file
                buffer.close()
                dest_path.unlink(missing_ok=True)
                raise ValueError(f"File exceeds maximum size of {max_size // (1024*1024)}MB")
            buffer.write(chunk)


def _move_file(src: str, dst: str) -> None:
    """Move file (blocking, run in executor)."""
    shutil.move(src, dst)


def _delete_file(path: Path) -> None:
    """Delete file if exists (blocking, run in executor)."""
    path.unlink(missing_ok=True)


@router.post("/upload")
async def upload_epub(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an EPUB file and create a new project."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only EPUB files are allowed")

    # Validate file size (check Content-Length header first for early rejection)
    max_size = settings.max_upload_size_mb * 1024 * 1024  # Convert to bytes
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB"
        )

    # Sanitize filename to prevent path traversal
    safe_filename = secure_filename(file.filename)

    # Save to temporary location first (need project_id for final location)
    # Use run_in_executor to avoid blocking the event loop
    # Include a unique ID to prevent collisions
    temp_filename = f"temp_{uuid.uuid4().hex[:8]}_{safe_filename}"
    temp_path = settings.upload_dir / temp_filename
    loop = asyncio.get_event_loop()

    # Read and validate actual file size while saving
    try:
        await loop.run_in_executor(
            None, _save_upload_file_with_limit, file.file, temp_path, max_size
        )
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))

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

        # Move file to project-scoped location (run in executor)
        final_path = ProjectStorage.get_original_epub_path(project.id)
        await loop.run_in_executor(None, _move_file, str(temp_path), str(final_path))

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
        # Clean up temporary file on error (run in executor)
        await loop.run_in_executor(None, _delete_file, temp_path)
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

