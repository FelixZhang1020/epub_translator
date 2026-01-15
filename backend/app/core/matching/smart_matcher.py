"""Smart Reference Matching Service - Intelligent paragraph alignment.

Uses multiple strategies to match paragraphs between source and reference EPUBs:
1. Feature extraction (numbers, proper nouns, punctuation patterns)
2. Length ratio analysis
3. Anchor point detection
4. Dynamic programming alignment
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional
from difflib import SequenceMatcher


@dataclass
class ParagraphFeatures:
    """Extracted features from a paragraph for matching."""
    text: str
    paragraph_id: str
    chapter_index: int
    paragraph_index: int
    global_index: int  # Index across all paragraphs

    # Features
    char_count: int
    word_count: int
    numbers: list[str]  # All numbers found in text
    quotes: list[str]  # Quoted text
    capitalized_words: list[str]  # Proper nouns
    punctuation_pattern: str  # Simplified punctuation pattern
    is_heading: bool

    @classmethod
    def from_text(
        cls,
        text: str,
        paragraph_id: str,
        chapter_index: int,
        paragraph_index: int,
        global_index: int,
        html_tag: str = "p"
    ) -> "ParagraphFeatures":
        """Extract features from paragraph text."""
        # Basic counts
        char_count = len(text)
        word_count = len(text.split())

        # Extract numbers (years, chapter numbers, verse numbers, etc.)
        numbers = re.findall(r'\d+(?:\.\d+)?', text)

        # Extract quoted text
        quotes = re.findall(r'[""「」『』《》]([^""「」『』《》]+)[""「」『』《》]', text)

        # Extract capitalized words (potential proper nouns)
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', text)

        # Create punctuation pattern (simplified)
        punct_pattern = ''.join(
            c for c in text if unicodedata.category(c).startswith('P')
        )[:20]  # First 20 punctuation chars

        # Check if heading
        is_heading = html_tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')

        return cls(
            text=text,
            paragraph_id=paragraph_id,
            chapter_index=chapter_index,
            paragraph_index=paragraph_index,
            global_index=global_index,
            char_count=char_count,
            word_count=word_count,
            numbers=numbers,
            quotes=quotes,
            capitalized_words=capitalized,
            punctuation_pattern=punct_pattern,
            is_heading=is_heading,
        )


@dataclass
class MatchResult:
    """Result of matching a source paragraph to reference."""
    source_paragraph_id: str
    reference_text: str
    reference_chapter_index: int
    reference_paragraph_index: int
    confidence: float
    match_reasons: list[str]


class SmartMatcher:
    """Intelligent paragraph matcher using multiple strategies."""

    # Expected Chinese/English character ratio
    # Chinese is typically 0.3-0.7x the length of English
    EXPECTED_RATIO_MIN = 0.25
    EXPECTED_RATIO_MAX = 0.85

    def __init__(
        self,
        source_paragraphs: list[dict],
        reference_paragraphs: list[dict],
    ):
        """Initialize with source and reference paragraphs.

        Args:
            source_paragraphs: List of dicts with 'id', 'text', 'chapter_index',
                              'paragraph_index', 'html_tag'
            reference_paragraphs: List of dicts with same structure
        """
        # Extract features for all paragraphs
        self.source_features = [
            ParagraphFeatures.from_text(
                text=p['text'],
                paragraph_id=p['id'],
                chapter_index=p['chapter_index'],
                paragraph_index=p['paragraph_index'],
                global_index=i,
                html_tag=p.get('html_tag', 'p'),
            )
            for i, p in enumerate(source_paragraphs)
        ]

        self.reference_features = [
            ParagraphFeatures.from_text(
                text=p['text'],
                paragraph_id=p['id'],
                chapter_index=p['chapter_index'],
                paragraph_index=p['paragraph_index'],
                global_index=i,
                html_tag=p.get('html_tag', 'p'),
            )
            for i, p in enumerate(reference_paragraphs)
        ]

        self.source_count = len(self.source_features)
        self.reference_count = len(self.reference_features)

    def calculate_similarity(
        self,
        source: ParagraphFeatures,
        reference: ParagraphFeatures,
    ) -> tuple[float, list[str]]:
        """Calculate similarity score between source and reference paragraph.

        Returns:
            Tuple of (score 0-1, list of match reasons)
        """
        score = 0.0
        reasons = []
        weights_sum = 0.0

        # 1. Length ratio score (weight: 2.0)
        weight = 2.0
        weights_sum += weight
        if source.char_count > 0 and reference.char_count > 0:
            ratio = reference.char_count / source.char_count
            if self.EXPECTED_RATIO_MIN <= ratio <= self.EXPECTED_RATIO_MAX:
                # Perfect ratio around 0.5
                ratio_score = 1.0 - abs(ratio - 0.5) / 0.35
                score += weight * max(0, ratio_score)
                if ratio_score > 0.7:
                    reasons.append(f"length_ratio:{ratio:.2f}")

        # 2. Number matching (weight: 3.0) - very strong signal
        weight = 3.0
        weights_sum += weight
        if source.numbers and reference.numbers:
            # Check how many numbers match
            source_nums = set(source.numbers)
            ref_nums = set(reference.numbers)
            if source_nums & ref_nums:
                match_ratio = len(source_nums & ref_nums) / max(len(source_nums), len(ref_nums))
                score += weight * match_ratio
                if match_ratio > 0.5:
                    matched = source_nums & ref_nums
                    reasons.append(f"numbers:{','.join(list(matched)[:3])}")

        # 3. Relative position score (weight: 1.5)
        weight = 1.5
        weights_sum += weight
        if self.source_count > 1 and self.reference_count > 1:
            source_pos = source.global_index / (self.source_count - 1)
            ref_pos = reference.global_index / (self.reference_count - 1)
            pos_diff = abs(source_pos - ref_pos)
            if pos_diff < 0.1:
                pos_score = 1.0 - (pos_diff / 0.1)
                score += weight * pos_score
                if pos_score > 0.7:
                    reasons.append(f"position:{source_pos:.2f}~{ref_pos:.2f}")

        # 4. Heading matching (weight: 1.0)
        weight = 1.0
        weights_sum += weight
        if source.is_heading and reference.is_heading:
            score += weight
            reasons.append("both_headings")
        elif source.is_heading != reference.is_heading:
            # Penalty for heading mismatch
            score -= weight * 0.5

        # 5. Quote similarity (weight: 2.0)
        weight = 2.0
        weights_sum += weight
        if source.quotes and reference.quotes:
            # Check if any quotes have similar length patterns
            for sq in source.quotes:
                for rq in reference.quotes:
                    # Chinese quote should be shorter
                    ratio = len(rq) / len(sq) if len(sq) > 0 else 0
                    if 0.3 <= ratio <= 0.8:
                        score += weight * 0.5
                        reasons.append("quote_match")
                        break

        # 6. Capitalized word matching (weight: 2.0) - proper nouns often transliterated
        weight = 2.0
        weights_sum += weight
        if source.capitalized_words:
            # Check if any English proper nouns appear in Chinese text
            for word in source.capitalized_words:
                if word.lower() in reference.text.lower():
                    score += weight
                    reasons.append(f"proper_noun:{word}")
                    break

        # Normalize score
        final_score = min(1.0, max(0.0, score / weights_sum))

        return final_score, reasons

    def find_anchors(self, threshold: float = 0.7) -> list[tuple[int, int, float]]:
        """Find high-confidence anchor points for alignment.

        Returns:
            List of (source_index, reference_index, confidence) tuples
        """
        anchors = []

        # For each source paragraph, find best matching reference
        for s_idx, source in enumerate(self.source_features):
            best_score = 0.0
            best_ref_idx = -1
            best_reasons = []

            # Search in a window around expected position
            expected_ref_idx = int(s_idx * self.reference_count / self.source_count)
            window_size = max(50, self.reference_count // 4)

            start_idx = max(0, expected_ref_idx - window_size)
            end_idx = min(self.reference_count, expected_ref_idx + window_size)

            for r_idx in range(start_idx, end_idx):
                reference = self.reference_features[r_idx]
                score, reasons = self.calculate_similarity(source, reference)

                if score > best_score:
                    best_score = score
                    best_ref_idx = r_idx
                    best_reasons = reasons

            if best_score >= threshold and best_ref_idx >= 0:
                anchors.append((s_idx, best_ref_idx, best_score))

        # Filter to keep only consistent anchors (monotonically increasing)
        filtered = self._filter_monotonic_anchors(anchors)

        return filtered

    def _filter_monotonic_anchors(
        self,
        anchors: list[tuple[int, int, float]]
    ) -> list[tuple[int, int, float]]:
        """Keep only anchors that form a monotonically increasing sequence."""
        if not anchors:
            return []

        # Sort by source index
        sorted_anchors = sorted(anchors, key=lambda x: x[0])

        # Use LIS (Longest Increasing Subsequence) on reference indices
        n = len(sorted_anchors)
        dp = [1] * n
        parent = [-1] * n

        for i in range(1, n):
            for j in range(i):
                if sorted_anchors[j][1] < sorted_anchors[i][1]:
                    if dp[j] + 1 > dp[i]:
                        dp[i] = dp[j] + 1
                        parent[i] = j

        # Reconstruct LIS
        max_len = max(dp)
        max_idx = dp.index(max_len)

        result = []
        idx = max_idx
        while idx != -1:
            result.append(sorted_anchors[idx])
            idx = parent[idx]

        return list(reversed(result))

    def align_between_anchors(
        self,
        source_start: int,
        source_end: int,
        ref_start: int,
        ref_end: int,
    ) -> list[MatchResult]:
        """Align paragraphs between two anchor points using DP.

        Uses a simplified DTW-like algorithm to find best alignment.
        """
        results = []

        source_range = list(range(source_start, source_end))
        ref_range = list(range(ref_start, ref_end))

        if not source_range or not ref_range:
            return results

        m, n = len(source_range), len(ref_range)

        # Build similarity matrix
        sim_matrix = []
        for s_idx in source_range:
            row = []
            for r_idx in ref_range:
                score, reasons = self.calculate_similarity(
                    self.source_features[s_idx],
                    self.reference_features[r_idx]
                )
                row.append((score, reasons))
            sim_matrix.append(row)

        # Simple greedy assignment (could use Hungarian algorithm for better results)
        used_refs = set()

        for i, s_idx in enumerate(source_range):
            best_score = 0.0
            best_j = -1
            best_reasons = []

            for j, r_idx in enumerate(ref_range):
                if j in used_refs:
                    continue
                score, reasons = sim_matrix[i][j]
                if score > best_score:
                    best_score = score
                    best_j = j
                    best_reasons = reasons

            if best_j >= 0 and best_score > 0.3:
                used_refs.add(best_j)
                r_idx = ref_range[best_j]
                ref_feat = self.reference_features[r_idx]
                source_feat = self.source_features[s_idx]

                results.append(MatchResult(
                    source_paragraph_id=source_feat.paragraph_id,
                    reference_text=ref_feat.text,
                    reference_chapter_index=ref_feat.chapter_index,
                    reference_paragraph_index=ref_feat.paragraph_index,
                    confidence=best_score,
                    match_reasons=best_reasons,
                ))

        return results

    def match_all(self) -> list[MatchResult]:
        """Perform full matching using anchor-based alignment."""
        # Step 1: Find anchor points
        anchors = self.find_anchors(threshold=0.65)

        if not anchors:
            # Fallback to simple ratio-based matching
            return self._fallback_ratio_matching()

        results = []

        # Step 2: Align between anchors
        prev_s, prev_r = 0, 0

        for s_idx, r_idx, conf in anchors:
            # Align paragraphs before this anchor
            between_results = self.align_between_anchors(
                prev_s, s_idx, prev_r, r_idx
            )
            results.extend(between_results)

            # Add the anchor itself
            source_feat = self.source_features[s_idx]
            ref_feat = self.reference_features[r_idx]
            results.append(MatchResult(
                source_paragraph_id=source_feat.paragraph_id,
                reference_text=ref_feat.text,
                reference_chapter_index=ref_feat.chapter_index,
                reference_paragraph_index=ref_feat.paragraph_index,
                confidence=conf,
                match_reasons=["anchor"],
            ))

            prev_s = s_idx + 1
            prev_r = r_idx + 1

        # Align remaining paragraphs after last anchor
        if prev_s < self.source_count and prev_r < self.reference_count:
            between_results = self.align_between_anchors(
                prev_s, self.source_count, prev_r, self.reference_count
            )
            results.extend(between_results)

        return results

    def _fallback_ratio_matching(self) -> list[MatchResult]:
        """Fallback matching based on relative position and length ratio."""
        results = []

        for s_idx, source in enumerate(self.source_features):
            # Estimate reference position based on ratio
            expected_r_idx = int(s_idx * self.reference_count / self.source_count)

            # Search in a small window
            best_score = 0.0
            best_ref = None
            best_reasons = []

            window = 10
            for r_idx in range(
                max(0, expected_r_idx - window),
                min(self.reference_count, expected_r_idx + window)
            ):
                score, reasons = self.calculate_similarity(
                    source, self.reference_features[r_idx]
                )
                if score > best_score:
                    best_score = score
                    best_ref = self.reference_features[r_idx]
                    best_reasons = reasons

            if best_ref and best_score > 0.3:
                results.append(MatchResult(
                    source_paragraph_id=source.paragraph_id,
                    reference_text=best_ref.text,
                    reference_chapter_index=best_ref.chapter_index,
                    reference_paragraph_index=best_ref.paragraph_index,
                    confidence=best_score,
                    match_reasons=best_reasons,
                ))

        return results

