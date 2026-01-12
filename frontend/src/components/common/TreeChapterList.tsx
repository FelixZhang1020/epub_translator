import { useState, useMemo, useEffect } from 'react'
import { ChevronRight, ChevronDown, FileText, Folder, FolderOpen } from 'lucide-react'
import { TocItem } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

interface FontClasses {
  base: string
  xs: string
  sm: string
  label: string
  paragraph: string
}

interface ChapterStats {
  translated: number
  total: number
}

interface TreeChapterListProps {
  toc: TocItem[]
  selectedChapterId: string | null
  onSelectChapter: (chapterId: string) => void
  fontClasses?: FontClasses
  expandAll?: boolean
  compact?: boolean
  minimal?: boolean
  showCheckboxes?: boolean
  selectedChapterIds?: Set<string>
  chapterStatsMap?: Map<string, ChapterStats>
}

interface TocNodeProps {
  item: TocItem
  level: number
  selectedChapterId: string | null
  onSelectChapter: (chapterId: string) => void
  defaultExpanded?: boolean
  expandAll?: boolean
  compact?: boolean
  minimal?: boolean
  fontClasses?: FontClasses
  showCheckboxes?: boolean
  selectedChapterIds?: Set<string>
  chapterStatsMap?: Map<string, ChapterStats>
}

/** Recursively collect all chapter IDs from a TOC node and its descendants */
function collectChapterIds(node: TocItem): string[] {
  const ids: string[] = []
  if (node.chapter_id) {
    ids.push(node.chapter_id)
  }
  if (node.children) {
    for (const child of node.children) {
      ids.push(...collectChapterIds(child))
    }
  }
  return ids
}

/** Check if a TOC node or any of its descendants contains the target chapter */
function containsChapter(node: TocItem, chapterId: string | null): boolean {
  if (!chapterId) return false
  if (node.chapter_id === chapterId) return true
  return node.children?.some(child => containsChapter(child, chapterId)) ?? false
}

function TocNode({
  item,
  level,
  selectedChapterId,
  onSelectChapter,
  defaultExpanded = true,
  expandAll = false,
  compact = false,
  minimal = false,
  fontClasses,
  showCheckboxes = false,
  selectedChapterIds,
  chapterStatsMap,
}: TocNodeProps): JSX.Element {
  const { t } = useTranslation()

  const hasChildren = item.children && item.children.length > 0
  const isClickable = item.chapter_id !== null
  const isDirectlySelected = item.chapter_id === selectedChapterId

  // Check if this node or any descendant contains the selected chapter
  const containsSelected = useMemo(
    () => containsChapter(item, selectedChapterId),
    [item, selectedChapterId]
  )

  const [isExpanded, setIsExpanded] = useState(defaultExpanded || containsSelected)

  // For checkbox mode: collect all unique chapter IDs under this node
  const childChapterIds = useMemo(() => {
    if (!showCheckboxes) return []
    const ids = hasChildren ? collectChapterIds(item) : (item.chapter_id ? [item.chapter_id] : [])
    return Array.from(new Set(ids))
  }, [item, showCheckboxes, hasChildren])

  // Check selection state for checkbox mode
  const allChildrenSelected = useMemo(() => {
    if (!showCheckboxes || childChapterIds.length === 0) return false
    return childChapterIds.every(id => selectedChapterIds?.has(id))
  }, [showCheckboxes, childChapterIds, selectedChapterIds])

  const someChildrenSelected = useMemo(() => {
    if (!showCheckboxes || childChapterIds.length === 0) return false
    const hasAnySelected = childChapterIds.some(id => selectedChapterIds?.has(id))
    return hasAnySelected && !allChildrenSelected
  }, [showCheckboxes, childChapterIds, selectedChapterIds, allChildrenSelected])

  // Check if any direct child is selected (for highlighting logic)
  const hasSelectedChild = hasChildren && item.children.some(child => child.chapter_id === selectedChapterId)

  // Only highlight as selected if directly selected AND no child is selected
  const isSelected = isDirectlySelected && !hasSelectedChild

  // Auto-expand when this node contains the selected chapter
  useEffect(() => {
    if (containsSelected && !expandAll && !minimal) {
      setIsExpanded(true)
    }
  }, [containsSelected, expandAll, minimal])

  // Sync with expandAll prop
  useEffect(() => {
    if (expandAll) {
      setIsExpanded(true)
    } else if (!containsSelected) {
      // When collapsing all, only collapse nodes that don't contain selected chapter
      setIsExpanded(false)
    }
  }, [expandAll, containsSelected])

  const canToggleExpand = hasChildren && !expandAll && !minimal

  function handleClick(): void {
    if (showCheckboxes) {
      // In checkbox mode, row clicks only expand/collapse
      if (canToggleExpand) setIsExpanded(!isExpanded)
      return
    }
    // Normal mode - clicking selects the chapter or toggles expansion
    if (isClickable) {
      onSelectChapter(item.chapter_id!)
    } else if (canToggleExpand) {
      setIsExpanded(!isExpanded)
    }
  }

  function handleToggle(e: React.MouseEvent): void {
    e.stopPropagation()
    if (canToggleExpand) setIsExpanded(!isExpanded)
  }

  const textSizeClass = minimal ? 'text-[10px]' : (fontClasses?.paragraph || 'text-sm')
  const badgeSizeClass = fontClasses?.xs || 'text-xs'
  const isOpen = expandAll ? true : (minimal ? true : isExpanded)
  const paddingClasses = minimal ? 'py-[1px] px-1' : (compact ? 'py-1 px-1.5' : 'py-1.5 px-2')
  const leadingClass = minimal ? 'leading-tight' : ''
  const titleWeightClass = minimal ? (isSelected ? 'font-semibold' : 'font-normal') : (compact ? 'font-normal' : 'font-medium')
  const selectedSizeClass = minimal && isSelected ? 'text-xs' : ''
  const idleTextClass = compact ? 'text-gray-500 dark:text-gray-400' : 'text-gray-700 dark:text-gray-300'
  const groupTextClass = compact ? 'text-gray-500 dark:text-gray-400' : 'text-gray-600 dark:text-gray-400'
  // In checkbox mode, row is only clickable for expand/collapse (if has children) or not clickable at all
  // In normal mode, row is clickable if chapter has content
  const cursorClass = showCheckboxes
    ? (hasChildren ? 'cursor-pointer' : 'cursor-default')
    : (isClickable ? 'cursor-pointer' : 'cursor-default')
  const transitionClass = minimal ? '' : 'transition-colors'
  const selectedBgClass = minimal && isSelected ? 'bg-amber-100 dark:bg-amber-900/40' : ''

  return (
    <div>
      <div
        onClick={handleClick}
        className={`
          relative flex items-center justify-start gap-1 ${textSizeClass} ${leadingClass} ${cursorClass} ${transitionClass} ${paddingClasses} rounded
          ${!minimal && !showCheckboxes && isSelected ? 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-50 font-semibold' : ''}
          ${!minimal && !showCheckboxes && !isSelected && isClickable ? `hover:bg-gray-50 dark:hover:bg-gray-700/50 ${idleTextClass}` : ''}
          ${!minimal && showCheckboxes ? `hover:bg-gray-50 dark:hover:bg-gray-700/50 ${idleTextClass}` : ''}
          ${!minimal && !isClickable && !hasChildren ? 'text-gray-400 dark:text-gray-500 cursor-default' : ''}
          ${!minimal && !isClickable && hasChildren ? groupTextClass : ''}
          ${selectedBgClass}
        `}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        {/* Selected indicator - only show in non-checkbox mode */}
        {!minimal && !showCheckboxes && isSelected && (
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-600 dark:bg-blue-400 rounded-l" />
        )}
        {/* Expand/collapse toggle for items with children */}
        {hasChildren && !minimal ? (
          <button
            onClick={handleToggle}
            className="flex-shrink-0 p-0.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
          >
            {isOpen ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
          </button>
        ) : !minimal ? (
          <span className="flex-shrink-0 w-[18px]" /> // Spacer for alignment (matches button width)
        ) : null}

        {/* Checkbox or spacer for alignment */}
        {showCheckboxes && (
          (isClickable || hasChildren) ? (
            <input
              type="checkbox"
              checked={
                item.chapter_id
                  ? selectedChapterIds?.has(item.chapter_id) || false
                  : allChildrenSelected
              }
              ref={(el) => {
                if (el) {
                  el.indeterminate = hasChildren && someChildrenSelected
                }
              }}
              onChange={(e) => {
                e.stopPropagation()
                if (hasChildren) {
                  // Node with children - toggle all descendants
                  // If ANY children are selected (all or some), deselect all
                  // If NO children are selected, select all
                  const anyChildrenSelected = childChapterIds.some(id => selectedChapterIds?.has(id))

                  if (anyChildrenSelected) {
                    // Deselect all descendants
                    childChapterIds.forEach(id => {
                      if (selectedChapterIds?.has(id)) {
                        onSelectChapter(id)
                      }
                    })
                  } else {
                    // Select all descendants
                    childChapterIds.forEach(id => {
                      if (!selectedChapterIds?.has(id)) {
                        onSelectChapter(id)
                      }
                    })
                  }
                } else if (item.chapter_id) {
                  // Leaf node with no children - just toggle this chapter
                  onSelectChapter(item.chapter_id)
                }
              }}
              className="flex-shrink-0 mr-2 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
            />
          ) : (
            // Invisible spacer to maintain alignment when no checkbox
            <span className="flex-shrink-0 w-[16px] mr-2" />
          )
        )}

        {/* Icon - show in both normal and checkbox modes */}
        {hasChildren && !minimal ? (
          isOpen ? (
            <FolderOpen className="w-4 h-4 text-amber-500" />
          ) : (
            <Folder className="w-4 h-4 text-amber-500" />
          )
        ) : !minimal ? (
          <FileText className={`w-4 h-4 ${isClickable ? 'text-blue-500' : 'text-gray-400'}`} />
        ) : null}

        {/* Title */}
        <span className={`truncate flex-1 text-left ${titleWeightClass} ${selectedSizeClass}`}>
          {item.title || t('preview.untitled')}
        </span>

        {/* Chapter stats (translated/total) */}
        {!minimal && item.chapter_id && chapterStatsMap?.has(item.chapter_id) && (
          <span className={`${badgeSizeClass} text-gray-500 dark:text-gray-400 ml-1 whitespace-nowrap`}>
            {chapterStatsMap.get(item.chapter_id)!.translated} / {chapterStatsMap.get(item.chapter_id)!.total}
          </span>
        )}

        {/* Paragraph count badge (fallback) */}
        {!minimal && !chapterStatsMap && item.paragraph_count !== null && item.paragraph_count > 0 && (
          <span className={`${badgeSizeClass} text-gray-400 dark:text-gray-500 ml-1`}>
            {item.paragraph_count}
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isOpen && (
        <div>
          {item.children.map((child, index) => (
            <TocNode
              key={`${child.href || child.title}-${index}`}
              item={child}
              level={level + 1}
              selectedChapterId={selectedChapterId}
              onSelectChapter={onSelectChapter}
              defaultExpanded={expandAll ? true : containsSelected}
              expandAll={expandAll}
              compact={compact}
              minimal={minimal}
              fontClasses={fontClasses}
              showCheckboxes={showCheckboxes}
              selectedChapterIds={selectedChapterIds}
              chapterStatsMap={chapterStatsMap}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function TreeChapterList({
  toc,
  selectedChapterId,
  onSelectChapter,
  fontClasses,
  expandAll = false,
  compact = false,
  minimal = false,
  showCheckboxes = false,
  selectedChapterIds,
  chapterStatsMap,
}: TreeChapterListProps) {
  const { t } = useTranslation()

  const textSizeClass = fontClasses?.paragraph || 'text-sm'

  if (!toc || toc.length === 0) {
    return (
      <div className={`text-gray-500 dark:text-gray-400 ${textSizeClass} p-4 text-center`}>
        {t('preview.noChapters')}
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {toc.map((item, index) => (
        <TocNode
          key={`${item.href || item.title}-${index}`}
          item={item}
          level={0}
          selectedChapterId={selectedChapterId}
          onSelectChapter={onSelectChapter}
          defaultExpanded={expandAll}
          expandAll={expandAll}
          compact={compact}
          minimal={minimal}
          fontClasses={fontClasses}
          showCheckboxes={showCheckboxes}
          selectedChapterIds={selectedChapterIds}
          chapterStatsMap={chapterStatsMap}
        />
      ))}
    </div>
  )
}
