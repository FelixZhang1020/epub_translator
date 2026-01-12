"""Export API routes."""

from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
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
from app.core.project_storage import ProjectStorage

router = APIRouter()


class ExportFormat(str, Enum):
    """Export format options."""
    BILINGUAL = "bilingual"      # Original + Translation side by side
    TRANSLATED = "translated"    # Translation only (replaces original)


class HtmlWidth(str, Enum):
    """HTML export width options."""
    NARROW = "narrow"      # 600px - mobile/e-reader friendly
    MEDIUM = "medium"      # 800px - comfortable reading
    WIDE = "wide"          # 1000px - wider screens
    FULL = "full"          # 100% - full width


class ExportRequest(BaseModel):
    """Export request parameters."""
    format: ExportFormat = ExportFormat.BILINGUAL
    target_language: str = "zh"


@router.post("/export/{project_id}")
async def export_bilingual_epub(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export project as bilingual EPUB (legacy method).

    Note: This uses the older EPUBGenerator. Consider using /export/{project_id}/v2 instead.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Ensure exports directory exists
        exports_dir = ProjectStorage.get_exports_dir(project_id)
        exports_dir.mkdir(parents=True, exist_ok=True)

        generator = EPUBGenerator(project_id, db, exports_dir)
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
    chapter_ids: Optional[List[str]] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Export project as EPUB using V2 reconstructor.

    This endpoint uses XPath-based reconstruction for accurate content replacement.

    Args:
        project_id: Project ID
        format: Export format (bilingual or translated)
        target_language: Target language code
        chapter_ids: Optional list of chapter IDs to export (exports all if not specified)

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
        # Build translation mappings (filter by chapter_ids if specified)
        translations = []
        all_paragraphs = []  # For bilingual mode - includes untranslated
        chapter_id_set = set(chapter_ids) if chapter_ids else None
        for chapter in project.chapters:
            # Skip chapters not in the selection
            if chapter_id_set and chapter.id not in chapter_id_set:
                continue
            for para in chapter.paragraphs:
                if not para.xpath:
                    continue
                latest = para.latest_translation
                if latest:
                    translations.append(TranslationMapping(
                        file_path=chapter.html_path,
                        xpath=para.xpath,
                        translated_text=latest.translated_text,
                    ))
                # For bilingual mode, include all paragraphs (translated or not)
                all_paragraphs.append(TranslationMapping(
                    file_path=chapter.html_path,
                    xpath=para.xpath,
                    translated_text=latest.translated_text if latest else "(待翻译)",
                ))

        # Ensure exports directory exists
        exports_dir = ProjectStorage.get_exports_dir(project_id)
        exports_dir.mkdir(parents=True, exist_ok=True)

        if format == ExportFormat.TRANSLATED:
            # Translated only - uses EPUBReconstructor (only translated paragraphs)
            if not translations:
                raise HTTPException(
                    status_code=400,
                    detail="No translations found. Please translate content first."
                )
            output_path = ProjectStorage.get_translated_epub_path(project_id)
            reconstructor = EPUBReconstructor(
                original_epub=original_path,
                translations=translations,
                target_language=target_language,
            )
            reconstructor.build(output_path)
            filename = f"{project.name}_translated.epub"
        else:
            # Bilingual - uses BilingualEPUBBuilder (all paragraphs)
            if not all_paragraphs:
                raise HTTPException(
                    status_code=400,
                    detail="No paragraphs found for export."
                )
            output_path = ProjectStorage.get_bilingual_epub_path(project_id)
            builder = BilingualEPUBBuilder(
                original_epub=original_path,
                translations=all_paragraphs,  # Use all_paragraphs instead of translations
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


@router.post("/export/{project_id}/html")
async def export_html(
    project_id: str,
    chapter_ids: Optional[List[str]] = Query(default=None),
    width: HtmlWidth = Query(default=HtmlWidth.MEDIUM),
    db: AsyncSession = Depends(get_db),
):
    """Export project as HTML file (bilingual format).

    This endpoint generates a standalone HTML file with bilingual content.

    Args:
        project_id: Project ID
        chapter_ids: Optional list of chapter IDs to export (exports all if not specified)
        width: Content width option (narrow/medium/wide/full)

    Returns:
        HTML file download
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        generator = EPUBGenerator(project_id, db)

        # If specific chapters selected, generate HTML for each and combine
        if chapter_ids:
            html_parts = []
            for chapter_id in chapter_ids:
                chapter_html = await generator.generate_preview(chapter_id)
                # Extract body content to avoid multiple html/head tags
                if '<body>' in chapter_html and '</body>' in chapter_html:
                    body_start = chapter_html.index('<body>') + 6
                    body_end = chapter_html.index('</body>')
                    html_parts.append(chapter_html[body_start:body_end])
                else:
                    html_parts.append(chapter_html)

            # Wrap in full HTML structure with width option
            css = generator._get_bilingual_css(width=width.value).decode("utf-8")
            html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project.name} - Bilingual</title>
    <style>{css}</style>
</head>
<body>
    {''.join(html_parts)}
</body>
</html>"""
        else:
            # Export all chapters
            html_content = await generator.generate_preview(width=width.value)

        # Save to file for download
        exports_dir = ProjectStorage.get_exports_dir(project_id)
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = exports_dir / f"{project.name}_bilingual.html"
        output_path.write_text(html_content, encoding="utf-8")

        return FileResponse(
            path=output_path,
            filename=f"{project.name}_bilingual.html",
            media_type="text/html",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
