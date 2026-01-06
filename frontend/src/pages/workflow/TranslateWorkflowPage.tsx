import { useState, useCallback, useEffect, useMemo } from 'react'
import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  ChevronLeft,
  ChevronRight,
  Edit2,
  Save,
  X,
  Loader2,
  Check,
  Lightbulb,
  Trash2,
  Play,
  FileText,
  BookOpen,
  PanelRightClose,
  Search,
  RefreshCw,
} from 'lucide-react'
import { api, TocItem, ChapterImage } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptPreviewModal } from '../../components/common/PromptPreviewModal'
import { TreeChapterList } from '../../components/common/TreeChapterList'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import { ResizeHandle } from '../../components/common/ResizeHandle'
import { PreviewModal } from '../../components/preview/PreviewModal'
import { ReasoningChatModal } from '../../components/translation/ReasoningChatModal'

// Helper function to flatten TOC into ordered chapter IDs for navigation
function flattenTocToChapterIds(toc: TocItem[]): string[] {
  const result: string[] = []
  for (const item of toc) {
    if (item.chapter_id) {
      result.push(item.chapter_id)
    }
    if (item.children && item.children.length > 0) {
      result.push(...flattenTocToChapterIds(item.children))
    }
  }
  return result
}

interface WorkflowContext {
  project: {
    id: string
    name: string
    has_reference_epub?: boolean
  } | null
  workflowStatus: {
    has_reference_epub: boolean
    translation_progress?: {
      has_task: boolean
      task_id?: string
      status?: string
      progress: number
      completed_paragraphs: number
      total_paragraphs: number
    }
  } | null
  refetchWorkflow: () => void
}

export function TranslateWorkflowPage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()
  const context = useOutletContext<WorkflowContext>()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const panelWidths = useAppStore((state) => state.panelWidths)
  const setPanelWidth = useAppStore((state) => state.setPanelWidth)

  // Panel width constraints
  const MIN_CHAPTER_LIST_WIDTH = 120
  const MAX_CHAPTER_LIST_WIDTH = 400
  const MIN_REFERENCE_PANEL_WIDTH = 200
  const MAX_REFERENCE_PANEL_WIDTH = 500

  // Resize handlers
  const handleChapterListResize = useCallback((delta: number) => {
    const newWidth = Math.max(
      MIN_CHAPTER_LIST_WIDTH,
      Math.min(MAX_CHAPTER_LIST_WIDTH, panelWidths.chapterList + delta)
    )
    setPanelWidth('chapterList', newWidth)
  }, [panelWidths.chapterList, setPanelWidth])

  const handleReferencePanelResize = useCallback((delta: number) => {
    // For reference panel, negative delta means making it wider (dragging left)
    const newWidth = Math.max(
      MIN_REFERENCE_PANEL_WIDTH,
      Math.min(MAX_REFERENCE_PANEL_WIDTH, panelWidths.referencePanel - delta)
    )
    setPanelWidth('referencePanel', newWidth)
  }, [panelWidths.referencePanel, setPanelWidth])

  // State
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [editingParagraph, setEditingParagraph] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [confirmedParagraphs, setConfirmedParagraphs] = useState<Set<string>>(new Set())
  const [showReasoningChat, setShowReasoningChat] = useState<{
    translationId: string
    paragraphId: string
    originalText: string
    translatedText: string
  } | null>(null)

  // Prompt preview state
  const [showTranslationPromptPreview, setShowTranslationPromptPreview] = useState(false)
  const [showReasoningPromptPreview, setShowReasoningPromptPreview] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)

  // Reference panel state
  const [showReferencePanel, setShowReferencePanel] = useState(false)
  const [selectedRefChapter, setSelectedRefChapter] = useState<number | null>(null)
  const [refSearchQuery, setRefSearchQuery] = useState('')
  const [refSearchInputValue, setRefSearchInputValue] = useState('')
  const [highlightedRefParagraph, setHighlightedRefParagraph] = useState<number | null>(null)

  // LLM config from settings store
  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // Check if has reference EPUB
  const hasReference = context?.workflowStatus?.has_reference_epub ?? false

  // Get translation progress from workflow status
  const translationProgress = context?.workflowStatus?.translation_progress
  const isTranslating = translationProgress?.status === 'processing' || translationProgress?.status === 'pending'
  const translationStatus = translationProgress?.status

  // Track previous translation status to detect completion
  const [prevTranslationStatus, setPrevTranslationStatus] = useState<string | undefined>(undefined)

  // Fetch hierarchical TOC
  const { data: toc } = useQuery({
    queryKey: ['toc', projectId],
    queryFn: () => api.getToc(projectId!),
    enabled: !!projectId,
  })

  // Fetch book analysis for prompt preview variables
  const { data: analysisData } = useQuery({
    queryKey: ['analysis', projectId],
    queryFn: () => api.getAnalysis(projectId!),
    enabled: !!projectId,
  })

  // Also fetch flat chapters for fallback
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

  // Extract prompt preview variables from analysis data
  const promptPreviewVariables = useMemo(() => {
    const rawAnalysis = analysisData?.raw_analysis as Record<string, unknown> | null
    if (!rawAnalysis) {
      return {
        source_text: '(Source text will be provided during translation)',
        analysis_text: '',
        author_biography: '',
        writing_style: '',
        tone: '',
        target_audience: '',
        genre_conventions: '',
        key_terminology: '',
        translation_principles: '',
        custom_guidelines: '',
      }
    }

    // Format key_terminology for display
    const terminology = rawAnalysis.key_terminology as Record<string, string> | undefined
    const terminologyText = terminology
      ? Object.entries(terminology).map(([en, zh]) => `${en}: ${zh}`).join('\n')
      : ''

    // Format translation_principles for display
    const principles = rawAnalysis.translation_principles as Record<string, unknown> | undefined
    const principlesText = principles ? JSON.stringify(principles, null, 2) : ''

    // Format custom_guidelines for display
    const guidelines = rawAnalysis.custom_guidelines as string[] | undefined
    const guidelinesText = guidelines ? guidelines.join('\n') : ''

    return {
      source_text: '(Source text will be provided during translation)',
      analysis_text: JSON.stringify(rawAnalysis, null, 2),
      author_biography: (rawAnalysis.author_biography as string) || '',
      writing_style: (rawAnalysis.writing_style as string) || '',
      tone: (rawAnalysis.tone as string) || '',
      target_audience: (rawAnalysis.target_audience as string) || '',
      genre_conventions: (rawAnalysis.genre_conventions as string) || '',
      key_terminology: terminologyText,
      translation_principles: principlesText,
      custom_guidelines: guidelinesText,
    }
  }, [analysisData])

  // Fetch reference EPUB info
  const { data: referenceEpub } = useQuery({
    queryKey: ['referenceEpub', projectId],
    queryFn: () => api.getReferenceEpub(projectId!),
    enabled: !!projectId && hasReference,
    retry: false,
  })

  // Fetch reference chapters list
  const { data: referenceChapters } = useQuery({
    queryKey: ['referenceChapters', projectId],
    queryFn: () => api.getReferenceChapters(projectId!),
    enabled: !!projectId && hasReference && showReferencePanel,
    retry: false,
  })

  // Fetch reference chapter content
  const { data: referenceChapterContent, isLoading: isLoadingRefContent } = useQuery({
    queryKey: ['referenceChapterContent', projectId, selectedRefChapter],
    queryFn: () => api.getReferenceChapterContent(projectId!, selectedRefChapter!),
    enabled: !!projectId && hasReference && showReferencePanel && selectedRefChapter !== null && !refSearchQuery,
    retry: false,
  })

  // Search reference content
  const { data: searchResults, isLoading: isSearchingRef } = useQuery({
    queryKey: ['referenceSearch', projectId, refSearchQuery],
    queryFn: () => api.searchReferenceContent(projectId!, refSearchQuery, 50),
    enabled: !!projectId && hasReference && showReferencePanel && refSearchQuery.length > 0,
    retry: false,
  })

  // Auto-select first reference chapter when panel opens
  useEffect(() => {
    if (showReferencePanel && referenceChapters && referenceChapters.length > 0 && selectedRefChapter === null) {
      setSelectedRefChapter(referenceChapters[0].chapter_number)
    }
  }, [showReferencePanel, referenceChapters, selectedRefChapter])

  // Fetch chapter content (auto-refetch while translating)
  const { data: chapterContent, isLoading: isLoadingContent, refetch: refetchChapterContent } = useQuery({
    queryKey: ['chapter', projectId, selectedChapter],
    queryFn: () => api.getChapterContent(projectId!, selectedChapter!),
    enabled: !!projectId && !!selectedChapter,
    refetchInterval: isTranslating ? 3000 : false, // Refetch every 3s while translating
  })

  // Trigger final refetch when translation completes to catch any remaining paragraphs
  useEffect(() => {
    if (prevTranslationStatus && translationStatus !== prevTranslationStatus) {
      // Status changed - check if translation just completed
      if ((prevTranslationStatus === 'processing' || prevTranslationStatus === 'pending') &&
          translationStatus === 'completed') {
        // Translation just completed - do a final refetch after a short delay
        // to ensure all final commits are persisted
        const timer = setTimeout(() => {
          refetchChapterContent()
        }, 500)
        return () => clearTimeout(timer)
      }
    }
    setPrevTranslationStatus(translationStatus)
  }, [translationStatus, prevTranslationStatus, refetchChapterContent])

  // Select first chapter by default
  useEffect(() => {
    if (orderedChapterIds.length > 0 && !selectedChapter) {
      setSelectedChapter(orderedChapterIds[0])
    }
  }, [orderedChapterIds, selectedChapter])

  // Get paragraphs from chapter content
  const paragraphs = chapterContent?.paragraphs || []

  // Upload reference mutation
  const uploadReferenceMutation = useMutation({
    mutationFn: async (file: File) => {
      const result = await api.uploadReferenceEpub(projectId!, file)
      // Auto-match after upload
      await api.autoMatchParagraphs(projectId!)
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referenceEpub', projectId] })
      queryClient.invalidateQueries({ queryKey: ['matches', projectId] })
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      context?.refetchWorkflow()
    },
  })

  // Delete reference mutation
  const deleteReferenceMutation = useMutation({
    mutationFn: () => api.deleteReferenceEpub(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referenceEpub', projectId] })
      queryClient.invalidateQueries({ queryKey: ['matches', projectId] })
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      context?.refetchWorkflow()
    },
  })

  // Update translation mutation
  const updateMutation = useMutation({
    mutationFn: ({ paragraphId, text }: { paragraphId: string; text: string }) =>
      api.updateTranslation(paragraphId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
      setEditingParagraph(null)
    },
  })

  // Start translation mutation - clears existing translations first, then translates current chapter
  const startTranslationMutation = useMutation({
    mutationFn: async (params?: { customSystemPrompt?: string; customUserPrompt?: string }) => {
      // Get current chapter info for translation scope
      const currentChapterNumber = chapterContent?.chapter_number
      const currentChapterId = chapterContent?.id
      if (!currentChapterNumber || !currentChapterId) {
        throw new Error('No chapter selected')
      }

      // First, clear all existing translations for this chapter
      await api.clearChapterTranslations(currentChapterId)

      // Then start fresh translation
      return api.startTranslation({
        project_id: projectId!,
        mode: 'author_based',
        config_id: configId || undefined,
        chapters: [currentChapterNumber],  // Only translate current chapter
        custom_system_prompt: params?.customSystemPrompt,
        custom_user_prompt: params?.customUserPrompt,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
    },
  })

  // Retranslate single paragraph mutation
  const retranslateMutation = useMutation({
    mutationFn: (paragraphId: string) =>
      api.retranslateParagraph(paragraphId, {
        config_id: configId || undefined,
        mode: 'author_aware',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
    },
  })

  // Handler for translation prompt confirmation
  const handleTranslationPromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    setShowTranslationPromptPreview(false)
    startTranslationMutation.mutate({
      customSystemPrompt: systemPrompt,
      customUserPrompt: userPrompt,
    })
  }

  // Handler for reasoning prompt confirmation (not currently used - reasoning triggered directly)
  const handleReasoningPromptConfirm = () => {
    setShowReasoningPromptPreview(false)
  }

  // Start translation directly without prompt preview
  const handleStartTranslationClick = () => {
    startTranslationMutation.mutate({})
  }

  // Handle file upload for reference
  const handleReferenceUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && file.name.endsWith('.epub')) {
      uploadReferenceMutation.mutate(file)
    }
  }, [uploadReferenceMutation])

  // Handle reference search
  const handleRefSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    setRefSearchQuery(refSearchInputValue.trim())
  }, [refSearchInputValue])

  // Clear reference search
  const handleClearRefSearch = useCallback(() => {
    setRefSearchQuery('')
    setRefSearchInputValue('')
  }, [])

  // Handle click on search result to navigate to chapter and highlight paragraph
  const handleSearchResultClick = useCallback((chapterNumber: number, paragraphNumber: number) => {
    setSelectedRefChapter(chapterNumber)
    setHighlightedRefParagraph(paragraphNumber)
    setRefSearchQuery('')
    setRefSearchInputValue('')
    // Clear highlight after 3 seconds
    setTimeout(() => setHighlightedRefParagraph(null), 3000)
  }, [])

  // Handle edit
  const handleEdit = (paragraphId: string, currentText: string) => {
    setEditingParagraph(paragraphId)
    setEditText(currentText || '')
  }

  // Handle save
  const handleSave = (paragraphId: string) => {
    updateMutation.mutate({ paragraphId, text: editText })
  }

  // Toggle confirm status for a paragraph
  const handleToggleConfirm = (paragraphId: string) => {
    setConfirmedParagraphs((prev) => {
      const next = new Set(prev)
      if (next.has(paragraphId)) {
        next.delete(paragraphId)
      } else {
        next.add(paragraphId)
      }
      return next
    })
  }

  // Handle reasoning request - opens chat modal
  const handleRequestReasoning = (paragraphId: string, translationId: string | undefined, originalText: string, translatedText: string) => {
    if (!translationId) return
    setShowReasoningChat({
      translationId,
      paragraphId,
      originalText,
      translatedText,
    })
  }

  // Navigation helpers
  const currentChapterIndex = orderedChapterIds.findIndex((id) => id === selectedChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < orderedChapterIds.length - 1

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Header with controls - compact */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 bg-white dark:bg-gray-800 p-2 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 lg:gap-4">
          {/* Reference EPUB status */}
          {hasReference && referenceEpub ? (
            <div className={`flex items-center gap-2 ${fontClasses.base}`}>
              <FileText className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0" />
              <span className="hidden sm:inline text-gray-600 dark:text-gray-400">{t('translate.referenceLoaded')}: </span>
              <span className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[150px] lg:max-w-none">{referenceEpub.filename}</span>
              <span className={`hidden md:inline text-gray-400 dark:text-gray-500 ${fontClasses.xs}`}>
                ({referenceEpub.total_chapters} {t('translate.chapters')}, {referenceEpub.total_paragraphs} {t('translate.paragraphs')})
              </span>
              <button
                onClick={() => deleteReferenceMutation.mutate()}
                className="p-1 text-red-500 hover:text-red-700 flex-shrink-0"
                title={t('translate.removeReference')}
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setShowReferencePanel(!showReferencePanel)}
                className={`flex items-center gap-2 px-2 lg:px-3 py-1.5 border rounded-lg flex-shrink-0 transition-colors ${
                  showReferencePanel
                    ? 'border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                } ${fontClasses.button}`}
                title={showReferencePanel ? t('translate.hideReferencePanel') : t('translate.showReferencePanel')}
              >
                {showReferencePanel ? <PanelRightClose className="w-4 h-4" /> : <BookOpen className="w-4 h-4" />}
                <span className="hidden lg:inline">{t('translate.reference')}</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <label className={`flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/50 ${fontClasses.button}`}>
                <Upload className="w-4 h-4" />
                {t('translate.uploadReference')}
                <input
                  type="file"
                  accept=".epub"
                  onChange={handleReferenceUpload}
                  className="hidden"
                  disabled={uploadReferenceMutation.isPending}
                />
              </label>
              {uploadReferenceMutation.isPending && (
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 lg:gap-3">
          {/* LLM Config selector */}
          <LLMConfigSelector />

          <button
            onClick={() => setShowTranslationPromptPreview(true)}
            disabled={!hasLLMConfig}
            className={`flex items-center gap-2 px-2 lg:px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 ${fontClasses.button}`}
            title={t('prompts.viewPrompt')}
          >
            <FileText className="w-4 h-4" />
            <span className="hidden lg:inline">{t('prompts.viewPrompt')}</span>
          </button>

          {/* Start translation button - translates current chapter only */}
          <button
            onClick={handleStartTranslationClick}
            disabled={!hasLLMConfig || !chapterContent || startTranslationMutation.isPending || isTranslating}
            title={chapterContent ? t('translate.translateChapterHint', { chapter: chapterContent.title || String(chapterContent.chapter_number) }) : ''}
            className={`flex items-center gap-2 px-3 lg:px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed ${fontClasses.button}`}
          >
            {(startTranslationMutation.isPending || isTranslating) ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">{isTranslating ? t('translate.translating') : t('translate.translateCurrentChapter')}</span>
          </button>
          <button
            onClick={() => setShowPreviewModal(true)}
            className={`flex items-center gap-2 px-2 lg:px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.button}`}
          >
            <BookOpen className="w-4 h-4" />
            <span className="hidden lg:inline">{t('common.preview')}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-x-auto">
        {/* Chapter list sidebar - resizable width */}
        <div
          className="hidden lg:flex lg:flex-col flex-shrink-0"
          style={{ width: panelWidths.chapterList }}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2 h-full overflow-y-auto">
            <h3 className={`font-medium text-gray-900 dark:text-gray-100 mb-1.5 ${fontClasses.sm}`}>{t('preview.chapterList')}</h3>
            {toc && toc.length > 0 ? (
              <TreeChapterList
                toc={toc}
                selectedChapterId={selectedChapter}
                onSelectChapter={setSelectedChapter}
                fontClasses={fontClasses}
              />
            ) : chapters?.length ? (
              <div className="space-y-0.5">
                {chapters.map((chapter) => (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter.id)}
                    className={`w-full text-left px-1.5 py-1 rounded ${fontClasses.paragraph} transition-colors ${
                      selectedChapter === chapter.id
                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="font-medium truncate">
                      {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                    </div>
                    <div className={`${fontClasses.xs} text-gray-400 dark:text-gray-500`}>
                      {chapter.paragraph_count} {t('home.paragraphs')}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className={`text-gray-500 dark:text-gray-400 ${fontClasses.paragraph} text-center py-4`}>
                {t('preview.noChapters')}
              </div>
            )}
          </div>
        </div>

        {/* Resize handle for chapter list */}
        <div className="hidden lg:flex h-full">
          <ResizeHandle onResize={handleChapterListResize} className="h-full" />
        </div>

        {/* Main content area - maintains minimum width */}
        <div className="flex-1 flex flex-col min-h-0 min-w-[500px]">
          {/* Chapter navigation */}
          <div className="flex items-center justify-between mb-2 px-1">
            <button
              onClick={() => {
                if (canGoPrev) {
                  setSelectedChapter(orderedChapterIds[currentChapterIndex - 1])
                }
              }}
              disabled={!canGoPrev}
              className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 text-xs"
            >
              <ChevronLeft className="w-3 h-3" />
              {t('preview.prevChapter')}
            </button>
            <span className="text-gray-600 dark:text-gray-300 font-medium text-xs">
              {chapterContent?.title || t('preview.chapterNumber', { number: String(chapterContent?.chapter_number) })}
            </span>
            <button
              onClick={() => {
                if (canGoNext) {
                  setSelectedChapter(orderedChapterIds[currentChapterIndex + 1])
                }
              }}
              disabled={!canGoNext}
              className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 text-xs"
            >
              {t('preview.nextChapter')}
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          {/* Paragraphs with two/three panel view */}
          <div className="flex-1 overflow-y-auto">
            {isLoadingContent ? (
              <div className="text-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
              </div>
            ) : (
              <div className="space-y-2">
                {/* Display images if chapter has any */}
                {chapterContent?.images && chapterContent.images.length > 0 && (
                  <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-2">
                    <div className="flex flex-wrap gap-2 justify-center">
                      {chapterContent.images.map((img: ChapterImage, idx: number) => {
                        // Extract image filename from src path (e.g., "../images/00001.jpeg" -> "images/00001.jpeg")
                        const imagePath = img.src.replace(/^\.\.\//, '')
                        const imageUrl = `/api/v1/preview/${projectId}/image/${imagePath}`
                        return (
                          <div key={idx} className="text-center">
                            <img
                              src={imageUrl}
                              alt={img.alt || `Image ${idx + 1}`}
                              className="max-w-full max-h-64 object-contain rounded"
                              onError={(e) => {
                                // Hide broken images
                                (e.target as HTMLImageElement).style.display = 'none'
                              }}
                            />
                            {img.caption && (
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{img.caption}</p>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
                {paragraphs.map((para) => (
                  <div
                    key={para.id}
                    className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-2"
                  >
                    {/* Grid for panels - responsive 2 columns */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {/* Original English panel */}
                      <div className="min-w-0">
                        <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>{t('translate.original')}</div>
                        <div className={`text-gray-700 dark:text-gray-300 ${fontClasses.paragraph} leading-relaxed`}>{para.original_text}</div>
                      </div>

                      {/* Translation panel */}
                      <div className="min-w-0">
                        <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>{t('translate.translation')}</div>
                        {editingParagraph === para.id ? (
                          <div>
                            <textarea
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              className={`w-full h-16 px-1.5 py-1 border border-gray-300 dark:border-gray-600 rounded ${fontClasses.paragraph} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500`}
                            />
                            <div className="flex gap-1.5 mt-1.5">
                              <button
                                onClick={() => handleSave(para.id)}
                                disabled={updateMutation.isPending}
                                className={`flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700 ${fontClasses.xs}`}
                              >
                                <Save className="w-2.5 h-2.5" />
                                {t('common.save')}
                              </button>
                              <button
                                onClick={() => setEditingParagraph(null)}
                                className={`flex items-center gap-0.5 px-1.5 py-0.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                              >
                                <X className="w-2.5 h-2.5" />
                                {t('common.cancel')}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className={`${fontClasses.paragraph} leading-relaxed ${para.translated_text ? 'text-blue-700 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500 italic'}`}>
                            {para.translated_text || t('common.noTranslation')}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action buttons - all on the right */}
                    <div className="flex items-center justify-end gap-1.5 mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-700">
                      {/* Reasoning/Chat button - only if translated */}
                      {para.translated_text && para.translation_id && (
                        <button
                          onClick={() => handleRequestReasoning(para.id, para.translation_id ?? undefined, para.original_text, para.translated_text || '')}
                          className="flex items-center gap-0.5 px-1.5 py-0.5 text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/30 rounded text-[10px]"
                        >
                          <Lightbulb className="w-2.5 h-2.5" />
                          {t('translate.showReasoning')}
                        </button>
                      )}

                      {/* Retranslate button */}
                      <button
                        onClick={() => retranslateMutation.mutate(para.id)}
                        disabled={retranslateMutation.isPending}
                        className="flex items-center gap-0.5 px-1.5 py-0.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded text-[10px] disabled:opacity-50"
                      >
                        {retranslateMutation.isPending && retranslateMutation.variables === para.id ? (
                          <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        ) : (
                          <RefreshCw className="w-2.5 h-2.5" />
                        )}
                        {retranslateMutation.isPending && retranslateMutation.variables === para.id
                          ? t('translate.retranslating')
                          : t('translate.retranslate')}
                      </button>

                      {/* Edit button */}
                      <button
                        onClick={() => handleEdit(para.id, para.translated_text || '')}
                        className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-[10px]"
                      >
                        <Edit2 className="w-2.5 h-2.5" />
                        {t('common.edit')}
                      </button>

                      {/* Confirm toggle button */}
                      <button
                        onClick={() => handleToggleConfirm(para.id)}
                        className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                          confirmedParagraphs.has(para.id)
                            ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                        }`}
                      >
                        <Check className="w-2.5 h-2.5" />
                        {confirmedParagraphs.has(para.id) ? t('translate.confirmed') : t('translate.pending')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Resize handle for reference panel */}
        {showReferencePanel && hasReference && (
          <ResizeHandle onResize={handleReferencePanelResize} className="h-full" />
        )}

        {/* Reference Panel - Fixed position, doesn't scroll with main content */}
        {showReferencePanel && hasReference && (
          <div
            className="flex-shrink-0 self-start sticky top-2"
            style={{ width: panelWidths.referencePanel }}
          >
            <div className="bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800 p-2 max-h-[calc(100vh-100px)] flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium text-amber-800 dark:text-amber-200 text-xs flex items-center gap-1">
                  <BookOpen className="w-3 h-3" />
                  {t('translate.referenceChapter')}
                </h3>
                <button
                  onClick={() => setShowReferencePanel(false)}
                  className="p-0.5 text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Search input */}
              <form onSubmit={handleRefSearch} className="flex gap-1 mb-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={refSearchInputValue}
                    onChange={(e) => setRefSearchInputValue(e.target.value)}
                    placeholder={t('translate.searchReference')}
                    className="w-full pl-6 pr-2 py-1 text-xs border border-amber-300 dark:border-amber-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400"
                  />
                  <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-amber-500" />
                </div>
                {refSearchQuery && (
                  <button
                    type="button"
                    onClick={handleClearRefSearch}
                    className="p-1 text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200"
                    title={t('common.cancel')}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </form>

              {/* Reference chapter selector - only when not searching */}
              {!refSearchQuery && (
                <select
                  value={selectedRefChapter ?? ''}
                  onChange={(e) => setSelectedRefChapter(Number(e.target.value))}
                  className="w-full px-1.5 py-1 mb-2 text-xs border border-amber-300 dark:border-amber-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                  {referenceChapters?.map((ch) => (
                    <option key={ch.chapter_number} value={ch.chapter_number}>
                      {ch.title || `Ch ${ch.chapter_number}`} ({ch.paragraph_count})
                    </option>
                  ))}
                </select>
              )}

              {/* Reference content */}
              <div className="flex-1 overflow-y-auto">
                {/* Search results */}
                {refSearchQuery ? (
                  isSearchingRef ? (
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
                          onClick={() => handleSearchResultClick(result.chapter_number, result.paragraph_number)}
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
                  isLoadingRefContent ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                    </div>
                  ) : referenceChapterContent ? (
                    <div className="space-y-1.5">
                      {referenceChapterContent.title && (
                        <h4 className={`font-medium text-amber-900 dark:text-amber-100 ${fontClasses.sm} border-b border-amber-200 dark:border-amber-700 pb-1`}>
                          {referenceChapterContent.title}
                        </h4>
                      )}
                      {referenceChapterContent.paragraphs.map((para) => (
                        <div
                          key={para.paragraph_number}
                          id={`ref-para-${para.paragraph_number}`}
                          ref={highlightedRefParagraph === para.paragraph_number ? (el) => el?.scrollIntoView({ behavior: 'smooth', block: 'center' }) : undefined}
                          className={`${fontClasses.paragraph} text-amber-900 dark:text-amber-100 leading-relaxed p-1 rounded transition-colors duration-300 ${
                            highlightedRefParagraph === para.paragraph_number
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
        )}
      </div>

      {/* Translation Reasoning Chat Modal */}
      {showReasoningChat && (
        <ReasoningChatModal
          isOpen={!!showReasoningChat}
          onClose={() => setShowReasoningChat(null)}
          translationId={showReasoningChat.translationId}
          paragraphId={showReasoningChat.paragraphId}
          originalText={showReasoningChat.originalText}
          translatedText={showReasoningChat.translatedText}
          onTranslationUpdated={() => {
            queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
          }}
        />
      )}

      {/* Translation Prompt Preview Modal */}
      {projectId && (
        <PreviewModal
          isOpen={showPreviewModal}
          onClose={() => setShowPreviewModal(false)}
          projectId={projectId}
        />
      )}

      <PromptPreviewModal
        isOpen={showTranslationPromptPreview}
        onClose={() => setShowTranslationPromptPreview(false)}
        promptType="translation"
        variables={promptPreviewVariables}
        onConfirm={handleTranslationPromptConfirm}
        isLoading={startTranslationMutation.isPending}
      />

      {/* Reasoning Prompt Preview Modal (legacy - not currently triggered) */}
      <PromptPreviewModal
        isOpen={showReasoningPromptPreview}
        onClose={() => setShowReasoningPromptPreview(false)}
        promptType="reasoning"
        variables={{
          original_text: '(Original text will be provided)',
          translated_text: '(Translated text will be provided)',
        }}
        onConfirm={handleReasoningPromptConfirm}
        isLoading={false}
      />
    </div>
  )
}
