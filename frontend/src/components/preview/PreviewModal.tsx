import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react'
import { api, TocItem } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'
import { TreeChapterList } from '../common/TreeChapterList'
import { ReaderView, ContentMode } from './ReaderView'

interface PreviewModalProps {
  isOpen: boolean
  onClose: () => void
  projectId: string
}

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

export function PreviewModal({ isOpen, onClose, projectId }: PreviewModalProps) {
  const { t } = useTranslation()
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [contentMode, setContentMode] = useState<ContentMode>('bilingual')

  const { data: toc } = useQuery({
    queryKey: ['toc', projectId],
    queryFn: () => api.getToc(projectId),
    enabled: isOpen && !!projectId,
  })

  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId),
    enabled: isOpen && !!projectId,
  })

  const orderedChapterIds = useMemo(() => {
    if (toc && toc.length > 0) {
      return flattenTocToChapterIds(toc)
    }
    return chapters?.map(c => c.id) || []
  }, [toc, chapters])

  useEffect(() => {
    if (!isOpen) {
      setSelectedChapter(null)
      return
    }
    if (orderedChapterIds.length > 0 && !selectedChapter) {
      setSelectedChapter(orderedChapterIds[0])
    }
  }, [isOpen, orderedChapterIds, selectedChapter])

  const { data: chapterContent, isLoading: isLoadingContent } = useQuery({
    queryKey: ['chapter', projectId, selectedChapter],
    queryFn: () => api.getChapterContent(projectId, selectedChapter!),
    enabled: isOpen && !!projectId && !!selectedChapter,
  })

  const currentChapterIndex = orderedChapterIds.findIndex((id) => id === selectedChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < orderedChapterIds.length - 1

  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        className="relative mx-auto my-6 h-[90vh] w-[92vw] max-w-6xl rounded-xl bg-white dark:bg-gray-900 shadow-xl border border-gray-200 dark:border-gray-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t('common.preview')}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
            aria-label={t('common.cancel')}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <div className="flex gap-6 h-full">
            <div className="w-56 flex-shrink-0">
              <div className="p-0.5 h-full overflow-y-auto text-gray-700 dark:text-gray-300">
                {toc && toc.length > 0 ? (
                  <TreeChapterList
                    toc={toc}
                    selectedChapterId={selectedChapter}
                    onSelectChapter={setSelectedChapter}
                    expandAll
                    minimal
                  />
                ) : chapters?.length ? (
                  <div className="space-y-1">
                    {chapters.map((chapter) => (
                      <button
                        key={chapter.id}
                        onClick={() => setSelectedChapter(chapter.id)}
                        className={`relative w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                          selectedChapter === chapter.id
                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-50 font-semibold'
                            : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                        }`}
                      >
                        {selectedChapter === chapter.id && (
                          <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-600 dark:bg-blue-400 rounded-l" />
                        )}
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

            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-4">
                <button
                  onClick={() => {
                    if (canGoPrev) {
                      setSelectedChapter(orderedChapterIds[currentChapterIndex - 1])
                    }
                  }}
                  disabled={!canGoPrev}
                  className="flex items-center gap-1 px-3 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 text-sm"
                >
                  <ChevronLeft className="w-4 h-4" />
                  {t('preview.prevChapter')}
                </button>

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

                <button
                  onClick={() => {
                    if (canGoNext) {
                      setSelectedChapter(orderedChapterIds[currentChapterIndex + 1])
                    }
                  }}
                  disabled={!canGoNext}
                  className="flex items-center gap-1 px-3 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 text-sm"
                >
                  {t('preview.nextChapter')}
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto">
                {isLoadingContent ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
                  </div>
                ) : chapterContent ? (
                  <ReaderView
                    content={chapterContent}
                    projectId={projectId}
                    contentMode={contentMode}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

