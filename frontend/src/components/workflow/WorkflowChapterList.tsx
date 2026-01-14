import { ChevronsDownUp, ChevronsUpDown } from 'lucide-react'
import { TreeChapterList } from '../common/TreeChapterList'
import { ResizeHandle } from '../common/ResizeHandle'
import { useTranslation } from '../../stores/appStore'
import { useState } from 'react'

interface TocItem {
    title: string | null
    href: string | null
    chapter_id: string | null
    chapter_number: number | null
    paragraph_count: number | null
    children: TocItem[]
}

interface Chapter {
    id: string
    title: string | null
    chapter_number: number
    paragraph_count: number
}

interface ChapterStats {
    translated: number
    total: number
}

interface WorkflowChapterListProps {
    width: number
    toc?: TocItem[]
    chapters?: Chapter[]
    selectedChapterId: string | null
    onSelectChapter: (id: string) => void
    onResize: (newWidth: number) => void
    fontClasses: any
    title?: string
    className?: string
    chapterStatsMap?: Map<string, ChapterStats>
    // Multi-select checkbox mode props
    showCheckboxes?: boolean
    selectedChapterIds?: Set<string>
    onSelectAll?: () => void
    selectionText?: string
}

export function WorkflowChapterList({
    width,
    toc,
    chapters,
    selectedChapterId,
    onSelectChapter,
    onResize,
    fontClasses,
    title,
    className = '',
    chapterStatsMap,
    showCheckboxes = false,
    selectedChapterIds,
    onSelectAll,
    selectionText,
}: WorkflowChapterListProps) {
    const { t } = useTranslation()
    const [expandAll, setExpandAll] = useState(false)

    // Determine if we have content to show
    const hasContent = (toc && toc.length > 0) || (chapters && chapters.length > 0)

    return (
        <>
            <div
                className={`hidden lg:flex lg:flex-col flex-shrink-0 self-stretch ${className}`}
                style={{ width }}
            >
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2 h-full overflow-y-auto">
                    <div className="flex items-center justify-between mb-1.5">
                        <h3 className={`font-medium text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>
                            {title || t('preview.chapterList')}
                        </h3>
                        <div className="flex items-center gap-1">
                            {/* Select all button - only in checkbox mode */}
                            {showCheckboxes && onSelectAll && (
                                <button
                                    onClick={onSelectAll}
                                    className={`text-blue-600 dark:text-blue-400 hover:underline ${fontClasses.xs}`}
                                    title={selectionText}
                                >
                                    {selectionText}
                                </button>
                            )}
                            {/* Expand/collapse button - always show when TOC exists */}
                            {toc && toc.length > 0 && (
                                <button
                                    onClick={() => setExpandAll(!expandAll)}
                                    className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                                    title={expandAll ? t('preview.collapseAll') : t('preview.expandAll')}
                                >
                                    {expandAll ? (
                                        <ChevronsDownUp className="w-4 h-4" />
                                    ) : (
                                        <ChevronsUpDown className="w-4 h-4" />
                                    )}
                                </button>
                            )}
                        </div>
                    </div>

                    {hasContent ? (
                        toc && toc.length > 0 ? (
                            <TreeChapterList
                                toc={toc}
                                selectedChapterId={selectedChapterId}
                                onSelectChapter={onSelectChapter}
                                fontClasses={fontClasses}
                                expandAll={expandAll}
                                showCheckboxes={showCheckboxes}
                                selectedChapterIds={selectedChapterIds}
                                chapterStatsMap={chapterStatsMap}
                            />
                        ) : showCheckboxes ? (
                            /* Checkbox mode fallback for flat chapters */
                            <div className="space-y-0.5">
                                {chapters?.map((chapter) => (
                                    <label
                                        key={chapter.id}
                                        className={`flex items-center gap-2 px-1.5 py-1 rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 ${fontClasses.paragraph} text-gray-700 dark:text-gray-300`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={selectedChapterIds?.has(chapter.id) ?? false}
                                            onChange={() => onSelectChapter(chapter.id)}
                                            className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                                        />
                                        <span className="truncate flex-1">
                                            {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                                        </span>
                                        {chapterStatsMap?.has(chapter.id) && (
                                            <span className={`${fontClasses.xs} text-gray-400 dark:text-gray-500`}>
                                                {chapterStatsMap.get(chapter.id)!.translated} / {chapterStatsMap.get(chapter.id)!.total}
                                            </span>
                                        )}
                                    </label>
                                ))}
                            </div>
                        ) : (
                            /* Single-select mode fallback for flat chapters */
                            <div className="space-y-0.5">
                                {chapters?.map((chapter) => (
                                    <button
                                        key={chapter.id}
                                        onClick={() => onSelectChapter(chapter.id)}
                                        className={`relative w-full text-left px-1.5 py-1 rounded ${fontClasses.paragraph} transition-colors ${selectedChapterId === chapter.id
                                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-50 font-semibold'
                                            : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                                            }`}
                                    >
                                        {selectedChapterId === chapter.id && (
                                            <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-600 dark:bg-blue-400 rounded-l" />
                                        )}
                                        <div className="font-medium truncate">
                                            {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                                        </div>
                                        <div className={`${fontClasses.xs} text-gray-400 dark:text-gray-500`}>
                                            {chapter.paragraph_count} {t('home.paragraphs')}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )
                    ) : (
                        <div className={`text-gray-500 dark:text-gray-400 ${fontClasses.paragraph} text-center py-4`}>
                            {t('preview.noChapters')}
                        </div>
                    )}
                </div>
            </div>
            <div className="hidden lg:flex self-stretch">
                <ResizeHandle onResize={onResize} className="h-full" />
            </div>
        </>
    )
}
