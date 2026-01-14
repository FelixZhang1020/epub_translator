import { useState, useCallback, useMemo, useEffect } from 'react'
import { useParams, useOutletContext, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Download,
  Eye,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { WorkflowChapterList } from '../../components/workflow/WorkflowChapterList'
import { useOrderedChapterIds, usePanelResize } from '../../utils/workflow'

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
      progress: number  // 0-1 range from API
      completed_paragraphs: number
      total_paragraphs: number
    }
  } | null
  refetchWorkflow: () => void
}

type ExportType = 'epub' | 'pdf' | 'html'
type ExportFormat = 'bilingual' | 'translated'
type HtmlWidth = 'narrow' | 'medium' | 'wide' | 'full'
type PaperSize = 'A4' | 'Letter'

export function ExportPage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const context = useOutletContext<WorkflowContext>()

  // App store for font size
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  // Panel resize functionality from shared hook
  const { panelWidths, handleChapterListResize } = usePanelResize()

  // Fetch feature flags
  const { data: featureFlags } = useQuery({
    queryKey: ['featureFlags'],
    queryFn: () => api.getFeatureFlags(),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  // State
  const [previewChapter, setPreviewChapter] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  // Default to PDF if ePub is disabled
  const [exportType, setExportType] = useState<ExportType>(() => {
    return 'pdf' // Start with PDF, will adjust based on feature flags
  })
  const [exportFormat, setExportFormat] = useState<ExportFormat>('bilingual')
  const [htmlWidth, setHtmlWidth] = useState<HtmlWidth>('medium')
  const [paperSize, setPaperSize] = useState<PaperSize>('A4')
  const [selectedChaptersForExport, setSelectedChaptersForExport] = useState<Set<string>>(new Set())

  // Reset export type if ePub is disabled but currently selected
  useEffect(() => {
    if (featureFlags && !featureFlags.enable_epub_export && exportType === 'epub') {
      setExportType('pdf')
    }
  }, [featureFlags, exportType])

  // Fetch hierarchical TOC
  const { data: toc } = useQuery({
    queryKey: ['toc', projectId],
    queryFn: () => api.getToc(projectId!),
    enabled: !!projectId,
  })

  // Fetch chapters for preview selection
  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId!),
    enabled: !!projectId,
  })

  // Create ordered list of chapter IDs
  const orderedChapterIds = useOrderedChapterIds(toc, chapters)

  // Create chapter stats map for showing confirmed/total in tree
  const chapterStatsMap = useMemo(() => {
    if (!chapters) return undefined
    const map = new Map<string, { translated: number; total: number }>()
    for (const chapter of chapters) {
      map.set(chapter.id, {
        translated: chapter.confirmed_count,
        total: chapter.paragraph_count,
      })
    }
    return map
  }, [chapters])

  // Get selected chapter IDs as array for API calls
  const selectedChapterIdsArray = useMemo(() =>
    Array.from(selectedChaptersForExport),
    [selectedChaptersForExport]
  )

  // Fetch preview HTML - pass selected chapter IDs for filtering
  const { data: previewData, isLoading: isLoadingPreview } = useQuery({
    queryKey: ['exportPreview', projectId, exportType, exportType === 'epub' ? previewChapter : selectedChapterIdsArray],
    queryFn: () => {
      if (exportType === 'epub') {
        // ePub: single chapter preview
        return api.getExportPreview(projectId!, previewChapter || undefined)
      } else {
        // PDF/HTML: pass selected chapter IDs for filtered preview
        const chapterIds = selectedChapterIdsArray.length > 0 ? selectedChapterIdsArray : undefined
        return api.getExportPreview(projectId!, undefined, chapterIds)
      }
    },
    enabled: !!projectId && showPreview && (exportType !== 'epub' || !!previewChapter),
  })

  const previewSrcDoc = useMemo(() => {
    if (!previewData?.html) return null

    let sanitizedHtml = previewData.html

    // Always strip images for copyright compliance (exports are text-only)
    if (typeof DOMParser !== 'undefined') {
      try {
        const parser = new DOMParser()
        const doc = parser.parseFromString(previewData.html, 'text/html')

        // Remove all images and figures (copyright compliance)
        doc.querySelectorAll('img, figure, picture, svg[data-image]').forEach(el => el.remove())

        sanitizedHtml = doc.body.innerHTML || previewData.html
      } catch {
        // Fallback: regex-based removal
        sanitizedHtml = sanitizedHtml
          .replace(/<img[^>]*>/gi, '')
          .replace(/<figure[^>]*>[\s\S]*?<\/figure>/gi, '')
          .replace(/<picture[^>]*>[\s\S]*?<\/picture>/gi, '')
      }
    }

    if (exportFormat === 'translated' && typeof DOMParser !== 'undefined') {
      try {
        const parser = new DOMParser()
        const doc = parser.parseFromString(sanitizedHtml, 'text/html')

        // Remove untranslated paragraphs entirely (they have .untranslated class)
        doc.querySelectorAll('.bilingual-pair.untranslated').forEach(pair => {
          pair.remove()
        })

        // For translated pairs, remove original text and unwrap translated text
        doc.querySelectorAll('.bilingual-pair').forEach(pair => {
          const translated = pair.querySelector('.translated-text')

          // Remove all original-text elements
          pair.querySelectorAll('.original-text').forEach(el => el.remove())

          // Unwrap the translated content from the bilingual-pair container
          const parent = pair.parentElement
          if (parent && translated) {
            const fragment = doc.createDocumentFragment()
            Array.from(translated.childNodes).forEach(child => fragment.appendChild(child.cloneNode(true)))
            parent.insertBefore(fragment, pair.nextSibling)
            parent.removeChild(pair)
          }
        })

        sanitizedHtml = doc.body.innerHTML || previewData.html
      } catch (err) {
        console.warn('Failed to sanitize preview HTML', err)
      }
    }

    const isDarkMode = typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
    const translatedClass = exportFormat === 'translated' ? 'preview-translated' : ''
    const bodyClasses = [translatedClass, isDarkMode ? 'dark' : ''].filter(Boolean).join(' ')
    const darkModeStyles = isDarkMode
      ? `
      .preview-wrapper { background-color: #111827; color: #e5e7eb; }
      .preview-wrapper .original-text { color: #e5e7eb !important; }
      .preview-wrapper .translated-text { color: #60a5fa !important; }
      .preview-wrapper .bilingual-pair { border-bottom-color: #374151 !important; }
      `
      : ''

    return `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      :root { color-scheme: ${isDarkMode ? 'dark' : 'light'}; }
      body { margin: 0; padding: 0; background: transparent; text-align: left; }
      .preview-wrapper { box-sizing: border-box; padding: 16px; text-align: left; }
      .preview-translated .original-text { display: none !important; }
      ${darkModeStyles}
    </style>
  </head>
  <body class="${bodyClasses}">
    <div class="preview-wrapper">
      ${sanitizedHtml}
    </div>
  </body>
</html>
    `
  }, [exportFormat, previewData?.html])

  // Toggle chapter selection
  const toggleChapterSelection = useCallback((chapterId: string) => {
    setSelectedChaptersForExport(prev => {
      const next = new Set(prev)
      if (next.has(chapterId)) {
        next.delete(chapterId)
      } else {
        next.add(chapterId)
      }
      return next
    })
  }, [])

  // Select/deselect all chapters
  const handleSelectAllChapters = useCallback(() => {
    if (selectedChaptersForExport.size === orderedChapterIds.length) {
      setSelectedChaptersForExport(new Set())
    } else {
      setSelectedChaptersForExport(new Set(orderedChapterIds))
    }
  }, [orderedChapterIds, selectedChaptersForExport.size])

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: async () => {
      // Only export selected chapters - if none selected, this shouldn't be called
      // (button should be disabled)
      const chapterIds = Array.from(selectedChaptersForExport)

      let blob: Blob
      let filename: string
      const suffix = exportFormat === 'translated' ? 'translated' : 'bilingual'
      const bookName = context?.project?.name || 'book'

      try {
        if (exportType === 'html') {
          blob = await api.exportTextHtml(projectId!, {
            format: exportFormat,
            chapter_ids: chapterIds
          })
          filename = `${bookName}_text_${suffix}.html`
        } else if (exportType === 'pdf') {
          blob = await api.exportPdf(projectId!, {
            format: exportFormat,
            paper_size: paperSize,
            chapter_ids: chapterIds
          })
          filename = `${bookName}_${suffix}.pdf`
        } else {
          // ePub - use text-only export
          blob = await api.exportTextEpub(projectId!, {
            format: exportFormat,
            chapter_ids: chapterIds
          })
          filename = `${bookName}_text_${suffix}.epub`
        }
      } catch (error: unknown) {
        // Handle axios error - try to extract message from blob response
        const axiosError = error as { response?: { data?: Blob | { detail?: string } } }
        if (axiosError.response?.data instanceof Blob) {
          // Error response was returned as blob, try to read it as JSON
          try {
            const text = await axiosError.response.data.text()
            const json = JSON.parse(text)
            throw new Error(json.detail || 'Export failed')
          } catch {
            throw new Error('Export failed. Please check the server logs.')
          }
        } else if (axiosError.response?.data?.detail) {
          throw new Error(axiosError.response.data.detail)
        }
        throw error
      }

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
    onError: (error: Error) => {
      alert(`${t('export.exportFailed')}: ${error.message}`)
    },
  })

  // Calculate progress based on selected chapters - must have chapters selected to export
  const { canExport } = useMemo(() => {
    // Must have chapters selected to export
    if (selectedChaptersForExport.size === 0) {
      return { completedParagraphs: 0, totalParagraphs: 0, progressPercent: 0, canExport: false }
    }

    // If no chapters data yet, can't export
    if (!chapterStatsMap || chapterStatsMap.size === 0) {
      return { completedParagraphs: 0, totalParagraphs: 0, progressPercent: 0, canExport: false }
    }

    let completed = 0
    let total = 0

    for (const chapterId of selectedChaptersForExport) {
      const stats = chapterStatsMap.get(chapterId)
      if (stats) {
        completed += stats.translated
        total += stats.total
      }
    }

    const percent = total > 0 ? Math.round((completed / total) * 100) : 0
    // Allow export if selected chapters have content
    const exportable = total > 0

    return {
      completedParagraphs: completed,
      totalParagraphs: total,
      progressPercent: percent,
      canExport: exportable,
    }
  }, [chapterStatsMap, selectedChaptersForExport])

  // ePub preview chapter navigation - only for selected chapters
  const selectedChaptersList = chapters?.filter(ch => selectedChaptersForExport.has(ch.id)) ?? []
  const currentChapterIndex = selectedChaptersList.findIndex((c) => c.id === previewChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < selectedChaptersList.length - 1

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Action Bar - unified format */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-gray-700 mb-2">
        <div className="flex flex-wrap items-center gap-3">
          {/* Left Group: Back button (no LLM/Prompt needed for export) */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/project/${projectId}/proofread`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">{t('common.back')}</span>
            </button>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Center: Export options - can grow */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Export Type Switch: ePub / PDF / HTML */}
            <div className="flex items-center gap-2">
              <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>{t('export.exportType')}:</span>
              <div className="flex rounded-lg bg-gray-200 dark:bg-gray-700 p-0.5">
                {featureFlags?.enable_epub_export && (
                  <button
                    onClick={() => setExportType('epub')}
                    className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportType === 'epub'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                      }`}
                  >
                    ePub
                  </button>
                )}
                <button
                  onClick={() => setExportType('pdf')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportType === 'pdf'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  PDF
                </button>
                <button
                  onClick={() => setExportType('html')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportType === 'html'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  HTML
                </button>
              </div>
            </div>

            {/* Export Format Switch: Bilingual / Chinese Only */}
            <div className="flex items-center gap-2">
              <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>{t('export.format')}:</span>
              <div className="flex rounded-lg bg-gray-200 dark:bg-gray-700 p-0.5">
                <button
                  onClick={() => setExportFormat('bilingual')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportFormat === 'bilingual'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  {t('export.formatBilingual')}
                </button>
                <button
                  onClick={() => setExportFormat('translated')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportFormat === 'translated'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  {t('export.formatChineseOnly')}
                </button>
              </div>
            </div>

            {/* Paper Size Switch (only for PDF) - use visibility to reserve space */}
            <div className={`flex items-center gap-2 ${exportType === 'pdf' ? '' : 'hidden'}`}>
              <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>{t('export.paperSize')}:</span>
              <div className="flex rounded-lg bg-gray-200 dark:bg-gray-700 p-0.5">
                <button
                  onClick={() => setPaperSize('A4')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${paperSize === 'A4'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  A4
                </button>
                <button
                  onClick={() => setPaperSize('Letter')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${paperSize === 'Letter'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                >
                  Letter
                </button>
              </div>
            </div>

            {/* HTML Width Switch (only for HTML) */}
            <div className={`flex items-center gap-2 ${exportType === 'html' ? '' : 'hidden'}`}>
              <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>{t('export.htmlWidth')}:</span>
              <div className="flex rounded-lg bg-gray-200 dark:bg-gray-700 p-0.5">
                <button
                  onClick={() => setHtmlWidth('narrow')}
                  className={`px-2 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${htmlWidth === 'narrow'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                  title="600px"
                >
                  {t('export.widthNarrow')}
                </button>
                <button
                  onClick={() => setHtmlWidth('medium')}
                  className={`px-2 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${htmlWidth === 'medium'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                  title="800px"
                >
                  {t('export.widthMedium')}
                </button>
                <button
                  onClick={() => setHtmlWidth('wide')}
                  className={`px-2 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${htmlWidth === 'wide'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                  title="1000px"
                >
                  {t('export.widthWide')}
                </button>
                <button
                  onClick={() => setHtmlWidth('full')}
                  className={`px-2 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${htmlWidth === 'full'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                    }`}
                  title="100%"
                >
                  {t('export.widthFull')}
                </button>
              </div>
            </div>
          </div>

          {/* Right: Action buttons - fixed position, won't shift when options change */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Preview Toggle Button */}
            <button
              onClick={() => {
                if (!showPreview) {
                  // When opening preview, use first selected chapter or first available chapter
                  const firstSelectedId = selectedChaptersForExport.size > 0
                    ? Array.from(selectedChaptersForExport)[0]
                    : chapters?.[0]?.id
                  if (firstSelectedId) {
                    setPreviewChapter(firstSelectedId)
                  }
                }
                setShowPreview(!showPreview)
              }}
              disabled={selectedChaptersForExport.size === 0 && !showPreview}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              <Eye className="w-4 h-4" />
              {showPreview ? t('export.hidePreview') : t('export.showPreview')}
            </button>

            {/* Download Button */}
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending || !canExport}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {exportMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              {t('export.exportButton')}
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-x-auto">
        {/* Chapter list sidebar - using shared WorkflowChapterList with checkboxes */}
        <WorkflowChapterList
          width={panelWidths.chapterList}
          toc={toc}
          chapters={chapters}
          selectedChapterId={null}
          onSelectChapter={toggleChapterSelection}
          onResize={handleChapterListResize}
          fontClasses={fontClasses}
          title={t('export.selectChapters')}
          showCheckboxes={true}
          selectedChapterIds={selectedChaptersForExport}
          onSelectAll={handleSelectAllChapters}
          selectionText={
            selectedChaptersForExport.size === orderedChapterIds.length
              ? t('common.deselectAll')
              : t('common.selectAll')
          }
          chapterStatsMap={chapterStatsMap}
        />

        {/* Main content area - maintains minimum width */}
        <div className="flex-1 flex flex-col min-h-0 min-w-[500px] overflow-hidden">
          {/* Preview Panel */}
          <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col">
            {showPreview ? (
              <>
                {/* ePub mode: Show chapter navigation for page-by-page preview */}
                {exportType === 'epub' && (
                  <div className="flex items-center gap-2 p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                    <button
                      onClick={() => {
                        if (canGoPrev) {
                          setPreviewChapter(selectedChaptersList[currentChapterIndex - 1].id)
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
                      className={`flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}
                    >
                      {selectedChaptersList.map((ch) => (
                        <option key={ch.id} value={ch.id}>
                          {ch.title || t('preview.chapterNumber', { number: String(ch.chapter_number) })}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => {
                        if (canGoNext) {
                          setPreviewChapter(selectedChaptersList[currentChapterIndex + 1].id)
                        }
                      }}
                      disabled={!canGoNext}
                      className="p-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:text-gray-300 dark:disabled:text-gray-600"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                    <span className={`text-gray-400 ml-2 ${fontClasses.xs}`}>
                      {currentChapterIndex + 1} / {selectedChaptersList.length}
                    </span>
                  </div>
                )}

                {/* Preview content - constrained width with scroll */}
                <div className="flex-1 overflow-hidden">
                  {isLoadingPreview ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                    </div>
                  ) : previewSrcDoc ? (
                    <iframe
                      title="Export preview"
                      srcDoc={previewSrcDoc}
                      className="w-full h-full border-0 bg-white dark:bg-gray-900"
                      sandbox="allow-same-origin"
                    />
                  ) : (
                    <div className={`text-center py-12 text-gray-500 dark:text-gray-400 ${fontClasses.paragraph}`}>
                      {t('export.noPreview')}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500">
                <div className="text-center p-8">
                  {orderedChapterIds.length > 0 ? (
                    <>
                      <p className={fontClasses.sm}>{t('export.selectChaptersHint')}</p>
                      <p className={`mt-2 ${fontClasses.xs}`}>{t('export.clickToPreview')}</p>
                    </>
                  ) : (
                    <p className={fontClasses.sm}>{t('export.noChaptersToExport')}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
