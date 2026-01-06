"""Export API routes."""

from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.database import get_db, Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.core.epub.generator import EPUBGenerator
from app.core.epub.reconstructor import EPUBReconstructor, BilingualEPUBBuilder, TranslationMapping

router = APIRouter()


class ExportFormat(str, Enum):
    """Export format options."""
    BILINGUAL = "bilingual"      # Original + Translation side by side
    TRANSLATED = "translated"    # Translation only (replaces original)


class ExportRequest(BaseModel):
    """Export request parameters."""
    format: ExportFormat = ExportFormat.BILINGUAL
    target_language: str = "zh"


@router.post("/export/{project_id}")
async def export_bilingual_epub(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export project as bilingual EPUB."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        generator = EPUBGenerator(project_id, db)
        output_path = await generator.generate()

        return FileResponse(
            path=output_path,
            filename=f"{project.name}_bilingual.epub",
            media_type="application/epub+zip",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{project_id}/preview")
async def preview_export(
    project_id: str,
    chapter_id: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Preview exported content (HTML format)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    generator = EPUBGenerator(project_id, db)
    html_content = await generator.generate_preview(chapter_id)

    return {"html": html_content}


@router.post("/export/{project_id}/v2")
async def export_epub_v2(
    project_id: str,
    format: ExportFormat = Query(default=ExportFormat.TRANSLATED),
    target_language: str = Query(default="zh"),
    db: AsyncSession = Depends(get_db),
):
    """Export project as EPUB using V2 reconstructor.

    This endpoint uses XPath-based reconstruction for accurate content replacement.

    Args:
        project_id: Project ID
        format: Export format (bilingual or translated)
        target_language: Target language code

    Returns:
        EPUB file download
    """
    # Load project with all chapters and paragraphs
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.chapters)
            .selectinload(Chapter.paragraphs)
            .selectinload(Paragraph.translations)
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if original file exists
    original_path = Path(project.original_file_path)
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Original EPUB file not found")

    try:
        # Build translation mappings
        translations = []
        for chapter in project.chapters:
            for para in chapter.paragraphs:
                latest = para.latest_translation
                if latest and para.xpath:
                    translations.append(TranslationMapping(
                        file_path=chapter.html_path,
                        xpath=para.xpath,
                        translated_text=latest.translated_text,
                    ))

        if not translations:
            raise HTTPException(
                status_code=400,
                detail="No translations found. Please translate content first."
            )

        # Determine output path
        output_dir = settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if format == ExportFormat.TRANSLATED:
            # Translated only - uses EPUBReconstructor
            output_path = output_dir / f"{project.id}_translated.epub"
            reconstructor = EPUBReconstructor(
                original_epub=original_path,
                translations=translations,
                target_language=target_language,
            )
            reconstructor.build(output_path)
            filename = f"{project.name}_translated.epub"
        else:
            # Bilingual - uses BilingualEPUBBuilder
            output_path = output_dir / f"{project.id}_bilingual_v2.epub"
            builder = BilingualEPUBBuilder(
                original_epub=original_path,
                translations=translations,
                style="stacked",
            )
            builder.build(output_path)
            filename = f"{project.name}_bilingual.epub"

        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/epub+zip",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{project_id}/stats")
async def get_export_stats(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get translation statistics for export readiness.

    Returns counts of:
    - Total paragraphs
    - Translated paragraphs
    - Paragraphs with XPath (for V2 export)
    """
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.chapters)
            .selectinload(Chapter.paragraphs)
            .selectinload(Paragraph.translations)
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    total_paragraphs = 0
    translated_paragraphs = 0
    paragraphs_with_xpath = 0
    v2_ready_paragraphs = 0

    for chapter in project.chapters:
        for para in chapter.paragraphs:
            total_paragraphs += 1
            has_translation = para.latest_translation is not None
            has_xpath = para.xpath is not None

            if has_translation:
                translated_paragraphs += 1
            if has_xpath:
                paragraphs_with_xpath += 1
            if has_translation and has_xpath:
                v2_ready_paragraphs += 1

    return {
        "total_paragraphs": total_paragraphs,
        "translated_paragraphs": translated_paragraphs,
        "translation_progress": translated_paragraphs / total_paragraphs if total_paragraphs > 0 else 0,
        "paragraphs_with_xpath": paragraphs_with_xpath,
        "v2_ready_paragraphs": v2_ready_paragraphs,
        "v2_export_available": paragraphs_with_xpath > 0 and v2_ready_paragraphs > 0,
    }
