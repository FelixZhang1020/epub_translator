"""Reference EPUB API routes."""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db, ReferenceEPUB
from app.core.matching.service import matching_service
from app.core.epub.parser import EPUBParser

router = APIRouter()


class ReferenceEPUBResponse(BaseModel):
    """Response model for reference EPUB."""
    id: str
    project_id: str
    filename: str
    language: str
    epub_title: Optional[str]
    epub_author: Optional[str]
    total_chapters: int
    total_paragraphs: int
    auto_matched: bool
    match_quality: Optional[float]
    created_at: str


class MatchResponse(BaseModel):
    """Response model for paragraph match."""
    id: str
    source_paragraph_id: str
    source_text: Optional[str]
    reference_text: str
    match_type: str
    confidence: Optional[float]
    user_verified: bool
    user_corrected: bool


class UpdateMatchRequest(BaseModel):
    """Request model for updating a match."""
    reference_text: str


class MatchingStatsResponse(BaseModel):
    """Response model for matching statistics."""
    matched: int
    unmatched: int
    average_confidence: float


class ReferenceChapterResponse(BaseModel):
    """Response model for a reference chapter."""
    chapter_number: int
    title: Optional[str]
    paragraph_count: int


class ReferenceChapterContentResponse(BaseModel):
    """Response model for reference chapter content."""
    chapter_number: int
    title: Optional[str]
    paragraphs: list[dict]  # List of {paragraph_number, text}


class SearchResultItem(BaseModel):
    """Response model for a search result item."""
    chapter_number: int
    chapter_title: Optional[str]
    paragraph_number: int
    text: str
    match_start: int  # Start position of match in text
    match_end: int    # End position of match in text


class SearchResponse(BaseModel):
    """Response model for search results."""
    query: str
    total_results: int
    results: list[SearchResultItem]


@router.post("/reference/{project_id}/upload")
async def upload_reference_epub(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ReferenceEPUBResponse:
    """Upload a Chinese reference EPUB file."""
    # Validate file type
    if not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only EPUB files are allowed")

    # Save file
    file_path = settings.upload_dir / f"ref_{project_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        reference = await matching_service.upload_reference_epub(
            db=db,
            project_id=project_id,
            file_path=file_path,
            filename=file.filename,
        )
        return ReferenceEPUBResponse(
            id=reference.id,
            project_id=reference.project_id,
            filename=reference.filename,
            language=reference.language,
            epub_title=reference.epub_title,
            epub_author=reference.epub_author,
            total_chapters=reference.total_chapters,
            total_paragraphs=reference.total_paragraphs,
            auto_matched=reference.auto_matched,
            match_quality=reference.match_quality,
            created_at=reference.created_at.isoformat(),
        )
    except ValueError as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/reference/{project_id}")
async def get_reference_epub(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReferenceEPUBResponse:
    """Get reference EPUB info for a project."""
    result = await db.execute(
        select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
    )
    reference = result.scalar_one_or_none()
    if not reference:
        raise HTTPException(status_code=404, detail="No reference EPUB found")

    return ReferenceEPUBResponse(
        id=reference.id,
        project_id=reference.project_id,
        filename=reference.filename,
        language=reference.language,
        epub_title=reference.epub_title,
        epub_author=reference.epub_author,
        total_chapters=reference.total_chapters,
        total_paragraphs=reference.total_paragraphs,
        auto_matched=reference.auto_matched,
        match_quality=reference.match_quality,
        created_at=reference.created_at.isoformat(),
    )


@router.post("/reference/{project_id}/match")
async def auto_match_paragraphs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> MatchingStatsResponse:
    """Trigger automatic paragraph matching."""
    try:
        stats = await matching_service.auto_match_paragraphs(db, project_id)
        return MatchingStatsResponse(**stats)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.get("/reference/{project_id}/matches")
async def get_matches(
    project_id: str,
    chapter_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MatchResponse]:
    """Get paragraph matches for a project."""
    matches = await matching_service.get_matches(
        db=db,
        project_id=project_id,
        chapter_id=chapter_id,
        limit=limit,
        offset=offset,
    )
    return [MatchResponse(**m) for m in matches]


@router.put("/reference/{project_id}/match/{match_id}")
async def update_match(
    project_id: str,
    match_id: str,
    request: UpdateMatchRequest,
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """Update a match with corrected reference text."""
    try:
        match = await matching_service.update_match(
            db=db,
            match_id=match_id,
            reference_text=request.reference_text,
        )
        return MatchResponse(
            id=match.id,
            source_paragraph_id=match.source_paragraph_id,
            source_text=None,  # Not loaded in update
            reference_text=match.reference_text,
            match_type=match.match_type,
            confidence=match.confidence,
            user_verified=match.user_verified,
            user_corrected=match.user_corrected,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reference/{project_id}/match/{match_id}/verify")
async def verify_match(
    project_id: str,
    match_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark a match as user-verified."""
    try:
        match = await matching_service.verify_match(db, match_id)
        return {"status": "verified", "match_id": match.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/reference/{project_id}")
async def delete_reference(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete reference EPUB and all matches."""
    await matching_service.delete_reference(db, project_id)
    return {"status": "deleted"}


@router.get("/reference/{project_id}/chapters")
async def get_reference_chapters(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ReferenceChapterResponse]:
    """Get list of chapters from reference EPUB."""
    result = await db.execute(
        select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
    )
    reference = result.scalar_one_or_none()
    if not reference:
        raise HTTPException(status_code=404, detail="No reference EPUB found")

    # Parse reference EPUB to get chapters
    try:
        parser = EPUBParser(Path(reference.file_path))
        chapters = await parser.extract_chapters()

        return [
            ReferenceChapterResponse(
                chapter_number=ch.get("chapter_number", i + 1),
                title=ch.get("title"),
                paragraph_count=len(ch.get("paragraphs", [])),
            )
            for i, ch in enumerate(chapters)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse reference EPUB: {str(e)}")


@router.get("/reference/{project_id}/chapter/{chapter_number}")
async def get_reference_chapter_content(
    project_id: str,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
) -> ReferenceChapterContentResponse:
    """Get content of a specific chapter from reference EPUB."""
    result = await db.execute(
        select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
    )
    reference = result.scalar_one_or_none()
    if not reference:
        raise HTTPException(status_code=404, detail="No reference EPUB found")

    # Parse reference EPUB to get chapters
    try:
        parser = EPUBParser(Path(reference.file_path))
        chapters = await parser.extract_chapters()

        # Find the chapter by number (use index+1 as fallback, consistent with get_reference_chapters)
        for i, ch in enumerate(chapters):
            ch_num = ch.get("chapter_number", i + 1)
            if ch_num == chapter_number:
                paragraphs = [
                    {
                        "paragraph_number": j + 1,
                        "text": p.get("original_text", ""),
                    }
                    for j, p in enumerate(ch.get("paragraphs", []))
                ]
                return ReferenceChapterContentResponse(
                    chapter_number=chapter_number,
                    title=ch.get("title"),
                    paragraphs=paragraphs,
                )

        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse reference EPUB: {str(e)}")


@router.get("/reference/{project_id}/search")
async def search_reference_content(
    project_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search for content in reference EPUB paragraphs."""
    result = await db.execute(
        select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
    )
    reference = result.scalar_one_or_none()
    if not reference:
        raise HTTPException(status_code=404, detail="No reference EPUB found")

    try:
        parser = EPUBParser(Path(reference.file_path))
        chapters = await parser.extract_chapters()

        # Search through all chapters and paragraphs
        results: list[SearchResultItem] = []
        query_lower = q.lower()

        for idx, ch in enumerate(chapters):
            # Use index+1 as fallback, consistent with get_reference_chapters
            chapter_number = ch.get("chapter_number", idx + 1)
            chapter_title = ch.get("title")
            paragraphs = ch.get("paragraphs", [])

            for i, para in enumerate(paragraphs):
                text = para.get("original_text", "")
                text_lower = text.lower()

                # Find match position
                match_pos = text_lower.find(query_lower)
                if match_pos != -1:
                    results.append(SearchResultItem(
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        paragraph_number=i + 1,
                        text=text,
                        match_start=match_pos,
                        match_end=match_pos + len(q),
                    ))

                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        return SearchResponse(
            query=q,
            total_results=len(results),
            results=results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
