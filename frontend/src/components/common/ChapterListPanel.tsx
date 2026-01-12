import { ReactNode } from 'react'
import { ChevronsDownUp, ChevronsUpDown } from 'lucide-react'
import { TreeChapterList } from './TreeChapterList'
import { ResizeHandle } from './ResizeHandle'
import type { TocItem } from '../../services/api/client'

interface FontClasses {
  base: string
  xs: string
  sm: string
  label: string
  paragraph: string
}

interface ChapterListPanelProps {
  toc?: TocItem[]
  selectedChapterId?: string | null
  onSelectChapter: (chapterId: string) => void
  expandAll: boolean
  onToggleExpandAll: () => void
  width: number
  onResize: (delta: number) => void
  fontClasses: FontClasses
  title: string
  // Checkbox mode
  showCheckboxes?: boolean
  selectedChapterIds?: Set<string>
  // Optional header content (e.g., select all button)
  headerExtra?: ReactNode
  // Optional info text below header
  infoText?: string
}

export function ChapterListPanel({
  toc,
  selectedChapterId,
  onSelectChapter,
  expandAll,
  onToggleExpandAll,
  width,
  onResize,
  fontClasses,
  title,
  showCheckboxes = false,
  selectedChapterIds,
  headerExtra,
  infoText,
}: ChapterListPanelProps): JSX.Element {
  const hasTocItems = toc && toc.length > 0

  return (
    <div className="hidden lg:flex flex-shrink-0 h-full" style={{ width }}>
      <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-1.5 flex-shrink-0">
          <h3 className={`font-medium text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>
            {title}
          </h3>
          <div className="flex items-center gap-1">
            {headerExtra}
            {hasTocItems && (
              <button
                onClick={onToggleExpandAll}
                className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              >
                {expandAll ? <ChevronsDownUp className="w-4 h-4" /> : <ChevronsUpDown className="w-4 h-4" />}
              </button>
            )}
          </div>
        </div>

        {/* Info text */}
        {infoText && (
          <div className={`text-gray-500 dark:text-gray-400 mb-2 ${fontClasses.xs}`}>
            {infoText}
          </div>
        )}

        {/* Chapter list */}
        <div className="flex-1 overflow-y-auto">
          {hasTocItems ? (
            <TreeChapterList
              toc={toc}
              selectedChapterId={showCheckboxes ? null : selectedChapterId || null}
              onSelectChapter={onSelectChapter}
              fontClasses={fontClasses}
              expandAll={expandAll}
              showCheckboxes={showCheckboxes}
              selectedChapterIds={selectedChapterIds}
            />
          ) : (
            <div className={`text-gray-500 dark:text-gray-400 ${fontClasses.paragraph} text-center py-4`}>
              No chapters
            </div>
          )}
        </div>
      </div>

      {/* Resize handle - no gap, directly attached */}
      <ResizeHandle onResize={onResize} className="h-full" />
    </div>
  )
}
