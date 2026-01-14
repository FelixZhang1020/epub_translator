"""Export API routes."""

from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.core.epub.generator import EPUBGenerator
from app.core.epub.reconstructor import EPUBReconstructor, BilingualEPUBBuilder, TranslationMapping
from app.core.project_storage import ProjectStorage
from app.api.dependencies import ValidatedProject

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


class PaperSize(str, Enum):
    """PDF paper size options."""
    A4 = "A4"
    LETTER = "Letter"


class ExportRequest(BaseModel):
    """Export request parameters."""
    format: ExportFormat = ExportFormat.BILINGUAL
    target_language: str = "zh"


@router.post("/export/{project_id}")
async def export_bilingual_epub(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Export project as bilingual EPUB (legacy method).

    Note: This uses the older EPUBGenerator. Consider using /export/{project_id}/v2 instead.
    """
    project_id = project.id

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
    project: ValidatedProject,
    chapter_id: Optional[str] = None,
    chapter_ids: Optional[List[str]] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Preview exported content (HTML format).

    This preview filters out copyright content and removes images
    to comply with copyright requirements.
    
    Args:
        chapter_id: Single chapter ID for ePub-style single chapter preview
        chapter_ids: Multiple chapter IDs for PDF/HTML-style filtered preview
    """
    generator = EPUBGenerator(project.id, db)
    
    # If single chapter_id is specified, use it directly
    if chapter_id:
        html_content = await generator.generate_preview(
            chapter_id,
            strip_images=True,
            filter_copyright=True,
        )
        return {"html": html_content}
    
    # If multiple chapter_ids specified, generate HTML for each and combine
    if chapter_ids:
        html_parts = []
        for ch_id in chapter_ids:
            chapter_html = await generator.generate_preview(
                ch_id,
                strip_images=True,
                filter_copyright=True,
            )
            # Extract body content to avoid multiple html/head tags
            if '<body>' in chapter_html and '</body>' in chapter_html:
                body_start = chapter_html.index('<body>') + 6
                body_end = chapter_html.index('</body>')
                html_parts.append(chapter_html[body_start:body_end])
            else:
                html_parts.append(chapter_html)
        
        # Wrap in full HTML structure
        css = generator._get_bilingual_css().decode("utf-8")
        html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project.name} - Preview</title>
    <style>{css}</style>
</head>
<body>
    {''.join(html_parts)}
</body>
</html>"""
        return {"html": html_content}
    
    # No chapter filter - generate all chapters preview
    html_content = await generator.generate_preview(
        strip_images=True,
        filter_copyright=True,
    )

    return {"html": html_content}


@router.post("/export/{project_id}/v2")
async def export_epub_v2(
    validated_project: ValidatedProject,
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
    project_id = validated_project.id

    # Load project with all chapters and paragraphs (eager loading)
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.chapters)
            .selectinload(Chapter.paragraphs)
            .selectinload(Paragraph.translations)
        )
    )
    project = result.scalar_one()

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
                    translated_text=latest.translated_text if latest else "(pending)",
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
                strip_images=True,  # Remove images for copyright compliance
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
                strip_images=True,  # Remove images for copyright compliance
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
    validated_project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
):
    """Get translation statistics for export readiness.

    Returns counts of:
    - Total paragraphs
    - Translated paragraphs
    - Paragraphs with XPath (for V2 export)
    """
    # Load project with eager loading for stats calculation
    result = await db.execute(
        select(Project)
        .where(Project.id == validated_project.id)
        .options(
            selectinload(Project.chapters)
            .selectinload(Chapter.paragraphs)
            .selectinload(Paragraph.translations)
        )
    )
    project = result.scalar_one()

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
    project: ValidatedProject,
    chapter_ids: Optional[List[str]] = Query(default=None),
    width: HtmlWidth = Query(default=HtmlWidth.MEDIUM),
    db: AsyncSession = Depends(get_db),
):
    """Export project as HTML file (bilingual format).

    This endpoint generates a standalone HTML file with bilingual content.
    Images are removed for copyright compliance.

    Args:
        project_id: Project ID
        chapter_ids: Optional list of chapter IDs to export (exports all if not specified)
        width: Content width option (narrow/medium/wide/full)

    Returns:
        HTML file download
    """
    project_id = project.id

    try:
        generator = EPUBGenerator(project_id, db)

        # If specific chapters selected, generate HTML for each and combine
        if chapter_ids:
            html_parts = []
            for chapter_id in chapter_ids:
                chapter_html = await generator.generate_preview(
                    chapter_id,
                    strip_images=True,
                    filter_copyright=True,
                )
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
            html_content = await generator.generate_preview(
                width=width.value,
                strip_images=True,
                filter_copyright=True,
            )

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


# =============================================================================
# Text-Only Exports (Copyright Compliant)
# =============================================================================


@router.post("/export/{project_id}/text-epub")
async def export_text_only_epub(
    project: ValidatedProject,
    format: ExportFormat = Query(default=ExportFormat.BILINGUAL),
    chapter_ids: Optional[List[str]] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Export project as text-only ePub (no images, minimal formatting).

    This endpoint generates a copyright-compliant ePub with text content only.
    All images and complex formatting are stripped.

    Args:
        project_id: Project ID
        format: Export format (bilingual or translated)
        chapter_ids: Optional list of chapter IDs to export

    Returns:
        ePub file download
    """
    from app.core.export import TextContentExtractor, TextOnlyEpubGenerator

    try:
        # Extract text content
        extractor = TextContentExtractor()
        content = await extractor.extract(
            db=db,
            project_id=project.id,
            chapter_ids=chapter_ids,
            include_untranslated=(format == ExportFormat.BILINGUAL),
        )

        if not content.chapters:
            raise HTTPException(
                status_code=400,
                detail="No content found for export."
            )

        # Generate ePub
        generator = TextOnlyEpubGenerator()
        epub_bytes = generator.generate(
            content=content,
            mode=format.value,
        )

        # Save to file for download
        exports_dir = ProjectStorage.get_exports_dir(project.id)
        exports_dir.mkdir(parents=True, exist_ok=True)
        suffix = "bilingual" if format == ExportFormat.BILINGUAL else "translated"
        output_path = exports_dir / f"{project.name}_text_{suffix}.epub"
        output_path.write_bytes(epub_bytes)

        return FileResponse(
            path=output_path,
            filename=f"{project.name}_text_{suffix}.epub",
            media_type="application/epub+zip",
        )

    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/{project_id}/pdf")
async def export_pdf(
    project: ValidatedProject,
    format: ExportFormat = Query(default=ExportFormat.BILINGUAL),
    paper_size: PaperSize = Query(default=PaperSize.A4),
    chapter_ids: Optional[List[str]] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Export project as PDF (text and TOC only).

    This endpoint generates a copyright-compliant PDF with text content only.
    Uses ReportLab (pure Python, no system dependencies).

    Args:
        project_id: Project ID
        format: Export format (bilingual or translated)
        paper_size: Paper size (A4 or Letter)
        chapter_ids: Optional list of chapter IDs to export

    Returns:
        PDF file download
    """
    from app.core.export import TextContentExtractor, PdfGenerator

    try:
        # Extract text content
        extractor = TextContentExtractor()
        content = await extractor.extract(
            db=db,
            project_id=project.id,
            chapter_ids=chapter_ids,
            include_untranslated=(format == ExportFormat.BILINGUAL),
        )

        if not content.chapters:
            raise HTTPException(
                status_code=400,
                detail="No content found for export."
            )

        # Generate PDF
        generator = PdfGenerator()
        pdf_bytes = generator.generate(
            content=content,
            mode=format.value,
            paper_size=paper_size.value,
        )

        # Save to file for download
        exports_dir = ProjectStorage.get_exports_dir(project.id)
        exports_dir.mkdir(parents=True, exist_ok=True)
        suffix = "bilingual" if format == ExportFormat.BILINGUAL else "translated"
        output_path = exports_dir / f"{project.name}_{suffix}.pdf"
        output_path.write_bytes(pdf_bytes)

        return FileResponse(
            path=output_path,
            filename=f"{project.name}_{suffix}.pdf",
            media_type="application/pdf",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/{project_id}/text-html")
async def export_text_only_html(
    project: ValidatedProject,
    format: ExportFormat = Query(default=ExportFormat.BILINGUAL),
    chapter_ids: Optional[List[str]] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Export project as text-only HTML (no images).

    This endpoint generates a copyright-compliant HTML with text content only.

    Args:
        project_id: Project ID
        format: Export format (bilingual or translated)
        chapter_ids: Optional list of chapter IDs to export

    Returns:
        HTML file download
    """
    from app.core.export import TextContentExtractor, TextOnlyHtmlGenerator

    try:
        # Extract text content
        extractor = TextContentExtractor()
        content = await extractor.extract(
            db=db,
            project_id=project.id,
            chapter_ids=chapter_ids,
            include_untranslated=(format == ExportFormat.BILINGUAL),
        )

        if not content.chapters:
            raise HTTPException(
                status_code=400,
                detail="No content found for export."
            )

        # Generate HTML
        generator = TextOnlyHtmlGenerator()
        html_bytes = generator.generate_bytes(
            content=content,
            mode=format.value,
        )

        # Save to file for download
        exports_dir = ProjectStorage.get_exports_dir(project.id)
        exports_dir.mkdir(parents=True, exist_ok=True)
        suffix = "bilingual" if format == ExportFormat.BILINGUAL else "translated"
        output_path = exports_dir / f"{project.name}_text_{suffix}.html"
        output_path.write_bytes(html_bytes)

        return FileResponse(
            path=output_path,
            filename=f"{project.name}_text_{suffix}.html",
            media_type="text/html",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
