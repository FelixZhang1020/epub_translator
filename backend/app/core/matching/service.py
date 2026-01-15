"""Reference EPUB Matching Service - Match EN and CN paragraphs."""

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.database import Project, ReferenceEPUB, ParagraphMatch
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.core.epub import EPUBParser
from app.core.matching.smart_matcher import SmartMatcher


class MatchingService:
    """Service for matching paragraphs between English and Chinese EPUBs."""

    async def upload_reference_epub(
        self,
        db: AsyncSession,
        project_id: str,
        file_path: Path,
        filename: str,
    ) -> ReferenceEPUB:
        """Upload and parse a Chinese reference EPUB.

        Args:
            db: Database session
            project_id: Project ID
            file_path: Path to uploaded file
            filename: Original filename

        Returns:
            ReferenceEPUB record
        """
        # Get project
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Remove existing reference if any
        await db.execute(
            delete(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
        )
        await db.execute(
            delete(ParagraphMatch).where(ParagraphMatch.project_id == project_id)
        )

        # Parse reference EPUB
        parser = EPUBParser(file_path)
        metadata = await parser.get_metadata()
        chapters = await parser.extract_chapters()

        # Count totals
        total_chapters = len(chapters)
        total_paragraphs = sum(len(ch.get("paragraphs", [])) for ch in chapters)

        # Create reference EPUB record
        reference = ReferenceEPUB(
            id=str(uuid.uuid4()),
            project_id=project_id,
            filename=filename,
            file_path=str(file_path),
            language="zh",
            epub_title=metadata.get("title"),
            epub_author=metadata.get("author"),
            total_chapters=total_chapters,
            total_paragraphs=total_paragraphs,
        )
        db.add(reference)

        # Update project
        project.has_reference_epub = True

        # Store parsed chapters data for matching
        # We'll store this temporarily in memory for the matching step
        self._reference_chapters = chapters

        await db.commit()
        await db.refresh(reference)
        return reference

    async def auto_match_paragraphs(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> dict:
        """Automatically match paragraphs between EN and CN EPUBs.

        Uses smart matching algorithm that handles different chapter structures
        between source and reference EPUBs.

        Args:
            db: Database session
            project_id: Project ID

        Returns:
            Dict with matching statistics
        """
        # Get reference EPUB
        result = await db.execute(
            select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
        )
        reference = result.scalar_one_or_none()
        if not reference:
            raise ValueError(f"No reference EPUB found for project {project_id}")

        # Parse reference EPUB to get chapters
        parser = EPUBParser(Path(reference.file_path))
        ref_chapters = await parser.extract_chapters()

        # Get source chapters with paragraphs
        result = await db.execute(
            select(Chapter)
            .options(selectinload(Chapter.paragraphs))
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
        )
        source_chapters = result.scalars().all()

        # Clear existing matches
        await db.execute(
            delete(ParagraphMatch).where(ParagraphMatch.project_id == project_id)
        )

        # Flatten all paragraphs for smart matching
        source_paragraphs = []
        for ch_idx, chapter in enumerate(source_chapters):
            for para in sorted(chapter.paragraphs, key=lambda p: p.paragraph_number):
                source_paragraphs.append({
                    'id': para.id,
                    'text': para.original_text,
                    'chapter_index': ch_idx,
                    'paragraph_index': para.paragraph_number,
                    'html_tag': para.html_tag,
                })

        reference_paragraphs = []
        for ch_idx, chapter in enumerate(ref_chapters):
            for para_idx, para in enumerate(chapter.get("paragraphs", [])):
                reference_paragraphs.append({
                    'id': f"ref_{ch_idx}_{para_idx}",
                    'text': para.get("original_text", ""),
                    'chapter_index': ch_idx,
                    'paragraph_index': para_idx,
                    'html_tag': para.get("html_tag", "p"),
                })

        # Use smart matcher
        matcher = SmartMatcher(source_paragraphs, reference_paragraphs)
        match_results = matcher.match_all()

        # Save matches to database
        matched_count = 0
        total_confidence = 0.0

        for match_result in match_results:
            match = ParagraphMatch(
                id=str(uuid.uuid4()),
                project_id=project_id,
                source_paragraph_id=match_result.source_paragraph_id,
                reference_text=match_result.reference_text,
                reference_chapter_index=match_result.reference_chapter_index,
                reference_paragraph_index=match_result.reference_paragraph_index,
                match_type="smart",
                confidence=match_result.confidence,
            )
            db.add(match)
            matched_count += 1
            total_confidence += match_result.confidence

        # Calculate unmatched
        total_source = len(source_paragraphs)
        unmatched_count = total_source - matched_count

        # Update reference EPUB stats
        reference.auto_matched = True
        if matched_count > 0:
            reference.match_quality = total_confidence / matched_count

        await db.commit()

        return {
            "matched": matched_count,
            "unmatched": unmatched_count,
            "average_confidence": total_confidence / matched_count if matched_count > 0 else 0,
        }

    async def get_matches(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get paragraph matches for a project.

        Args:
            db: Database session
            project_id: Project ID
            chapter_id: Optional chapter ID to filter
            limit: Max results
            offset: Pagination offset

        Returns:
            List of match dicts with source and reference info
        """
        query = (
            select(ParagraphMatch)
            .options(selectinload(ParagraphMatch.source_paragraph))
            .where(ParagraphMatch.project_id == project_id)
        )

        if chapter_id:
            # Filter by chapter
            query = query.join(
                Paragraph, ParagraphMatch.source_paragraph_id == Paragraph.id
            ).where(Paragraph.chapter_id == chapter_id)

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        matches = result.scalars().all()

        return [
            {
                "id": m.id,
                "source_paragraph_id": m.source_paragraph_id,
                "source_text": m.source_paragraph.original_text if m.source_paragraph else None,
                "reference_text": m.reference_text,
                "match_type": m.match_type,
                "confidence": m.confidence,
                "user_verified": m.user_verified,
                "user_corrected": m.user_corrected,
            }
            for m in matches
        ]

    async def update_match(
        self,
        db: AsyncSession,
        match_id: str,
        reference_text: str,
    ) -> ParagraphMatch:
        """Update a match with corrected reference text.

        Args:
            db: Database session
            match_id: Match ID
            reference_text: Corrected reference text

        Returns:
            Updated ParagraphMatch
        """
        result = await db.execute(
            select(ParagraphMatch).where(ParagraphMatch.id == match_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            raise ValueError(f"Match {match_id} not found")

        match.reference_text = reference_text
        match.user_corrected = True
        match.match_type = "manual"
        match.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(match)
        return match

    async def verify_match(
        self,
        db: AsyncSession,
        match_id: str,
    ) -> ParagraphMatch:
        """Mark a match as user-verified.

        Args:
            db: Database session
            match_id: Match ID

        Returns:
            Updated ParagraphMatch
        """
        result = await db.execute(
            select(ParagraphMatch).where(ParagraphMatch.id == match_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            raise ValueError(f"Match {match_id} not found")

        match.user_verified = True
        match.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(match)
        return match

    async def delete_reference(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> None:
        """Delete reference EPUB and all matches.

        Args:
            db: Database session
            project_id: Project ID
        """
        # Get reference to delete file
        result = await db.execute(
            select(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
        )
        reference = result.scalar_one_or_none()

        if reference:
            # Delete file
            Path(reference.file_path).unlink(missing_ok=True)

            # Delete matches
            await db.execute(
                delete(ParagraphMatch).where(ParagraphMatch.project_id == project_id)
            )

            # Delete reference
            await db.execute(
                delete(ReferenceEPUB).where(ReferenceEPUB.project_id == project_id)
            )

            # Update project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if project:
                project.has_reference_epub = False

            await db.commit()


# Global service instance
matching_service = MatchingService()

