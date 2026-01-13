import { useState, useCallback, useMemo } from 'react'
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
  ChevronsDownUp,
  ChevronsUpDown,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { TreeChapterList } from '../../components/common/TreeChapterList'
import { ResizeHandle } from '../../components/common/ResizeHandle'
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
  const context = useOutletContext<WorkflowContext>()

  // App store for font size
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  // Panel resize functionality from shared hook
  const { panelWidths, handleChapterListResize } = usePanelResize()

  // State
  const [previewChapter, setPreviewChapter] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [exportType, setExportType] = useState<ExportType>('epub')
  const [exportFormat, setExportFormat] = useState<ExportFormat>('bilingual')
  const [htmlWidth, setHtmlWidth] = useState<HtmlWidth>('medium')
  const [paperSize, setPaperSize] = useState<PaperSize>('A4')
  const [selectedChaptersForExport, setSelectedChaptersForExport] = useState<Set<string>>(new Set())
  const [expandAllChapters, setExpandAllChapters] = useState(false)

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

  // Fetch preview HTML - different behavior for ePub vs HTML
  const { data: previewData, isLoading: isLoadingPreview } = useQuery({
    queryKey: ['exportPreview', projectId, exportType, exportType === 'epub' ? previewChapter : 'all'],
    queryFn: () => {
      const chapterId = exportType === 'epub' ? previewChapter || undefined : undefined
      return api.getExportPreview(projectId!, chapterId)
    },
    enabled: !!projectId && showPreview && (exportType === 'html' || !!previewChapter),
  })

  const previewSrcDoc = useMemo(() => {
    if (!previewData?.html) return null

    let sanitizedHtml = previewData.html
    if (exportFormat === 'translated' && typeof DOMParser !== 'undefined') {
      try {
        const parser = new DOMParser()
        const doc = parser.parseFromString(previewData.html, 'text/html')

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
      body { margin: 0; padding: 0; background: transparent; }
      .preview-wrapper { box-sizing: border-box; padding: 16px; }
      .preview-wrapper img, .preview-wrapper svg { max-width: 100%; height: auto; }
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
      const chapterIds = selectedChaptersForExport.size > 0
        ? Array.from(selectedChaptersForExport)
        : undefined

      let blob: Blob
      let filename: string
      const suffix = exportFormat === 'translated' ? 'translated' : 'bilingual'
      const bookName = context?.project?.name || 'book'

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
  })

  // Calculate progress - use translation_completed flag first, then API progress
  const translationCompleted = context?.workflowStatus?.translation_completed ?? false
  const translationProgress = context?.workflowStatus?.translation_progress
  const completedParagraphs = translationProgress?.completed_paragraphs ?? 0
  const totalParagraphs = translationProgress?.total_paragraphs ?? context?.project?.total_paragraphs ?? 0
  // If no paragraphs exist, show 0% and not complete
  // Otherwise, if translation is completed, show 100%, else use API's progress value (0-1 range)
  const hasContent = totalParagraphs > 0
  const progressPercent = !hasContent
    ? 0
    : translationCompleted
      ? 100
      : Math.round((translationProgress?.progress ?? 0) * 100)
  const isComplete = hasContent && (translationCompleted || progressPercent === 100)

  // ePub preview chapter navigation - only for selected chapters
  const selectedChaptersList = chapters?.filter(ch => selectedChaptersForExport.has(ch.id)) ?? []
  const currentChapterIndex = selectedChaptersList.findIndex((c) => c.id === previewChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < selectedChaptersList.length - 1

  // Chapter selection info
  const selectedCount = selectedChaptersForExport.size
  const selectionText = selectedCount === 0
    ? t('export.allChaptersSelected')
    : t('export.chaptersSelected', { count: String(selectedCount) })

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Action Bar - unified format with inline switches */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2 bg-white dark:bg-gray-800 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
        {/* Left side: Title and status */}
        <div className="flex items-center gap-3">
          <h2 className={`font-semibold text-gray-900 dark:text-gray-100 ${fontClasses.heading}`}>{t('workflow.export')}</h2>
          {isComplete ? (
            <span className={`flex items-center gap-1 px-2 py-0.5 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded ${fontClasses.sm}`}>
              <CheckCircle className="w-3.5 h-3.5" />
              {t('export.readyToExport')}
            </span>
          ) : (
            <span className={`flex items-center gap-1 px-2 py-0.5 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded ${fontClasses.sm}`}>
              <AlertTriangle className="w-3.5 h-3.5" />
              {progressPercent}%
            </span>
          )}
        </div>

        {/* Right side: Switches and Download button */}
        <div className="flex items-center gap-4">
          {/* Export Type Switch: ePub / PDF / HTML */}
          <div className="flex items-center gap-2">
            <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>{t('export.exportType')}:</span>
            <div className="flex rounded-lg bg-gray-200 dark:bg-gray-700 p-0.5">
              <button
                onClick={() => setExportType('epub')}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${fontClasses.xs} ${exportType === 'epub'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
              >
                ePub
              </button>
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

          {/* Export Format Switch: Bilingual / Chinese Only (for ePub, PDF, HTML) */}
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

          {/* Paper Size Switch (only for PDF) */}
          {exportType === 'pdf' && (
            <div className="flex items-center gap-2">
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
          )}

          {/* HTML Width Switch (only for HTML) */}
          {exportType === 'html' && (
            <div className="flex items-center gap-2">
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
          )}


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
            className={`flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700 dark:text-gray-300 ${fontClasses.button}`}
          >
            <Eye className="w-4 h-4" />
            {showPreview ? t('export.hidePreview') : t('export.showPreview')}
          </button>

          {/* Download Button */}
          <button
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending || !isComplete}
            className={`flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed ${fontClasses.button}`}
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

      <div className="flex flex-1 min-h-0 overflow-x-auto">
        {/* Chapter list sidebar - resizable width */}
        <div
          className="hidden lg:flex lg:flex-col flex-shrink-0 self-stretch"
          style={{ width: panelWidths.chapterList }}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2 h-full overflow-y-auto">
            <div className="flex items-center justify-between mb-1.5">
              <h3 className={`font-medium text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>{t('preview.chapterList')}</h3>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleSelectAllChapters}
                  className={`text-blue-600 dark:text-blue-400 hover:underline ${fontClasses.xs}`}
                  title={selectionText}
                >
                  {selectedChaptersForExport.size === orderedChapterIds.length
                    ? t('common.deselectAll')
                    : t('common.selectAll')}
                </button>
                {toc && toc.length > 0 && (
                  <button
                    onClick={() => setExpandAllChapters(!expandAllChapters)}
                    className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title={expandAllChapters ? t('preview.collapseAll') : t('preview.expandAll')}
                  >
                    {expandAllChapters ? (
                      <ChevronsDownUp className="w-4 h-4" />
                    ) : (
                      <ChevronsUpDown className="w-4 h-4" />
                    )}
                  </button>
                )}
              </div>
            </div>
            <div>
              {toc && toc.length > 0 ? (
                <TreeChapterList
                  toc={toc}
                  selectedChapterId={null}
                  onSelectChapter={toggleChapterSelection}
                  fontClasses={fontClasses}
                  expandAll={expandAllChapters}
                  showCheckboxes={true}
                  selectedChapterIds={selectedChaptersForExport}
                  chapterStatsMap={chapterStatsMap}
                />
              ) : chapters?.length ? (
                <div className="space-y-0.5">
                  {chapters.map((chapter) => (
                    <label
                      key={chapter.id}
                      className={`flex items-center gap-2 px-1.5 py-1 rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 ${fontClasses.paragraph} text-gray-700 dark:text-gray-300`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedChaptersForExport.has(chapter.id)}
                        onChange={() => toggleChapterSelection(chapter.id)}
                        className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="truncate flex-1">
                        {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                      </span>
                      <span className={`${fontClasses.xs} text-gray-400 dark:text-gray-500`}>
                        {chapter.confirmed_count} / {chapter.paragraph_count}
                      </span>
                    </label>
                  ))}
                </div>
              ) : (
                <div className={`text-gray-500 dark:text-gray-400 ${fontClasses.paragraph} text-center py-4`}>
                  {t('preview.noChapters')}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Resize handle for chapter list */}
        <div className="hidden lg:flex self-stretch">
          <ResizeHandle onResize={handleChapterListResize} className="h-full" />
        </div>

        {/* Main content area - overflow-hidden to contain preview content */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
          {/* Stats Row - flexbox with fixed widths for stability */}
          <div className="flex gap-4 mb-4">
            {/* Project Info - fills remaining space */}
            <div className="flex-1 min-w-0 bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className={`font-medium mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>
                <BookOpen className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                {t('export.projectInfo')}
              </h3>
              <div className={`grid grid-cols-3 gap-4 ${fontClasses.sm}`}>
                <div>
                  <span className={`text-gray-500 dark:text-gray-400 block ${fontClasses.xs}`}>{t('export.bookTitle')}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100 truncate block">{context?.project?.name}</span>
                </div>
                <div>
                  <span className={`text-gray-500 dark:text-gray-400 block ${fontClasses.xs}`}>{t('export.totalChapters')}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{context?.project?.total_chapters}</span>
                </div>
                <div>
                  <span className={`text-gray-500 dark:text-gray-400 block ${fontClasses.xs}`}>{t('export.totalParagraphs')}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{context?.project?.total_paragraphs}</span>
                </div>
              </div>
            </div>

            {/* Translation Status - fixed width */}
            <div className="w-64 flex-shrink-0 bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className={`font-medium mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>
                <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                {t('export.translationStatus')}
              </h3>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${isComplete ? 'bg-green-500' : 'bg-blue-600'}`}
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
                <span className={`font-medium text-gray-900 dark:text-gray-100 ${fontClasses.sm}`}>{progressPercent}%</span>
              </div>
              <div className={`text-gray-400 dark:text-gray-500 mt-1 ${fontClasses.xs}`}>
                {translationCompleted
                  ? `${totalParagraphs} / ${totalParagraphs}`
                  : `${completedParagraphs} / ${totalParagraphs}`} {t('export.paragraphsTranslated')}
              </div>
            </div>
          </div>

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
