/**
 * Shared workflow utilities for translate and proofread pages.
 */

import { useCallback, useMemo } from 'react'
import { useAppStore } from '../stores/appStore'
import { TocItem } from '../services/api/client'

// Panel width constraints
export const PANEL_CONSTRAINTS = {
  chapterList: {
    min: 120,
    max: 400,
  },
  referencePanel: {
    min: 200,
    max: 500,
  },
} as const

/**
 * Flatten a hierarchical TOC structure into an ordered list of chapter IDs.
 * This is used for chapter navigation (prev/next).
 * Removes duplicates while preserving order (keeps last occurrence).
 */
export function flattenTocToChapterIds(toc: TocItem[]): string[] {
  const result: string[] = []
  const seen = new Set<string>()

  for (const item of toc) {
    if (item.chapter_id) {
      result.push(item.chapter_id)
    }
    if (item.children && item.children.length > 0) {
      result.push(...flattenTocToChapterIds(item.children))
    }
  }

  // Remove duplicates by keeping only the last occurrence
  // This ensures that if a chapter appears as both parent and child,
  // we keep the child position (deeper in the hierarchy)
  const uniqueResult: string[] = []
  const lastIndices = new Map<string, number>()

  // Find the last index of each chapter_id
  result.forEach((id, index) => {
    lastIndices.set(id, index)
  })

  // Keep only items at their last occurrence index
  result.forEach((id, index) => {
    if (lastIndices.get(id) === index && !seen.has(id)) {
      uniqueResult.push(id)
      seen.add(id)
    }
  })

  return uniqueResult
}

/**
 * Hook for building an ordered list of chapter IDs from TOC or flat chapters.
 */
export function useOrderedChapterIds(
  toc: TocItem[] | undefined,
  chapters: { id: string }[] | undefined
): string[] {
  return useMemo(() => {
    if (toc && toc.length > 0) {
      return flattenTocToChapterIds(toc)
    }
    return chapters?.map((c) => c.id) || []
  }, [toc, chapters])
}

/**
 * Hook for chapter navigation logic.
 * Returns navigation state and handlers.
 */
export function useChapterNavigation(
  orderedChapterIds: string[],
  selectedChapter: string | null,
  setSelectedChapter: (id: string) => void
) {
  const currentChapterIndex = orderedChapterIds.findIndex(
    (id) => id === selectedChapter
  )
  const canGoPrev = currentChapterIndex > 0
  const canGoNext =
    currentChapterIndex >= 0 &&
    currentChapterIndex < orderedChapterIds.length - 1

  const goToPrevChapter = useCallback(() => {
    const currentIndex = orderedChapterIds.findIndex((id) => id === selectedChapter)
    if (currentIndex > 0) {
      setSelectedChapter(orderedChapterIds[currentIndex - 1])
    }
  }, [orderedChapterIds, selectedChapter, setSelectedChapter])

  const goToNextChapter = useCallback(() => {
    const currentIndex = orderedChapterIds.findIndex((id) => id === selectedChapter)
    if (currentIndex >= 0 && currentIndex < orderedChapterIds.length - 1) {
      setSelectedChapter(orderedChapterIds[currentIndex + 1])
    }
  }, [orderedChapterIds, selectedChapter, setSelectedChapter])

  return {
    currentChapterIndex,
    canGoPrev,
    canGoNext,
    goToPrevChapter,
    goToNextChapter,
  }
}

/**
 * Hook for panel resize functionality.
 * Manages chapter list and reference panel widths.
 */
export function usePanelResize() {
  const panelWidths = useAppStore((state) => state.panelWidths)
  const setPanelWidth = useAppStore((state) => state.setPanelWidth)

  const handleChapterListResize = useCallback(
    (delta: number) => {
      const newWidth = Math.max(
        PANEL_CONSTRAINTS.chapterList.min,
        Math.min(
          PANEL_CONSTRAINTS.chapterList.max,
          panelWidths.chapterList + delta
        )
      )
      setPanelWidth('chapterList', newWidth)
    },
    [panelWidths.chapterList, setPanelWidth]
  )

  const handleReferencePanelResize = useCallback(
    (delta: number) => {
      // For reference panel, negative delta means making it wider (dragging left)
      const newWidth = Math.max(
        PANEL_CONSTRAINTS.referencePanel.min,
        Math.min(
          PANEL_CONSTRAINTS.referencePanel.max,
          panelWidths.referencePanel - delta
        )
      )
      setPanelWidth('referencePanel', newWidth)
    },
    [panelWidths.referencePanel, setPanelWidth]
  )

  return {
    panelWidths,
    handleChapterListResize,
    handleReferencePanelResize,
  }
}
