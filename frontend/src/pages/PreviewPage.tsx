import { useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { api, TocItem } from '../services/api/client'
import { useTranslation } from '../stores/appStore'
import { TreeChapterList } from '../components/common/TreeChapterList'
import { ReaderView, ContentMode } from '../components/preview/ReaderView'

// Helper function to flatten TOC into ordered chapter IDs for navigation
function flattenTocToChapterIds(toc: TocItem[]): string[] {
  const result: string[] = []
  const seen = new Set<string>()
  const walk = (items: TocItem[]) => {
    for (const item of items) {
      if (item.chapter_id && !seen.has(item.chapter_id)) {
        seen.add(item.chapter_id)
        result.push(item.chapter_id)
      }
      if (item.children && item.children.length > 0) {
        walk(item.children)
      }
    }
  }
  walk(toc)
  return result
}

export function PreviewPage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [contentMode, setContentMode] = useState<ContentMode>('bilingual')

  // Fetch hierarchical TOC
  const { data: toc } = useQuery({
    queryKey: ['toc', projectId],
    queryFn: () => api.getToc(projectId!),
    enabled: !!projectId,
  })

  // Also fetch flat chapters for fallback and navigation
  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId!),
    enabled: !!projectId,
  })

  // Create ordered list of chapter IDs from TOC for navigation
  const orderedChapterIds = useMemo(() => {
    if (toc && toc.length > 0) {
      return flattenTocToChapterIds(toc)
    }
    return chapters?.map(c => c.id) || []
  }, [toc, chapters])

  const { data: chapterContent, isLoading: isLoadingContent } = useQuery({
    queryKey: ['chapter', projectId, selectedChapter],
    queryFn: () => api.getChapterContent(projectId!, selectedChapter!),
    enabled: !!projectId && !!selectedChapter,
  })

  // Select first chapter by default
  if (orderedChapterIds.length > 0 && !selectedChapter) {
    setSelectedChapter(orderedChapterIds[0])
  }

  const currentChapterIndex = orderedChapterIds.findIndex((id) => id === selectedChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < orderedChapterIds.length - 1

  return (
    <div className="flex gap-6">
      {/* Chapter list */}
      <div className="w-72 flex-shrink-0">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 sticky top-4">
          <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">{t('preview.chapterList')}</h3>
          <div className="max-h-[600px] overflow-y-auto">
            {toc && toc.length > 0 ? (
              <TreeChapterList
                toc={toc}
                selectedChapterId={selectedChapter}
                onSelectChapter={setSelectedChapter}
              />
            ) : chapters?.length ? (
              // Fallback to flat list if no TOC
              <div className="space-y-1">
                {chapters.map((chapter) => (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter.id)}
                    className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                      selectedChapter === chapter.id
                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="font-medium truncate">
                      {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                    </div>
                    <div className="text-xs text-gray-400 dark:text-gray-500">
                      {chapter.paragraph_count} {t('home.paragraphs')}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
                {t('preview.noChapters')}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1">
        {/* Navigation */}
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => {
              if (canGoPrev) {
                setSelectedChapter(orderedChapterIds[currentChapterIndex - 1])
              }
            }}
            disabled={!canGoPrev}
            className="flex items-center gap-1 px-3 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600"
          >
            <ChevronLeft className="w-4 h-4" />
            {t('preview.prevChapter')}
          </button>

          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-lg bg-gray-100 dark:bg-gray-700 p-1">
              <button
                onClick={() => setContentMode('translation')}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  contentMode === 'translation'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                {t('preview.showTranslation')}
              </button>
              <button
                onClick={() => setContentMode('bilingual')}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  contentMode === 'bilingual'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                {t('preview.showBilingual')}
              </button>
              <button
                onClick={() => setContentMode('original')}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  contentMode === 'original'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                {t('preview.showOriginal')}
              </button>
            </div>
          </div>

          <button
            onClick={() => {
              if (canGoNext) {
                setSelectedChapter(orderedChapterIds[currentChapterIndex + 1])
              }
            }}
            disabled={!canGoNext}
            className="flex items-center gap-1 px-3 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600"
          >
            {t('preview.nextChapter')}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Content Area */}
        {isLoadingContent ? (
          <div className="text-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
          </div>
        ) : chapterContent ? (
          <ReaderView
            content={chapterContent}
            projectId={projectId!}
            contentMode={contentMode}
          />
        ) : null}
      </div>
    </div>
  )
}
