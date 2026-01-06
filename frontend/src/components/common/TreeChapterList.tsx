import { useState, useMemo } from 'react'
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

interface TreeChapterListProps {
  toc: TocItem[]
  selectedChapterId: string | null
  onSelectChapter: (chapterId: string) => void
  fontClasses?: FontClasses
  expandAll?: boolean
  compact?: boolean
  minimal?: boolean
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
}: TocNodeProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  const hasChildren = item.children && item.children.length > 0
  const isClickable = item.chapter_id !== null
  const isSelected = item.chapter_id === selectedChapterId

  // Check if this node or any descendant contains the selected chapter
  const containsSelected = useMemo(() => {
    const checkSelected = (node: TocItem): boolean => {
      if (node.chapter_id === selectedChapterId) return true
      return node.children?.some(checkSelected) ?? false
    }
    return checkSelected(item)
  }, [item, selectedChapterId])

  const handleClick = () => {
    if (isClickable) {
      onSelectChapter(item.chapter_id!)
    } else if (hasChildren && !expandAll && !minimal) {
      setIsExpanded(!isExpanded)
    }
  }

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!expandAll && !minimal) {
      setIsExpanded(!isExpanded)
    }
  }

  const textSizeClass = minimal ? 'text-[10px]' : (fontClasses?.paragraph || 'text-sm')
  const badgeSizeClass = fontClasses?.xs || 'text-xs'
  const isOpen = expandAll || minimal ? true : isExpanded
  const paddingClasses = minimal ? 'py-[1px] px-1' : (compact ? 'py-1 px-1.5' : 'py-1.5 px-2')
  const leadingClass = minimal ? 'leading-tight' : ''
  const titleWeightClass = minimal ? (isSelected ? 'font-semibold' : 'font-normal') : (compact ? 'font-normal' : 'font-medium')
  const selectedSizeClass = minimal && isSelected ? 'text-xs' : ''
  const idleTextClass = compact ? 'text-gray-500 dark:text-gray-400' : 'text-gray-700 dark:text-gray-300'
  const groupTextClass = compact ? 'text-gray-500 dark:text-gray-400' : 'text-gray-600 dark:text-gray-400'
  const cursorClass = isClickable ? 'cursor-pointer' : 'cursor-default'
  const transitionClass = minimal ? '' : 'transition-colors'
  const selectedBgClass = minimal && isSelected ? 'bg-amber-100 dark:bg-amber-900/40' : ''

  return (
    <div>
      <div
        onClick={handleClick}
        className={`
          flex items-center gap-1 ${textSizeClass} ${leadingClass} ${cursorClass} ${transitionClass} ${paddingClasses}
          ${!minimal && isSelected ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' : ''}
          ${!minimal && !isSelected && isClickable ? `hover:bg-gray-50 dark:hover:bg-gray-700/50 ${idleTextClass}` : ''}
          ${!minimal && !isClickable && !hasChildren ? 'text-gray-400 dark:text-gray-500 cursor-default' : ''}
          ${!minimal && !isClickable && hasChildren ? groupTextClass : ''}
          ${selectedBgClass}
        `}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        {/* Expand/collapse toggle for items with children */}
        {hasChildren && !minimal ? (
          <button
            onClick={handleToggle}
            className="p-0.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
          >
            {isOpen ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
          </button>
        ) : (
          <span className="w-4" /> // Spacer for alignment
        )}

        {/* Icon */}
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
        <span className={`truncate flex-1 ${titleWeightClass} ${selectedSizeClass}`}>
          {item.title || t('preview.untitled')}
        </span>

        {/* Paragraph count badge */}
        {!minimal && item.paragraph_count !== null && item.paragraph_count > 0 && (
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
          defaultExpanded={true}
          expandAll={expandAll}
          compact={compact}
          minimal={minimal}
          fontClasses={fontClasses}
        />
      ))}
    </div>
  )
}
