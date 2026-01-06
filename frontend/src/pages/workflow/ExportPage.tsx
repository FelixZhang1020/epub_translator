import { useState } from 'react'
import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Download,
  Eye,
  Loader2,
  CheckCircle,
  AlertTriangle,
  FileText,
  BookOpen,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

interface WorkflowContext {
  project: {
    id: string
    name: string
    total_chapters: number
    total_paragraphs: number
  } | null
  workflowStatus: {
    translation_completed: boolean
    proofreading_completed: boolean
    translation_progress?: {
      completed_paragraphs: number
      total_paragraphs: number
    }
  } | null
  refetchWorkflow: () => void
}

export function ExportPage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const context = useOutletContext<WorkflowContext>()

  // State
  const [previewChapter, setPreviewChapter] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)

  // Fetch chapters for preview selection
  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId!),
    enabled: !!projectId,
  })

  // Fetch preview HTML
  const { data: previewData, isLoading: isLoadingPreview } = useQuery({
    queryKey: ['exportPreview', projectId, previewChapter],
    queryFn: async () => {
      const response = await fetch(`/api/v1/export/${projectId}/preview${previewChapter ? `?chapter_id=${previewChapter}` : ''}`)
      return response.json()
    },
    enabled: !!projectId && showPreview,
  })

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await api.exportEpub(projectId!)
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${context?.project?.name || 'book'}_bilingual.epub`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
  })

  // Calculate progress
  const translationProgress = context?.workflowStatus?.translation_progress
  const completedParagraphs = translationProgress?.completed_paragraphs || 0
  const totalParagraphs = translationProgress?.total_paragraphs || context?.project?.total_paragraphs || 0
  const progressPercent = totalParagraphs > 0 ? Math.round((completedParagraphs / totalParagraphs) * 100) : 0
  const isComplete = progressPercent === 100

  // Preview chapter navigation
  const currentChapterIndex = chapters?.findIndex((c) => c.id === previewChapter) ?? -1
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = chapters && currentChapterIndex < chapters.length - 1 && currentChapterIndex >= 0

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
        <div>
          <h2 className="text-lg font-medium">{t('export.title')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('export.subtitle')}</p>
        </div>

        <button
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending || !isComplete}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed"
        >
          {exportMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {t('export.downloadEpub')}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        {/* Stats and Options */}
        <div className="col-span-1 space-y-4">
          {/* Project Info */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <BookOpen className="w-4 h-4" />
              {t('export.projectInfo')}
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('export.bookTitle')}</span>
                <span className="font-medium">{context?.project?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('export.totalChapters')}</span>
                <span className="font-medium">{context?.project?.total_chapters}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{t('export.totalParagraphs')}</span>
                <span className="font-medium">{context?.project?.total_paragraphs}</span>
              </div>
            </div>
          </div>

          {/* Translation Status */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              {t('export.translationStatus')}
            </h3>

            <div className="mb-2">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500 dark:text-gray-400">{t('export.progress')}</span>
                <span className="font-medium">{progressPercent}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${isComplete ? 'bg-green-500' : 'bg-blue-600'}`}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                {completedParagraphs} / {totalParagraphs} {t('export.paragraphsTranslated')}
              </div>
            </div>

            <div className={`flex items-center gap-2 p-2 rounded ${isComplete ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'}`}>
              {isComplete ? (
                <>
                  <CheckCircle className="w-4 h-4" />
                  <span className="text-sm">{t('export.readyToExport')}</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-sm">{t('export.translationIncomplete')}</span>
                </>
              )}
            </div>
          </div>

          {/* Export Format */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="font-medium mb-3">{t('export.format')}</h3>
            <div className="space-y-2">
              <label className="flex items-center gap-2 p-2 border border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-900/20 rounded cursor-pointer">
                <input type="radio" name="format" defaultChecked className="text-blue-600" />
                <div>
                  <div className="text-sm font-medium">{t('export.formatBilingual')}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{t('export.formatBilingualDesc')}</div>
                </div>
              </label>
              <label className="flex items-center gap-2 p-2 border border-gray-200 dark:border-gray-700 rounded cursor-pointer opacity-50">
                <input type="radio" name="format" disabled className="text-gray-400" />
                <div>
                  <div className="text-sm font-medium">{t('export.formatChineseOnly')}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{t('export.comingSoon')}</div>
                </div>
              </label>
            </div>
          </div>

          {/* Preview toggle */}
          <button
            onClick={() => {
              setShowPreview(!showPreview)
              if (!previewChapter && chapters?.length) {
                setPreviewChapter(chapters[0].id)
              }
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-200"
          >
            <Eye className="w-4 h-4" />
            {showPreview ? t('export.hidePreview') : t('export.showPreview')}
          </button>
        </div>

        {/* Preview Panel */}
        <div className="col-span-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
          {showPreview ? (
            <>
              {/* Preview header */}
              <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (canGoPrev && chapters) {
                        setPreviewChapter(chapters[currentChapterIndex - 1].id)
                      }
                    }}
                    disabled={!canGoPrev}
                    className="p-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:text-gray-300 dark:disabled:text-gray-600"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <select
                    value={previewChapter || ''}
                    onChange={(e) => setPreviewChapter(e.target.value)}
                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">{t('export.allChapters')}</option>
                    {chapters?.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        {ch.title || t('preview.chapterNumber', { number: String(ch.chapter_number) })}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => {
                      if (canGoNext && chapters) {
                        setPreviewChapter(chapters[currentChapterIndex + 1].id)
                      }
                    }}
                    disabled={!canGoNext}
                    className="p-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:text-gray-300 dark:disabled:text-gray-600"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
                <span className="text-xs text-gray-400 dark:text-gray-500">{t('export.previewNote')}</span>
              </div>

              {/* Preview content */}
              <div className="flex-1 overflow-y-auto p-4">
                {isLoadingPreview ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                  </div>
                ) : previewData?.html ? (
                  <div
                    className="prose prose-sm max-w-none dark:prose-invert"
                    dangerouslySetInnerHTML={{ __html: previewData.html }}
                  />
                ) : (
                  <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    {t('export.noPreview')}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500">
              <div className="text-center">
                <Eye className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>{t('export.clickToPreview')}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
