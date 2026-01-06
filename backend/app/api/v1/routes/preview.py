"""Preview API routes."""

import mimetypes
import re
import zipfile
from pathlib import Path
from typing import Optional, Any
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Project, Chapter, Paragraph, Translation

router = APIRouter()


def _normalize_image_path(raw_path: str) -> str:
    """Normalize image path from EPUB/URL to zip entry path."""
    from posixpath import normpath

    parsed = urlsplit(raw_path)
    path = unquote(parsed.path or "")
    path = path.lstrip("/")
    path = normpath(path)
    while path.startswith("../"):
        path = path[3:]
    if path.startswith("./"):
        path = path[2:]
    if path == ".":
        return ""
    return path


def _build_toc_with_chapters(
    toc_items: list[dict],
    chapter_map: dict[str, dict],
) -> list[dict]:
    """Build TOC structure with chapter IDs linked by href.

    Also automatically adds split files as children when they exist.
    e.g., part0009_split_000.html -> adds part0009_split_001.html, etc. as children
    """
    result = []

    for item in toc_items:
        href = item.get("href")
        # Remove fragment (e.g., #section1) from href for matching
        base_href = href.split("#")[0] if href else None

        # Find matching chapter by html_path
        chapter_info = chapter_map.get(base_href) if base_href else None

        # Build children from TOC first
        children = _build_toc_with_chapters(
            item.get("children", []),
            chapter_map,
        )

        # If this is a split_000 file with no children, find related split files
        if base_href and "_split_000" in base_href and not children:
            # Find all related split files (split_001, split_002, etc.)
            # e.g., text/part0009_split_000.html -> text/part0009_split_
            import re
            base_pattern = re.sub(r"_split_\d+\.html$", "_split_", base_href)

            related_chapters = []
            for path, info in chapter_map.items():
                # Match same base with different split numbers (not 000)
                if path.startswith(base_pattern) and path != base_href:
                    related_chapters.append((path, info))

            # Sort by split number and add as children
            related_chapters.sort(key=lambda x: x[0])

            # If the parent chapter (split_000) has content paragraphs,
            # add it as "Introduction" before other sections
            if chapter_info and chapter_info.get("paragraph_count", 0) > 0 and related_chapters:
                intro_title = "Introduction"
                children.append({
                    "title": intro_title,
                    "href": base_href,
                    "chapter_id": chapter_info["id"],
                    "chapter_number": chapter_info["chapter_number"],
                    "paragraph_count": chapter_info["paragraph_count"],
                    "children": [],
                    "is_intro": True,
                })

            for path, info in related_chapters:
                children.append({
                    "title": info["title"],
                    "href": path,
                    "chapter_id": info["id"],
                    "chapter_number": info["chapter_number"],
                    "paragraph_count": info["paragraph_count"],
                    "children": [],
                })

        toc_node = {
            "title": item.get("title"),
            "href": href,
            "chapter_id": chapter_info["id"] if chapter_info else None,
            "chapter_number": chapter_info["chapter_number"] if chapter_info else None,
            "paragraph_count": chapter_info["paragraph_count"] if chapter_info else None,
            "children": children,
        }
        result.append(toc_node)

    return result


class UpdateTranslationRequest(BaseModel):
    """Request to manually update a translation."""
    translated_text: str


@router.get("/preview/{project_id}/chapters")
async def get_chapters(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all chapters for a project."""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    return [
        {
            "id": c.id,
            "chapter_number": c.chapter_number,
            "title": c.title,
            "paragraph_count": c.paragraph_count,
            "word_count": c.word_count,
        }
        for c in chapters
    ]


def _collect_toc_hrefs(toc_items: list[dict]) -> set[str]:
    """Collect all hrefs referenced in TOC structure."""
    hrefs = set()
    for item in toc_items:
        href = item.get("href")
        if href:
            # Remove fragment for matching
            base_href = href.split("#")[0]
            hrefs.add(base_href)
        hrefs.update(_collect_toc_hrefs(item.get("children", [])))
    return hrefs


@router.get("/preview/{project_id}/toc")
async def get_toc(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get hierarchical table of contents for a project.

    Returns the original EPUB TOC structure with chapter IDs linked.
    Also includes chapters that exist in spine but not in TOC (like Cover).
    """
    # Get project with TOC structure
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get chapters for mapping
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    # Build chapter map by html_path
    chapter_map = {
        c.html_path: {
            "id": c.id,
            "chapter_number": c.chapter_number,
            "title": c.title,
            "paragraph_count": c.paragraph_count,
            "word_count": c.word_count,
        }
        for c in chapters
    }

    # If no TOC structure stored, return flat chapter list
    if not project.toc_structure:
        return [
            {
                "title": c.title or f"Chapter {c.chapter_number}",
                "href": c.html_path,
                "chapter_id": c.id,
                "chapter_number": c.chapter_number,
                "paragraph_count": c.paragraph_count,
                "children": [],
            }
            for c in chapters
        ]

    # Collect hrefs that are in the TOC (including base patterns for split files)
    toc_hrefs = _collect_toc_hrefs(project.toc_structure)

    # Find the minimum chapter number that's in the TOC
    min_toc_chapter_number = None
    for href in toc_hrefs:
        chapter_info = chapter_map.get(href)
        if chapter_info:
            if min_toc_chapter_number is None or chapter_info["chapter_number"] < min_toc_chapter_number:
                min_toc_chapter_number = chapter_info["chapter_number"]

    # Find chapters that are NOT in the TOC at all (orphaned chapters)
    # These include front matter (Cover) and any content not referenced in TOC
    # Exclude split files (except _split_000) as they're handled by _build_toc_with_chapters
    chapters_not_in_toc = []
    for c in chapters:
        # Skip split files that aren't the base (_split_000)
        # These are added as children by _build_toc_with_chapters
        if re.search(r"_split_\d+\.html$", c.html_path) and "_split_000" not in c.html_path:
            continue
        if c.html_path not in toc_hrefs:
            chapters_not_in_toc.append({
                "title": c.title or f"Chapter {c.chapter_number}",
                "href": c.html_path,
                "chapter_id": c.id,
                "chapter_number": c.chapter_number,
                "paragraph_count": c.paragraph_count,
                "children": [],
            })

    # Sort by chapter number
    chapters_not_in_toc.sort(key=lambda x: x["chapter_number"])

    # Build TOC with chapter IDs linked
    toc_result = _build_toc_with_chapters(project.toc_structure, chapter_map)

    # Split orphaned chapters into before-TOC and after-TOC groups
    chapters_before = [c for c in chapters_not_in_toc if min_toc_chapter_number and c["chapter_number"] < min_toc_chapter_number]
    chapters_after = [c for c in chapters_not_in_toc if min_toc_chapter_number and c["chapter_number"] >= min_toc_chapter_number]

    # Return: chapters before TOC + TOC + chapters after TOC
    return chapters_before + toc_result + chapters_after


@router.get("/preview/{project_id}/chapter/{chapter_id}")
async def get_chapter_content(
    project_id: str,
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get chapter content with translations."""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.project_id == project_id)
        .options(selectinload(Chapter.paragraphs).selectinload(Paragraph.translations))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    paragraphs = []
    for p in sorted(chapter.paragraphs, key=lambda x: x.paragraph_number):
        latest_translation = p.latest_translation
        paragraphs.append({
            "id": p.id,
            "paragraph_number": p.paragraph_number,
            "original_text": p.original_text,
            "html_tag": p.html_tag,
            "translated_text": latest_translation.translated_text if latest_translation else None,
            "translation_id": latest_translation.id if latest_translation else None,
            "translation_provider": latest_translation.provider if latest_translation else None,
            "is_manual_edit": latest_translation.is_manual_edit if latest_translation else False,
        })

    # Format image URLs with API path
    images = []
    for img in (chapter.images or []):
        img_copy = dict(img)
        # Add API URL for fetching the image
        if img_copy.get("src"):
            src = img_copy["src"]
            if src.startswith(("http://", "https://", "data:")):
                img_copy["url"] = src
            else:
                normalized_src = _normalize_image_path(src)
                encoded_src = quote(normalized_src, safe="/")
                img_copy["url"] = f"/api/v1/preview/{project_id}/image/{encoded_src}"
        images.append(img_copy)

    return {
        "id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "paragraphs": paragraphs,
        "images": images,
    }


@router.put("/preview/paragraph/{paragraph_id}")
async def update_translation(
    paragraph_id: str,
    request: UpdateTranslationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually update a paragraph's translation."""
    result = await db.execute(
        select(Paragraph)
        .where(Paragraph.id == paragraph_id)
        .options(selectinload(Paragraph.translations))
    )
    paragraph = result.scalar_one_or_none()
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    # Create new manual translation (keeps version history)
    latest = paragraph.latest_translation
    new_version = (latest.version + 1) if latest else 1

    translation = Translation(
        paragraph_id=paragraph_id,
        translated_text=request.translated_text,
        mode="manual",
        provider="user",
        model="manual",
        version=new_version,
        is_manual_edit=True,
    )
    db.add(translation)
    await db.commit()

    return {"status": "updated", "version": new_version}


@router.get("/preview/paragraph/{paragraph_id}/history")
async def get_translation_history(
    paragraph_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get translation history for a paragraph."""
    result = await db.execute(
        select(Translation)
        .where(Translation.paragraph_id == paragraph_id)
        .order_by(Translation.version.desc())
    )
    translations = result.scalars().all()
    return [
        {
            "id": t.id,
            "version": t.version,
            "translated_text": t.translated_text,
            "provider": t.provider,
            "model": t.model,
            "is_manual_edit": t.is_manual_edit,
            "created_at": t.created_at.isoformat(),
        }
        for t in translations
    ]


@router.get("/preview/{project_id}/image/{image_path:path}")
async def get_image(
    project_id: str,
    image_path: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve an image from the EPUB file.

    The image_path should be the path within the EPUB (e.g., 'images/cover.jpg').
    Handles various path formats including relative paths.
    """
    # Get project to find EPUB file
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    epub_path = Path(project.original_file_path)
    if not epub_path.exists():
        raise HTTPException(status_code=404, detail="EPUB file not found")

    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            # Try to find the image in the EPUB
            # The image_path might be relative or need adjustment
            image_data = None

            # Normalize the path (resolve .. and .)
            normalized_path = _normalize_image_path(image_path)
            if normalized_path.startswith("./"):
                normalized_path = normalized_path[2:]

            # Build list of paths to try
            paths_to_try = [normalized_path] if normalized_path else []
            if normalized_path and not normalized_path.startswith("OEBPS/"):
                paths_to_try.append(f"OEBPS/{normalized_path}")
            if normalized_path and not normalized_path.startswith("OPS/"):
                paths_to_try.append(f"OPS/{normalized_path}")

            # Try each path
            for try_path in paths_to_try:
                try:
                    image_data = zf.read(try_path)
                    break
                except KeyError:
                    continue

            # Try matching by filename only as fallback
            if image_data is None:
                image_name = Path(image_path).name
                # First try exact filename match
                for name in zf.namelist():
                    if name.endswith(f"/{image_name}") or name == image_name:
                        image_data = zf.read(name)
                        break

            # If still not found, try case-insensitive match
            if image_data is None:
                image_name_lower = image_name.lower()
                for name in zf.namelist():
                    if name.lower().endswith(f"/{image_name_lower}") or name.lower() == image_name_lower:
                        image_data = zf.read(name)
                        break

            if image_data is None:
                raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

            # Determine content type
            content_type, _ = mimetypes.guess_type(normalized_path or image_path)
            if not content_type:
                content_type = "application/octet-stream"

            return Response(content=image_data, media_type=content_type)

    except zipfile.BadZipFile:
        raise HTTPException(status_code=500, detail="Invalid EPUB file")
