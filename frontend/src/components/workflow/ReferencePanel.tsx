import { BookOpen, Search, X, Loader2 } from 'lucide-react'
import { ResizeHandle } from '../common/ResizeHandle'
import { useTranslation } from '../../stores/appStore'
import { ReferenceChapter, ReferenceChapterContent, ReferenceSearchResponse } from '../../services/api/client'

interface ReferencePanelProps {
    width: number
    show: boolean
    hasReference: boolean
    onClose: () => void
    onResize: (newWidth: number) => void

    // Search State
    searchQuery: string
    searchInputValue: string
    isSearching: boolean
    onSearch: (e: React.FormEvent) => void
    onSearchInputChange: (value: string) => void
    onClearSearch: () => void
    searchResults?: ReferenceSearchResponse
    onSearchResultClick: (chapterNumber: number, paragraphNumber: number) => void

    // Browse State
    chapters?: ReferenceChapter[]
    selectedChapter: number | null
    onSelectChapter: (chapterNumber: number) => void

    // Content State
    isLoadingContent: boolean
    chapterContent?: ReferenceChapterContent
    highlightedParagraph: number | null

    fontClasses: any
}

export function ReferencePanel({
    width,
    show,
    hasReference,
    onClose,
    onResize,
    searchQuery,
    searchInputValue,
    isSearching,
    onSearch,
    onSearchInputChange,
    onClearSearch,
    searchResults,
    onSearchResultClick,
    chapters,
    selectedChapter,
    onSelectChapter,
    isLoadingContent,
    chapterContent,
    highlightedParagraph,
    fontClasses
}: ReferencePanelProps) {
    const { t } = useTranslation()

    if (!show || !hasReference) return null

    return (
        <>
            <ResizeHandle onResize={onResize} className="h-full" />

            <div
                className="flex-shrink-0 self-start sticky top-2 transition-all"
                style={{ width }}
            >
                <div className="bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800 p-2 max-h-[calc(100vh-100px)] flex flex-col">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium text-amber-800 dark:text-amber-200 text-xs flex items-center gap-1">
                            <BookOpen className="w-3 h-3" />
                            {t('translate.referenceChapter')}
                        </h3>
                        <button
                            onClick={onClose}
                            className="p-0.5 text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </div>

                    {/* Search input */}
                    <form onSubmit={onSearch} className="flex gap-1 mb-2">
                        <div className="relative flex-1">
                            <input
                                type="text"
                                value={searchInputValue}
                                onChange={(e) => onSearchInputChange(e.target.value)}
                                placeholder={t('translate.searchReference')}
                                className="w-full pl-6 pr-2 py-1 text-xs border border-amber-300 dark:border-amber-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400"
                            />
                            <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-amber-500" />
                        </div>
                        {searchQuery && (
                            <button
                                type="button"
                                onClick={onClearSearch}
                                className="p-1 text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200"
                                title={t('common.cancel')}
                            >
                                <X className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </form>

                    {/* Reference chapter selector - only when not searching */}
                    {!searchQuery && (
                        <select
                            value={selectedChapter ?? ''}
                            onChange={(e) => onSelectChapter(Number(e.target.value))}
                            className="w-full px-1.5 py-1 mb-2 text-xs border border-amber-300 dark:border-amber-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                        >
                            {chapters?.map((ch) => (
                                <option key={ch.chapter_number} value={ch.chapter_number}>
                                    {ch.title || `Ch ${ch.chapter_number}`} ({ch.paragraph_count})
                                </option>
                            ))}
                        </select>
                    )}

                    {/* Reference content */}
                    <div className="flex-1 overflow-y-auto">
                        {/* Search results */}
                        {searchQuery ? (
                            isSearching ? (
                                <div className="flex items-center justify-center py-4">
                                    <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                                </div>
                            ) : searchResults && searchResults.results.length > 0 ? (
                                <div className="space-y-1.5">
                                    <div className={`${fontClasses.xs} text-amber-600 dark:text-amber-400 mb-2`}>
                                        {t('translate.searchResultsCount', { count: String(searchResults.total_results) })}
                                    </div>
                                    {searchResults.results.map((result, idx) => (
                                        <div
                                            key={`${result.chapter_number}-${result.paragraph_number}-${idx}`}
                                            onClick={() => onSearchResultClick(result.chapter_number, result.paragraph_number)}
                                            className={`${fontClasses.paragraph} text-amber-900 dark:text-amber-100 leading-relaxed p-1.5 rounded cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-900/40 border border-amber-200 dark:border-amber-700`}
                                        >
                                            <div className={`${fontClasses.xs} text-amber-500 dark:text-amber-500 mb-0.5`}>
                                                {result.chapter_title || `Ch ${result.chapter_number}`} - P{result.paragraph_number}
                                            </div>
                                            <div>
                                                {result.text.slice(0, result.match_start)}
                                                <mark className="bg-amber-300 dark:bg-amber-600 text-amber-900 dark:text-amber-100 px-0.5 rounded">
                                                    {result.text.slice(result.match_start, result.match_end)}
                                                </mark>
                                                {result.text.slice(result.match_end)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-amber-600 dark:text-amber-400 text-xs text-center py-4">
                                    {t('translate.noSearchResults')}
                                </div>
                            )
                        ) : (
                            /* Chapter content */
                            isLoadingContent ? (
                                <div className="flex items-center justify-center py-4">
                                    <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                                </div>
                            ) : chapterContent ? (
                                <div className="space-y-1.5">
                                    {chapterContent.title && (
                                        <h4 className={`font-medium text-amber-900 dark:text-amber-100 ${fontClasses.sm} border-b border-amber-200 dark:border-amber-700 pb-1`}>
                                            {chapterContent.title}
                                        </h4>
                                    )}
                                    {chapterContent.paragraphs.map((para) => (
                                        <div
                                            key={para.paragraph_number}
                                            id={`ref-para-${para.paragraph_number}`}
                                            ref={highlightedParagraph === para.paragraph_number ? (el) => el?.scrollIntoView({ behavior: 'smooth', block: 'center' }) : undefined}
                                            className={`${fontClasses.paragraph} text-amber-900 dark:text-amber-100 leading-relaxed p-1 rounded transition-colors duration-300 ${highlightedParagraph === para.paragraph_number
                                                ? 'bg-amber-200 dark:bg-amber-700 ring-2 ring-amber-400'
                                                : 'hover:bg-amber-100 dark:hover:bg-amber-900/40'
                                                }`}
                                        >
                                            <span className={`text-amber-500 dark:text-amber-500 ${fontClasses.xs} mr-1`}>{para.paragraph_number}.</span>
                                            {para.text}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-amber-600 dark:text-amber-400 text-xs text-center py-2">
                                    {t('translate.selectReferenceChapter')}
                                </div>
                            )
                        )}
                    </div>
                </div>
            </div>
        </>
    )
}

