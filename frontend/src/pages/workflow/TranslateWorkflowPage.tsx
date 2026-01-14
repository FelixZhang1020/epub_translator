import { useState, useCallback, useEffect, useMemo } from 'react'
import { useParams, useOutletContext, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  ChevronLeft,
  ChevronRight,
  Edit2,
  Save,
  X,
  Loader2,
  Lightbulb,
  Trash2,
  Play,
  FileText,
  BookOpen,
  PanelRightClose,
  RefreshCw,
  ArrowLeft,
  ArrowRight,
  Lock,
  Unlock,
} from 'lucide-react'
import { api, ChapterImage } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptTemplateSelector } from '../../components/common/PromptTemplateSelector'
import { WorkflowChapterList } from '../../components/workflow/WorkflowChapterList'
import { ReferencePanel } from '../../components/workflow/ReferencePanel'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import { PreviewModal } from '../../components/preview/PreviewModal'
import { ReasoningChatModal } from '../../components/translation/ReasoningChatModal'
import {
  useOrderedChapterIds,
  useChapterNavigation,
  usePanelResize,
} from '../../utils/workflow'
import type { Project } from '../../services/api/client'

interface WorkflowContext {
  project: Project | null
  workflowStatus: {
    has_reference_epub: boolean
    translation_completed: boolean
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
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const context = useOutletContext<WorkflowContext>()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const [searchParams, setSearchParams] = useSearchParams()

  // Panel resize functionality from shared hook
  const { panelWidths, handleChapterListResize, handleReferencePanelResize } = usePanelResize()

  // State - initialize from URL params if available
  const [selectedChapter, setSelectedChapter] = useState<string | null>(
    searchParams.get('chapter') || null
  )
  const [editingParagraph, setEditingParagraph] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [showReasoningChat, setShowReasoningChat] = useState<{
    translationId: string
    paragraphId: string
    originalText: string
    translatedText: string
  } | null>(null)

  // Preview modal state
  const [showPreviewModal, setShowPreviewModal] = useState(false)

  // Custom prompts from template selector (used when user edits in modal)
  const [customSystemPrompt, setCustomSystemPrompt] = useState<string | undefined>()
  const [customUserPrompt, setCustomUserPrompt] = useState<string | undefined>()

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
  const translationCompleted = context?.workflowStatus?.translation_completed ?? false
  const translationDone = translationCompleted ||
    translationStatus === 'completed' ||
    (translationProgress?.progress ?? 0) >= 1
  const hasTranslationContent = (translationProgress?.completed_paragraphs ?? 0) > 0
  const canConfirmTranslation = translationDone && hasTranslationContent && !isTranslating && !translationCompleted

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
  const orderedChapterIds = useOrderedChapterIds(toc, chapters)

  // Create a map of chapter IDs to titles from TOC for looking up titles
  const chapterTitleMap = useMemo(() => {
    const map = new Map<string, string>()

    const extractTitles = (items: typeof toc) => {
      if (!items) return
      for (const item of items) {
        if (item.chapter_id && item.title) {
          map.set(item.chapter_id, item.title)
        }
        if (item.children && item.children.length > 0) {
          extractTitles(item.children)
        }
      }
    }

    extractTitles(toc)
    return map
  }, [toc])

  // Build chapter stats map for translation progress display
  const chapterStatsMap = useMemo(() => {
    const map = new Map<string, { translated: number; total: number }>()
    chapters?.forEach(chapter => {
      map.set(chapter.id, {
        translated: chapter.translated_count,
        total: chapter.paragraph_count,
      })
    })
    return map
  }, [chapters])


  // Wrapper function to update both state and URL params
  const setSelectedChapterWithUrl = useCallback((chapterId: string) => {
    setSelectedChapter(chapterId)
    setSearchParams({ chapter: chapterId })
  }, [setSearchParams])

  // Chapter navigation
  const { canGoPrev, canGoNext, goToPrevChapter, goToNextChapter } =
    useChapterNavigation(orderedChapterIds, selectedChapter, setSelectedChapterWithUrl)

  // Extract prompt preview variables from analysis data
  const promptPreviewVariables = useMemo(() => {
    const rawAnalysis = analysisData?.raw_analysis as Record<string, unknown> | null

    // Helper to get nested value (supports both flat and nested structures)
    const getNestedValue = (obj: Record<string, unknown> | null, ...paths: string[]): string => {
      if (!obj) return ''
      for (const path of paths) {
        const keys = path.split('.')
        let value: unknown = obj
        for (const key of keys) {
          if (value && typeof value === 'object' && key in (value as Record<string, unknown>)) {
            value = (value as Record<string, unknown>)[key]
          } else {
            value = undefined
            break
          }
        }
        if (value && typeof value === 'string') return value
      }
      return ''
    }

    // Extract values supporting both flat (default schema) and nested (reformed-theology schema)
    const writingStyle = getNestedValue(rawAnalysis, 'writing_style', 'work_profile.writing_style')
    const tone = getNestedValue(rawAnalysis, 'tone', 'work_profile.tone')
    const targetAudience = getNestedValue(rawAnalysis, 'target_audience', 'work_profile.target_audience')
    const genreConventions = getNestedValue(rawAnalysis, 'genre_conventions', 'work_profile.genre')

    // Format key_terminology for display
    // Support both field names: recommended_chinese (from analysis) and chinese_translation (legacy)
    const terminology = rawAnalysis?.key_terminology as Array<{
      english_term: string
      recommended_chinese?: string
      chinese_translation?: string
      fallback_options?: string[]
      usage_rule?: string
    }> | undefined
    const terminologyText = terminology
      ? terminology.map(t => {
        const chinese = t.recommended_chinese || t.chinese_translation || ''
        const fallbacks = t.fallback_options?.slice(0, 2).join(', ')
        let line = `- **${t.english_term}**: ${chinese}`
        if (fallbacks) line += ` (alt: ${fallbacks})`
        if (t.usage_rule) line += `\n  - Usage: ${t.usage_rule.slice(0, 100)}${t.usage_rule.length > 100 ? '...' : ''}`
        return line
      }).join('\n')
      : ''

    // Format translation_principles for display
    const principles = rawAnalysis?.translation_principles as Record<string, unknown> | undefined
    const priorityOrder = (principles?.priority_order as string[] | string | undefined)
      ? (Array.isArray(principles?.priority_order)
        ? (principles.priority_order as string[]).join(', ')
        : String(principles?.priority_order))
      : ''
    const faithfulnessBoundary = getNestedValue(rawAnalysis,
      'translation_principles.faithfulness_boundary',
      'translation_principles.must_be_literal')
    const permissibleAdaptation = getNestedValue(rawAnalysis,
      'translation_principles.permissible_adaptation',
      'translation_principles.allowed_adjustment')
    const styleConstraints = getNestedValue(rawAnalysis, 'translation_principles.style_constraints')
    const redLines = getNestedValue(rawAnalysis,
      'translation_principles.red_lines',
      'translation_principles.absolute_red_lines')

    // Format custom_guidelines for display (support both custom_guidelines and custom_watchlist)
    const guidelines = (rawAnalysis?.custom_guidelines || rawAnalysis?.custom_watchlist) as string[] | undefined
    const guidelinesText = guidelines
      ? guidelines.map(g => `- ${g}`).join('\n')
      : ''

    return {
      // Project info (namespaced keys)
      'project.title': context?.project?.epub_title || context?.project?.name || '',
      'project.author': context?.project?.epub_author || '',
      'project.author_background': context?.project?.author_background || '',
      // Content
      'content.source': t('prompts.placeholderSource'),
      // Derived from analysis
      'derived.writing_style': writingStyle,
      'derived.tone': tone,
      'derived.target_audience': targetAudience,
      'derived.genre_conventions': genreConventions,
      'derived.terminology_table': terminologyText,
      'derived.priority_order': priorityOrder,
      'derived.faithfulness_boundary': faithfulnessBoundary,
      'derived.permissible_adaptation': permissibleAdaptation,
      'derived.style_constraints': styleConstraints,
      'derived.red_lines': redLines,
      'derived.custom_guidelines': guidelinesText,
      // Boolean flags
      'derived.has_analysis': !!rawAnalysis,
      'derived.has_writing_style': !!writingStyle,
      'derived.has_tone': !!tone,
      'derived.has_terminology': !!terminologyText,
      'derived.has_target_audience': !!targetAudience,
      'derived.has_genre_conventions': !!genreConventions,
      'derived.has_translation_principles': !!principles,
      'derived.has_custom_guidelines': !!(guidelines && guidelines.length > 0),
      'derived.has_style_constraints': !!styleConstraints,
    }
  }, [analysisData, context?.project])

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
      setSelectedChapterWithUrl(orderedChapterIds[0])
    }
  }, [orderedChapterIds, selectedChapter, setSelectedChapterWithUrl])

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
        throw new Error(t('translate.noChapterSelected'))
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

  // Confirm translation mutation
  const confirmTranslationMutation = useMutation({
    mutationFn: () => api.confirmTranslation(projectId!),
    onSuccess: () => {
      // Navigate immediately to proofreading stage
      navigate(`/project/${projectId}/proofread`)
      // Invalidate queries after navigation
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      context?.refetchWorkflow()
    },
  })

  // Cancel stuck tasks mutation
  const cancelStuckTasksMutation = useMutation({
    mutationFn: () => api.cancelStuckTasks(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
      context?.refetchWorkflow()
    },
  })

  // Lock/unlock translation mutation
  const lockTranslationMutation = useMutation({
    mutationFn: ({ paragraphId, isConfirmed }: { paragraphId: string; isConfirmed: boolean }) =>
      api.lockTranslation(paragraphId, isConfirmed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
    },
  })

  // Handler for translation prompt confirmation from the selector modal
  const handleTranslationPromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    // Store custom prompts for use in translation
    setCustomSystemPrompt(systemPrompt)
    setCustomUserPrompt(userPrompt)
    // Start translation with custom prompts
    startTranslationMutation.mutate({
      customSystemPrompt: systemPrompt,
      customUserPrompt: userPrompt,
    })
  }

  // Start translation directly with current prompts (from selector or default)
  const handleStartTranslationClick = () => {
    startTranslationMutation.mutate({
      customSystemPrompt,
      customUserPrompt,
    })
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

  // Handle translation discussion - opens chat modal
  const handleRequestReasoning = (paragraphId: string, translationId: string | undefined, originalText: string, translatedText: string) => {
    if (!translationId) return
    setShowReasoningChat({
      translationId,
      paragraphId,
      originalText,
      translatedText,
    })
  }

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Action Bar - unified format */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-gray-700 mb-2">
        <div className="flex flex-wrap items-center gap-3">
          {/* Left Group: Back + LLM + Prompt */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/project/${projectId}/analysis`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">{t('common.back')}</span>
            </button>
            <LLMConfigSelector />
            <PromptTemplateSelector
              promptType="translation"
              projectId={projectId}
              variables={promptPreviewVariables}
              disabled={!hasLLMConfig}
              onConfirm={handleTranslationPromptConfirm}
              isLoading={startTranslationMutation.isPending}
              compact
            />
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right Group: Cancel + Translate + Next */}
          <div className="flex items-center gap-2">
            {/* Cancel stuck tasks button */}
            {isTranslating && (
              <button
                onClick={() => cancelStuckTasksMutation.mutate()}
                disabled={cancelStuckTasksMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-orange-600 dark:text-orange-400 border border-orange-300 dark:border-orange-700 rounded-lg hover:bg-orange-50 dark:hover:bg-orange-900/30 text-sm font-medium transition-colors"
                title={t('translate.cancelStuckTasks')}
              >
                {cancelStuckTasksMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">{t('common.cancel')}</span>
              </button>
            )}

            {/* Translate button */}
            <button
              onClick={handleStartTranslationClick}
              disabled={!hasLLMConfig || !chapterContent || startTranslationMutation.isPending || isTranslating}
              title={chapterContent ? t('translate.translateChapterHint', { chapter: chapterContent.title || String(chapterContent.chapter_number) }) : ''}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {(startTranslationMutation.isPending || isTranslating) ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">
                {(startTranslationMutation.isPending || isTranslating) ? t('translate.translating') : t('translate.translateCurrentChapter')}
              </span>
            </button>

            {/* Next button */}
            <button
              onClick={() => {
                if (translationCompleted) {
                  navigate(`/project/${projectId}/proofread`)
                } else {
                  confirmTranslationMutation.mutate()
                }
              }}
              disabled={!translationCompleted && (!canConfirmTranslation || confirmTranslationMutation.isPending)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {confirmTranslationMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{t('common.next')}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-x-auto">
        {/* Chapter list sidebar - resizable width */}
        <WorkflowChapterList
          width={panelWidths.chapterList}
          toc={toc}
          chapters={chapters}
          selectedChapterId={selectedChapter}
          onSelectChapter={setSelectedChapterWithUrl}
          onResize={handleChapterListResize}
          fontClasses={fontClasses}
          chapterStatsMap={chapterStatsMap}
        />

        {/* Main content area - maintains minimum width */}
        <div className="flex-1 flex flex-col min-h-0 min-w-[500px]">
          {/* Reference EPUB Row - above stats */}
          <div className="flex items-center justify-between gap-2 mb-2 bg-white dark:bg-gray-800 p-2 px-3 rounded-lg border border-gray-200 dark:border-gray-700">
            {hasReference && referenceEpub ? (
              <div className={`flex items-center gap-2 ${fontClasses.base}`}>
                <FileText className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                <span className="text-gray-600 dark:text-gray-400">{t('translate.referenceLoaded')}</span>
                <span className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>
                  ({referenceEpub.total_chapters} {t('translate.chapters')}, {referenceEpub.total_paragraphs} {t('translate.paragraphs')})
                </span>
                <button
                  onClick={() => deleteReferenceMutation.mutate()}
                  className="p-1 text-red-500 hover:text-red-700 flex-shrink-0"
                  title={t('translate.removeReference')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className={`flex items-center gap-2 ${fontClasses.base}`}>
                <FileText className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                <span className="text-gray-500 dark:text-gray-400">{t('translate.reference')}: </span>
                <label className={`flex items-center gap-2 px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/50 ${fontClasses.sm}`}>
                  <Upload className="w-3.5 h-3.5" />
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
            {/* Toggle reference panel button - only show when reference is loaded */}
            {hasReference && referenceEpub && (
              <button
                onClick={() => setShowReferencePanel(!showReferencePanel)}
                className={`flex items-center gap-2 px-2 lg:px-3 py-1 border rounded-lg flex-shrink-0 transition-colors ${showReferencePanel
                  ? 'border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                  : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                  } ${fontClasses.sm}`}
                title={showReferencePanel ? t('translate.hideReferencePanel') : t('translate.showReferencePanel')}
              >
                {showReferencePanel ? <PanelRightClose className="w-4 h-4" /> : <BookOpen className="w-4 h-4" />}
                <span className="hidden sm:inline">{t('translate.reference')}</span>
              </button>
            )}
          </div>

          {/* Chapter navigation */}
          <div className="flex items-center justify-between mb-2 px-1">
            <button
              onClick={goToPrevChapter}
              disabled={!canGoPrev}
              className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 text-xs"
            >
              <ChevronLeft className="w-3 h-3" />
              {t('preview.prevChapter')}
            </button>
            <span className="text-gray-600 dark:text-gray-300 font-medium text-xs">
              {chapterContent?.title ||
                (chapterContent?.id ? chapterTitleMap.get(chapterContent.id) : null) ||
                (chapterContent?.chapter_number ? t('preview.chapterNumber', { number: String(chapterContent.chapter_number) }) : t('translate.noChapterSelected'))}
            </span>
            <button
              onClick={goToNextChapter}
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

                      {/* Retranslate button - disabled when locked */}
                      <button
                        onClick={() => retranslateMutation.mutate(para.id)}
                        disabled={retranslateMutation.isPending || para.is_confirmed}
                        className="flex items-center gap-0.5 px-1.5 py-0.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded text-[10px] disabled:opacity-50 disabled:cursor-not-allowed"
                        title={para.is_confirmed ? t('translate.unlockToEdit') : ''}
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

                      {/* Edit button - disabled when locked */}
                      <button
                        onClick={() => handleEdit(para.id, para.translated_text || '')}
                        disabled={para.is_confirmed}
                        className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-[10px] disabled:opacity-50 disabled:cursor-not-allowed"
                        title={para.is_confirmed ? t('translate.unlockToEdit') : ''}
                      >
                        <Edit2 className="w-2.5 h-2.5" />
                        {t('common.edit')}
                      </button>

                      {/* Lock/Unlock button */}
                      <button
                        onClick={() => lockTranslationMutation.mutate({
                          paragraphId: para.id,
                          isConfirmed: !para.is_confirmed
                        })}
                        disabled={lockTranslationMutation.isPending || !para.translated_text}
                        className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition-colors ${para.is_confirmed
                          ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 hover:bg-orange-100 dark:hover:bg-orange-900/50 hover:text-orange-700 dark:hover:text-orange-400'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-green-100 dark:hover:bg-green-900/50 hover:text-green-700 dark:hover:text-green-400'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        title={para.is_confirmed ? t('proofreading.unlock') : t('proofreading.confirm')}
                      >
                        {lockTranslationMutation.isPending ? (
                          <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        ) : para.is_confirmed ? (
                          <Lock className="w-2.5 h-2.5" />
                        ) : (
                          <Unlock className="w-2.5 h-2.5" />
                        )}
                        {para.is_confirmed ? t('translate.locked') : t('translate.unlocked')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Reference Panel */}
        <ReferencePanel
          width={panelWidths.referencePanel}
          show={showReferencePanel}
          hasReference={hasReference}
          onClose={() => setShowReferencePanel(false)}
          onResize={handleReferencePanelResize}

          searchQuery={refSearchQuery}
          searchInputValue={refSearchInputValue}
          isSearching={isSearchingRef}
          onSearch={handleRefSearch}
          onSearchInputChange={setRefSearchInputValue}
          onClearSearch={handleClearRefSearch}
          searchResults={searchResults}
          onSearchResultClick={handleSearchResultClick}

          chapters={referenceChapters}
          selectedChapter={selectedRefChapter}
          onSelectChapter={setSelectedRefChapter}

          isLoadingContent={isLoadingRefContent}
          chapterContent={referenceChapterContent}
          highlightedParagraph={highlightedRefParagraph}

          fontClasses={fontClasses}
        />
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

    </div>
  )
}
