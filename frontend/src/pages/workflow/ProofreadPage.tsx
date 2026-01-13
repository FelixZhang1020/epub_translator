import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useOutletContext, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  X,
  Edit2,
  Loader2,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  FileCheck,
  Save,
  FileText,
  ChevronLeft,
  ChevronRight,
  Eye,
  MessageSquare,
  BookOpen,
  Lock,
  Unlock,
  Sparkles,
  Check,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptPreviewModal } from '../../components/common/PromptPreviewModal'
import { TreeChapterList } from '../../components/common/TreeChapterList'
import { WorkflowChapterList } from '../../components/workflow/WorkflowChapterList'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import { PreviewModal } from '../../components/preview/PreviewModal'
import {
  useOrderedChapterIds,
  useChapterNavigation,
  usePanelResize,
} from '../../utils/workflow'
import type { Project } from '../../services/api/client'

interface WorkflowContext {
  project: Project | null
  workflowStatus: {
    proofreading_progress?: {
      has_session: boolean
      session_id?: string
      status?: string
      round_number: number
      progress: number
      pending_suggestions: number
    }
  } | null
  refetchWorkflow: () => void
}

type ViewMode = 'llm-suggestions' | 'all-translations'

export function ProofreadPage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const context = useOutletContext<WorkflowContext>()
  const [searchParams, setSearchParams] = useSearchParams()

  // App store for font size
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  // Panel resize functionality from shared hook
  const { panelWidths, handleChapterListResize } = usePanelResize()

  // Settings store for LLM config
  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // View mode state
  const [viewMode, setViewMode] = useState<ViewMode>('llm-suggestions')

  // Session and suggestion state
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('pending')

  // Chapter state (for all-translations mode) - initialize from URL params
  const [selectedChapter, setSelectedChapter] = useState<string | null>(
    searchParams.get('chapter') || null
  )
  const [editingParagraph, setEditingParagraph] = useState<string | null>(null)
  const [editParagraphText, setEditParagraphText] = useState('')

  // Keyboard navigation state
  const [focusedSuggestionIndex, setFocusedSuggestionIndex] = useState<number>(0)

  // Prompt preview state
  const [showPromptPreview, setShowPromptPreview] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)

  // Chapter selection state
  const [showChapterSelection, setShowChapterSelection] = useState(false)
  const [selectedChaptersForProofreading, setSelectedChaptersForProofreading] = useState<Set<string>>(new Set())
  const [includeNonMain, setIncludeNonMain] = useState(false) // Include non-main content

  // Current translation editing state
  const [editingCurrentTranslation, setEditingCurrentTranslation] = useState<string | null>(null)
  const [editCurrentText, setEditCurrentText] = useState('')

  // LLM recommendation state
  const [recommendations, setRecommendations] = useState<Map<string, string>>(new Map())
  const [loadingRecommendation, setLoadingRecommendation] = useState<string | null>(null)

  // Fetch hierarchical TOC
  const { data: toc } = useQuery({
    queryKey: ['toc', projectId],
    queryFn: () => api.getToc(projectId!),
    enabled: !!projectId,
  })

  // Fetch chapters
  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId!),
    enabled: !!projectId,
  })

  // Create ordered list of chapter IDs
  const orderedChapterIds = useOrderedChapterIds(toc, chapters)

  // Wrapper function to update both state and URL params
  const setSelectedChapterWithUrl = useCallback((chapterId: string) => {
    setSelectedChapter(chapterId)
    setSearchParams({ chapter: chapterId })
  }, [setSearchParams])

  // Chapter navigation
  const { canGoPrev, canGoNext, goToPrevChapter, goToNextChapter } =
    useChapterNavigation(orderedChapterIds, selectedChapter, setSelectedChapterWithUrl)

  // Auto-select first chapter when viewing all translations
  useEffect(() => {
    if (viewMode === 'all-translations' && orderedChapterIds.length > 0 && !selectedChapter) {
      setSelectedChapterWithUrl(orderedChapterIds[0])
    }
  }, [viewMode, orderedChapterIds, selectedChapter, setSelectedChapterWithUrl])

  // Fetch chapter content for all-translations view
  const { data: chapterContent, isLoading: isLoadingContent } = useQuery({
    queryKey: ['chapter', projectId, selectedChapter],
    queryFn: () => api.getChapterContent(projectId!, selectedChapter!),
    enabled: !!projectId && !!selectedChapter && viewMode === 'all-translations',
  })

  // Fetch sessions
  const { data: sessions, isLoading: isLoadingSessions } = useQuery({
    queryKey: ['proofreadingSessions', projectId],
    queryFn: () => api.listProofreadingSessions(projectId!),
    enabled: !!projectId,
  })

  // Fetch models for display
  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  // Auto-select latest session
  useEffect(() => {
    if (sessions?.length && !selectedSession) {
      setSelectedSession(sessions[0].id)
    }
  }, [sessions, selectedSession])

  // Fetch current session
  const { data: currentSession } = useQuery({
    queryKey: ['proofreadingSession', selectedSession],
    queryFn: () => api.getProofreadingSession(selectedSession!),
    enabled: !!selectedSession,
    refetchInterval: (query) => {
      const session = query.state.data
      return session?.status === 'processing' ? 2000 : false
    },
  })

  // Auto-refetch suggestions and sessions when session completes or fails
  useEffect(() => {
    if (currentSession && (currentSession.status === 'completed' || currentSession.status === 'failed')) {
      // Switch to 'all' filter to show all results including errors
      setStatusFilter('all')
      // Invalidate suggestions to trigger refetch and show results or errors
      queryClient.invalidateQueries({ queryKey: ['proofreadingSuggestions', selectedSession] })
      // Also invalidate sessions list so the dropdown shows updated status
      queryClient.invalidateQueries({ queryKey: ['proofreadingSessions', projectId] })
    }
  }, [currentSession?.status, selectedSession, projectId, queryClient])

  // Fetch suggestions for current session
  const { data: suggestions, isLoading: isLoadingSuggestions } = useQuery({
    queryKey: ['proofreadingSuggestions', selectedSession, statusFilter],
    queryFn: () => api.getProofreadingSuggestions(
      selectedSession!,
      statusFilter === 'all' ? undefined : statusFilter,
      100,
      0
    ),
    enabled: !!selectedSession && viewMode === 'llm-suggestions',
  })

  // Start proofreading mutation
  const startMutation = useMutation({
    mutationFn: async (params?: { customSystemPrompt?: string; customUserPrompt?: string; chapterIds?: string[]; includeNonMain?: boolean }) => {
      return api.startProofreading(projectId!, {
        config_id: configId || undefined,
        custom_system_prompt: params?.customSystemPrompt,
        custom_user_prompt: params?.customUserPrompt,
        chapter_ids: params?.chapterIds,
        include_non_main: params?.includeNonMain,
      })
    },
    onSuccess: (session) => {
      // Optimistically update the cache with the new session
      queryClient.setQueryData(['proofreadingSessions', projectId], (old: any[] = []) => {
        return [session, ...old]
      })
      queryClient.invalidateQueries({ queryKey: ['proofreadingSessions', projectId] })
      setSelectedSession(session.id)
      setViewMode('llm-suggestions')
      setShowChapterSelection(false)
    },
    onError: (error: Error) => {
      console.error('Failed to start proofreading:', error)
      alert(t('proofreading.startFailed') + ': ' + error.message)
    },
  })

  // Handler for prompt confirmation
  const handlePromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    setShowPromptPreview(false)
    const chapterIds = selectedChaptersForProofreading.size > 0
      ? Array.from(selectedChaptersForProofreading)
      : undefined
    startMutation.mutate({
      customSystemPrompt: systemPrompt,
      customUserPrompt: userPrompt,
      chapterIds,
      includeNonMain,
    })
  }

  // Open chapter selection modal
  const handleStartClick = () => {
    if (!hasLLMConfig) {
      alert(t('translate.configLlmWarning'))
      return
    }
    setShowChapterSelection(true)
  }

  // Toggle all chapters selection
  const handleSelectAllChapters = () => {
    if (selectedChaptersForProofreading.size === orderedChapterIds.length) {
      setSelectedChaptersForProofreading(new Set())
    } else {
      setSelectedChaptersForProofreading(new Set(orderedChapterIds))
    }
  }

  // Toggle individual chapter selection
  const toggleChapterSelection = (chapterId: string) => {
    setSelectedChaptersForProofreading(prev => {
      const next = new Set(prev)
      if (next.has(chapterId)) {
        next.delete(chapterId)
      } else {
        next.add(chapterId)
      }
      return next
    })
  }

  // Start proofreading with selected chapters
  const handleStartProofreading = () => {
    setShowChapterSelection(false)
    setShowPromptPreview(true)
  }

  // Build chapter stats map
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

  // Update translation mutation (for direct editing)
  const updateTranslationMutation = useMutation({
    mutationFn: ({ paragraphId, text }: { paragraphId: string; text: string }) =>
      api.updateParagraphTranslation(paragraphId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
      queryClient.invalidateQueries({ queryKey: ['proofreadingSuggestions', selectedSession] })
      setEditingParagraph(null)
      setEditingCurrentTranslation(null)
    },
    onError: (error: Error) => {
      console.error('Failed to update translation:', error)
      alert(t('common.error') + ': ' + error.message)
      // Reset editing state so user can try again or cancel
      setEditingParagraph(null)
      setEditingCurrentTranslation(null)
    },
  })

  // Confirm translation mutation (lock a translation)
  const confirmTranslationMutation = useMutation({
    mutationFn: ({ paragraphId, isConfirmed }: { paragraphId: string; isConfirmed: boolean }) =>
      api.lockTranslation(paragraphId, isConfirmed),
    onSuccess: () => {
      // Invalidate queries to refetch the updated confirmed status
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
      queryClient.invalidateQueries({ queryKey: ['proofreadingSuggestions', selectedSession] })
    },
    onError: (error: Error) => {
      console.error('Failed to lock/unlock translation:', error)
      alert(t('common.error') + ': ' + error.message)
    },
  })

  // Reset translation status mutation (back to translation stage)
  const resetTranslationMutation = useMutation({
    mutationFn: async () => {
      return api.resetTranslationStatus(projectId!)
    },
    onSuccess: async () => {
      // Remove all cached queries for this project
      queryClient.removeQueries({ queryKey: ['workflowStatus', projectId] })
      queryClient.removeQueries({ queryKey: ['project', projectId] })
      queryClient.removeQueries({ queryKey: ['proofreadingSessions', projectId] })
      queryClient.removeQueries({ queryKey: ['proofreadingSuggestions'] })

      // Refetch workflow status to ensure we have the latest data
      await queryClient.refetchQueries({ queryKey: ['workflowStatus', projectId] })

      // Navigate using React Router
      navigate(`/project/${projectId}/translate`, { replace: true })
    },
  })

  // Confirm proofreading completion mutation
  const confirmProofreadingMutation = useMutation({
    mutationFn: async () => {
      return api.confirmProofreading(projectId!)
    },
    onSuccess: () => {
      context?.refetchWorkflow()
      navigate(`/project/${projectId}/export`)
    },
  })

  // Cancel proofreading mutation
  const cancelProofreadingMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      return api.cancelProofreadingSession(sessionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proofreadingSession', selectedSession] })
      queryClient.invalidateQueries({ queryKey: ['proofreadingSessions', projectId] })
    },
  })

  // Direct edit handlers
  const handleDirectEdit = (paragraphId: string, currentText: string) => {
    setEditingParagraph(paragraphId)
    setEditParagraphText(currentText || '')
  }

  const handleDirectSave = (paragraphId: string) => {
    updateTranslationMutation.mutate({ paragraphId, text: editParagraphText })
  }

  // Get LLM recommendation for a paragraph
  const handleGetRecommendation = async (
    paragraphId: string,
    originalText: string,
    currentTranslation: string,
    feedback: string
  ) => {
    setLoadingRecommendation(paragraphId)
    try {
      const result = await api.getQuickRecommendation({
        original_text: originalText,
        current_translation: currentTranslation,
        feedback: feedback,
        config_id: configId || undefined,
      })
      setRecommendations(prev => new Map(prev).set(paragraphId, result.recommended_translation))
    } catch (error) {
      console.error('Failed to get recommendation:', error)
      alert(t('common.error') + ': ' + (error as Error).message)
    } finally {
      setLoadingRecommendation(null)
    }
  }

  // Apply recommendation to current translation
  const handleApplyRecommendation = (paragraphId: string) => {
    const recommendation = recommendations.get(paragraphId)
    if (recommendation) {
      updateTranslationMutation.mutate({ paragraphId, text: recommendation })
      // Clear the recommendation after applying
      setRecommendations(prev => {
        const next = new Map(prev)
        next.delete(paragraphId)
        return next
      })
    }
  }

  // Keyboard shortcuts for navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (viewMode !== 'llm-suggestions' || !suggestions?.length) return
      if (editingCurrentTranslation) return // Disable when editing

      const filteredSuggestions = suggestions.filter(s =>
        statusFilter === 'all' ||
        (statusFilter === 'pending' && !s.is_confirmed) ||
        (statusFilter === 'accepted' && s.is_confirmed)
      )

      if (filteredSuggestions.length === 0) return

      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault()
        setFocusedSuggestionIndex(prev =>
          Math.min(prev + 1, filteredSuggestions.length - 1)
        )
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault()
        setFocusedSuggestionIndex(prev => Math.max(prev - 1, 0))
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [viewMode, suggestions, statusFilter, focusedSuggestionIndex, editingCurrentTranslation])

  // Stats for current session - based on lock status (is_confirmed)
  const pendingCount = suggestions?.filter(s => !s.is_confirmed).length || 0
  const acceptedCount = suggestions?.filter(s => s.is_confirmed).length || 0

  // Get model display name
  const getModelName = (modelId: string) => {
    const model = models?.find(m => m.id === modelId)
    return model?.display_name || modelId
  }

  const paragraphs = chapterContent?.paragraphs || []

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Action Bar - unified format */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 bg-white dark:bg-gray-800 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h2 className={`font-semibold text-gray-900 dark:text-gray-100 ${fontClasses.heading}`}>{t('workflow.proofreading')}</h2>
          {currentSession && (
            <span className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
              {t('proofreading.round')} {currentSession.round_number}
            </span>
          )}

          {/* View mode toggle */}
          <div className="flex rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5">
            <button
              onClick={() => setViewMode('llm-suggestions')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md ${fontClasses.sm} font-medium transition-colors ${viewMode === 'llm-suggestions'
                ? 'bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-400 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t('proofreading.llmSuggestions')}</span>
              {pendingCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded-full">
                  {pendingCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setViewMode('all-translations')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md ${fontClasses.sm} font-medium transition-colors ${viewMode === 'all-translations'
                ? 'bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-400 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t('proofreading.allTranslations')}</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {/* Session selector */}
          {sessions && sessions.length > 1 && (
            <select
              value={selectedSession || ''}
              onChange={(e) => setSelectedSession(e.target.value)}
              className={`px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-lg ${fontClasses.sm} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100`}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {t('proofreading.round')} {s.round_number} - {s.status}
                </option>
              ))}
            </select>
          )}

          {/* LLM Config selector */}
          <LLMConfigSelector />

          <button
            onClick={() => setShowPromptPreview(true)}
            disabled={!hasLLMConfig}
            className={`flex items-center gap-1.5 px-2 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 ${fontClasses.button}`}
          >
            <FileText className="w-4 h-4" />
            <span className="hidden lg:inline">{t('prompts.viewPrompt')}</span>
          </button>

          {/* Start new round */}
          <button
            onClick={handleStartClick}
            disabled={startMutation.isPending || currentSession?.status === 'processing'}
            className={`flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed ${fontClasses.button}`}
          >
            {startMutation.isPending || currentSession?.status === 'processing' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : sessions?.length ? (
              <RefreshCw className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">
              {sessions?.length ? t('proofreading.newRound') : t('proofreading.start')}
            </span>
          </button>
          <button
            onClick={() => setShowPreviewModal(true)}
            className={`flex items-center gap-1.5 px-2 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.button}`}
          >
            <BookOpen className="w-4 h-4" />
            <span className="hidden lg:inline">{t('common.preview')}</span>
          </button>

          {/* Back to Translation button */}
          <button
            onClick={() => resetTranslationMutation.mutate()}
            disabled={resetTranslationMutation.isPending}
            className={`flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed ${fontClasses.button}`}
          >
            {resetTranslationMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowLeft className="w-4 h-4" />
            )}
            <span className="hidden lg:inline">{t('proofreading.backToTranslation')}</span>
          </button>

          {/* Continue to Export button */}
          <button
            onClick={() => confirmProofreadingMutation.mutate()}
            disabled={confirmProofreadingMutation.isPending}
            className={`flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed ${fontClasses.button}`}
          >
            {confirmProofreadingMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('workflow.continueToExport')}
              </>
            ) : (
              <>
                {t('workflow.continueToExport')}
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main content area with optional chapter panel */}
      <div className="flex flex-1 min-h-0">
        {/* Chapter list sidebar - only for all-translations view */}
        {viewMode === 'all-translations' && (
          <WorkflowChapterList
            width={panelWidths.chapterList}
            toc={toc}
            chapters={chapters}
            selectedChapterId={selectedChapter}
            onSelectChapter={setSelectedChapterWithUrl}
            onResize={handleChapterListResize}
            fontClasses={fontClasses}
          />
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
          {/* No session yet */}
          {!sessions?.length && !isLoadingSessions && viewMode === 'llm-suggestions' && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <FileCheck className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                <h3 className={`font-medium text-gray-700 dark:text-gray-300 mb-2 ${fontClasses.heading}`}>
                  {t('proofreading.noSession')}
                </h3>
                <p className={`text-gray-500 dark:text-gray-400 mb-4 ${fontClasses.paragraph}`}>
                  {t('proofreading.noSessionHint')}
                </p>
                <button
                  onClick={handleStartClick}
                  disabled={!hasLLMConfig || startMutation.isPending}
                  className={`flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 mx-auto ${fontClasses.button}`}
                >
                  {startMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {t('proofreading.start')}
                </button>
              </div>
            </div>
          )}

          {/* Session failed */}
          {currentSession?.status === 'failed' && viewMode === 'llm-suggestions' && (
            <div className="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg mb-4 border border-red-200 dark:border-red-800">
              <div className="flex items-center gap-3 mb-2">
                <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                <span className={`font-medium text-red-700 dark:text-red-300 ${fontClasses.base}`}>
                  {t('proofreading.startFailed')}
                </span>
              </div>
              <p className={`text-red-600 dark:text-red-400 ${fontClasses.sm} mb-3`}>
                {currentSession.error_message || t('common.error')}
              </p>
              <button
                onClick={handleStartClick}
                className={`px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 ${fontClasses.sm}`}
              >
                {t('common.retry')}
              </button>
            </div>
          )}

          {/* Session in progress */}
          {currentSession?.status === 'processing' && viewMode === 'llm-suggestions' && (
            <div className="bg-blue-50 dark:bg-blue-900/30 p-4 rounded-lg mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400" />
                  <span className={`font-medium text-blue-700 dark:text-blue-300 ${fontClasses.base}`}>
                    {t('proofreading.inProgress')}
                  </span>
                </div>
                <button
                  onClick={() => cancelProofreadingMutation.mutate(currentSession.id)}
                  disabled={cancelProofreadingMutation.isPending}
                  className={`flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 ${fontClasses.sm}`}
                >
                  {cancelProofreadingMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <X className="w-4 h-4" />
                  )}
                  {t('proofreading.cancel')}
                </button>
              </div>
              <div className={`flex items-center gap-4 ${fontClasses.sm} text-blue-600 dark:text-blue-400`}>
                <span>{t('proofreading.model')}: {getModelName(currentSession.model)}</span>
                <span>
                  {currentSession.completed_paragraphs} / {currentSession.total_paragraphs} {t('proofreading.paragraphs')}
                </span>
              </div>
              <div className="mt-2 bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                <div
                  className="bg-blue-600 dark:bg-blue-400 h-2 rounded-full transition-all"
                  style={{ width: `${currentSession.progress * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* LLM Suggestions View */}
          {viewMode === 'llm-suggestions' && currentSession?.status === 'completed' && (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Stats bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-white dark:bg-gray-800 p-2 rounded-lg border border-gray-200 dark:border-gray-700 mb-2">
                <div className="flex items-center gap-2 lg:gap-4">
                  <button
                    onClick={() => { setStatusFilter('pending'); setFocusedSuggestionIndex(0) }}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded ${fontClasses.sm} ${statusFilter === 'pending' ? 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`}
                  >
                    <Unlock className="w-4 h-4" />
                    {t('proofreading.pending')} ({pendingCount})
                  </button>
                  <button
                    onClick={() => { setStatusFilter('accepted'); setFocusedSuggestionIndex(0) }}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded ${fontClasses.sm} ${statusFilter === 'accepted' ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`}
                  >
                    <Lock className="w-4 h-4" />
                    {t('proofreading.accepted')} ({acceptedCount})
                  </button>
                  <button
                    onClick={() => { setStatusFilter('all'); setFocusedSuggestionIndex(0) }}
                    className={`px-2 py-1 rounded ${fontClasses.sm} ${statusFilter === 'all' ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`}
                  >
                    {t('proofreading.all')}
                  </button>
                </div>

                <div className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
                  {t('proofreading.lockToAccept')}
                </div>
              </div>

              {/* Suggestions list */}
              <div className="flex-1 overflow-y-auto space-y-3">
                {isLoadingSuggestions ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
                    <p className={`mt-2 text-gray-500 dark:text-gray-400 ${fontClasses.sm}`}>
                      {t('proofreading.loadingSuggestions')}
                    </p>
                  </div>
                ) : !suggestions || suggestions.length === 0 ? (
                  <div className="text-center py-12">
                    {statusFilter === 'all' && currentSession ? (
                      <div className="max-w-md mx-auto">
                        <AlertCircle className="w-12 h-12 text-amber-400 dark:text-amber-500 mx-auto mb-4" />
                        <h3 className={`font-medium text-gray-700 dark:text-gray-300 mb-2 ${fontClasses.heading}`}>
                          {t('proofreading.noSuggestionsGenerated')}
                        </h3>
                        <p className={`text-gray-500 dark:text-gray-400 mb-4 ${fontClasses.paragraph}`}>
                          {t('proofreading.noSuggestionsHint')}
                        </p>
                        {currentSession.error_message && (
                          <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3 text-left">
                            <p className={`text-red-700 dark:text-red-300 ${fontClasses.sm}`}>
                              {currentSession.error_message}
                            </p>
                          </div>
                        )}
                        {/* Show session details for debugging */}
                        <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg text-left">
                          <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                            {t('proofreading.sessionDetails')}:
                          </p>
                          <p className={`${fontClasses.xs} text-gray-600 dark:text-gray-300`}>
                            {t('proofreading.totalParagraphs')}: {currentSession.total_paragraphs}
                          </p>
                          <p className={`${fontClasses.xs} text-gray-600 dark:text-gray-300`}>
                            {t('proofreading.completedParagraphs')}: {currentSession.completed_paragraphs}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className={`text-gray-500 dark:text-gray-400 ${fontClasses.paragraph}`}>
                        {statusFilter === 'pending'
                          ? t('proofreading.noPending')
                          : t('proofreading.noSuggestions')}
                      </div>
                    )}
                  </div>
                ) : (
                  suggestions
                    ?.filter(s =>
                      statusFilter === 'all' ||
                      (statusFilter === 'pending' && !s.is_confirmed) ||
                      (statusFilter === 'accepted' && s.is_confirmed)
                    )
                    .map((suggestion, index) => {
                      const improvementLevel = suggestion.improvement_level || 'none'
                      const isNoChange = improvementLevel === 'none'

                      return (
                        <div
                          key={suggestion.id}
                          className={`bg-white dark:bg-gray-800 rounded-lg border p-3 transition-all ${isNoChange
                            ? 'border-gray-300 dark:border-gray-600 opacity-75'
                            : suggestion.is_confirmed
                              ? 'border-green-200 dark:border-green-800'
                              : focusedSuggestionIndex === index && statusFilter === 'pending'
                                ? 'border-blue-400 dark:border-blue-500 ring-2 ring-blue-100 dark:ring-blue-900'
                                : 'border-gray-200 dark:border-gray-700'
                            }`}
                        >
                          {/* Improvement level badge */}
                          <div className="flex items-center justify-between mb-2">
                            <div>
                              {improvementLevel === 'critical' && (
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300`}>
                                  Critical
                                </span>
                              )}
                              {improvementLevel === 'recommended' && (
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300`}>
                                  Recommended
                                </span>
                              )}
                              {improvementLevel === 'optional' && (
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300`}>
                                  Optional
                                </span>
                              )}
                              {improvementLevel === 'none' && (
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400`}>
                                  No Changes Needed
                                </span>
                              )}
                            </div>

                            {/* Status badge based on lock status */}
                            <span
                              className={`flex items-center gap-1 px-2 py-0.5 rounded ${fontClasses.xs} ${suggestion.is_confirmed
                                ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                                : 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300'
                                }`}
                            >
                              {suggestion.is_confirmed ? (
                                <>
                                  <Lock className="w-3 h-3" />
                                  {t('proofreading.accepted')}
                                </>
                              ) : (
                                <>
                                  <Unlock className="w-3 h-3" />
                                  {t('proofreading.pending')}
                                </>
                              )}
                            </span>
                          </div>

                          {/* Original text */}
                          <div className="mb-3">
                            <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                              {t('proofreading.originalText')}
                            </div>
                            <div className={`text-gray-700 dark:text-gray-300 ${fontClasses.paragraph}`}>
                              {suggestion.original_text}
                            </div>
                          </div>

                          {/* Current translation - full width if no suggested translation */}
                          <div className="mb-3">
                            <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1 flex items-center justify-between`}>
                              <span>{t('proofreading.currentTranslation')}</span>
                              {/* Edit and Lock/Unlock buttons for current translation - hide during edit mode */}
                              {editingCurrentTranslation !== suggestion.paragraph_id && (
                                <div className="flex items-center gap-1">
                                  {!suggestion.is_confirmed && (
                                    <button
                                      onClick={() => {
                                        setEditingCurrentTranslation(suggestion.paragraph_id)
                                        setEditCurrentText(suggestion.current_translation || suggestion.original_translation)
                                      }}
                                      className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                                      title={t('common.edit')}
                                    >
                                      <Edit2 className="w-3.5 h-3.5" />
                                    </button>
                                  )}
                                  <button
                                    onClick={() => confirmTranslationMutation.mutate({
                                      paragraphId: suggestion.paragraph_id,
                                      isConfirmed: !suggestion.is_confirmed
                                    })}
                                    disabled={confirmTranslationMutation.isPending}
                                    className={`p-1 rounded transition-colors ${suggestion.is_confirmed
                                      ? 'text-green-600 dark:text-green-400 hover:text-orange-600 dark:hover:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/30'
                                      : 'text-gray-400 hover:text-green-600 dark:hover:text-green-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                                      }`}
                                    title={suggestion.is_confirmed ? t('proofreading.unlock') : t('proofreading.confirm')}
                                  >
                                    {confirmTranslationMutation.isPending ? (
                                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : suggestion.is_confirmed ? (
                                      <Lock className="w-3.5 h-3.5" />
                                    ) : (
                                      <Unlock className="w-3.5 h-3.5" />
                                    )}
                                  </button>
                                </div>
                              )}
                            </div>
                            {editingCurrentTranslation === suggestion.paragraph_id ? (
                              <div>
                                <textarea
                                  value={editCurrentText}
                                  onChange={(e) => setEditCurrentText(e.target.value)}
                                  className={`w-full h-24 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded ${fontClasses.paragraph} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500`}
                                />
                                <div className="flex gap-2 mt-2">
                                  <button
                                    onClick={() => {
                                      updateTranslationMutation.mutate({
                                        paragraphId: suggestion.paragraph_id,
                                        text: editCurrentText,
                                      })
                                    }}
                                    disabled={updateTranslationMutation.isPending}
                                    className={`flex items-center gap-1 px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 ${fontClasses.xs}`}
                                  >
                                    {updateTranslationMutation.isPending ? (
                                      <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                      <Save className="w-3 h-3" />
                                    )}
                                    {t('common.save')}
                                  </button>
                                  <button
                                    onClick={() => setEditingCurrentTranslation(null)}
                                    className={`flex items-center gap-1 px-2 py-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                                  >
                                    <X className="w-3 h-3" />
                                    {t('common.cancel')}
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className={`text-gray-600 dark:text-gray-400 ${fontClasses.paragraph} bg-gray-50 dark:bg-gray-900/50 p-2 rounded ${suggestion.is_confirmed ? 'border-l-4 border-green-500' : ''
                                }`}>
                                {suggestion.current_translation || suggestion.original_translation}
                              </div>
                            )}
                          </div>

                          {/* Suggested translation - only show if exists */}
                          {suggestion.suggested_translation && (
                            <div className="mb-3">
                              <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                                {t('proofreading.suggestedTranslation')}
                              </div>
                              <div className={`text-blue-700 dark:text-blue-400 ${fontClasses.paragraph} bg-blue-50 dark:bg-blue-900/30 p-2 rounded`}>
                                {suggestion.suggested_translation}
                              </div>
                            </div>
                          )}

                          {/* Explanation - more prominent for comment-only mode */}
                          {suggestion.explanation && (
                            <div className={`mt-3 ${fontClasses.sm} text-gray-600 dark:text-gray-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3 rounded`}>
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex items-start gap-2 flex-1">
                                  <MessageSquare className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                                  <div>
                                    <span className="font-medium text-amber-800 dark:text-amber-300">{t('proofreading.feedback')}: </span>
                                    <span className="text-gray-700 dark:text-gray-300">{suggestion.explanation}</span>
                                  </div>
                                </div>
                                {/* LLM Recommendation button */}
                                {!suggestion.is_confirmed && !recommendations.has(suggestion.paragraph_id) && (
                                  <button
                                    onClick={() => handleGetRecommendation(
                                      suggestion.paragraph_id,
                                      suggestion.original_text || '',
                                      suggestion.current_translation || suggestion.original_translation,
                                      suggestion.explanation || ''
                                    )}
                                    disabled={loadingRecommendation === suggestion.paragraph_id || !hasLLMConfig}
                                    className={`flex items-center gap-1 px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0 ${fontClasses.xs}`}
                                    title={t('proofreading.getRecommendation')}
                                  >
                                    {loadingRecommendation === suggestion.paragraph_id ? (
                                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                      <Sparkles className="w-3.5 h-3.5" />
                                    )}
                                    <span className="hidden sm:inline">{t('proofreading.askLLM')}</span>
                                  </button>
                                )}
                              </div>
                            </div>
                          )}

                          {/* LLM Recommendation - show if available */}
                          {recommendations.has(suggestion.paragraph_id) && (
                            <div className={`mt-3 ${fontClasses.sm} bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 p-3 rounded`}>
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                                  <span className="font-medium text-purple-800 dark:text-purple-300">{t('proofreading.recommendedTranslation')}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                  <button
                                    onClick={() => handleApplyRecommendation(suggestion.paragraph_id)}
                                    disabled={updateTranslationMutation.isPending}
                                    className={`flex items-center gap-1 px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 ${fontClasses.xs}`}
                                    title={t('proofreading.applyRecommendation')}
                                  >
                                    {updateTranslationMutation.isPending ? (
                                      <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                      <Check className="w-3 h-3" />
                                    )}
                                    {t('common.apply')}
                                  </button>
                                  <button
                                    onClick={() => {
                                      setRecommendations(prev => {
                                        const next = new Map(prev)
                                        next.delete(suggestion.paragraph_id)
                                        return next
                                      })
                                    }}
                                    className={`flex items-center gap-1 px-2 py-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                                  >
                                    <X className="w-3 h-3" />
                                    {t('common.dismiss')}
                                  </button>
                                </div>
                              </div>
                              <div className={`text-purple-700 dark:text-purple-300 ${fontClasses.paragraph} bg-purple-100 dark:bg-purple-900/30 p-2 rounded`}>
                                {recommendations.get(suggestion.paragraph_id)}
                              </div>
                            </div>
                          )}

                        </div>
                      )
                    })
                )}
              </div>
            </div>
          )}

          {/* All Translations View */}
          {viewMode === 'all-translations' && (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Chapter navigation */}
              <div className="flex items-center justify-between mb-2 px-1">
                <button
                  onClick={goToPrevChapter}
                  disabled={!canGoPrev}
                  className={`flex items-center gap-0.5 px-1.5 py-0.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 ${fontClasses.xs}`}
                >
                  <ChevronLeft className="w-3 h-3" />
                  {t('preview.prevChapter')}
                </button>
                <span className={`text-gray-600 dark:text-gray-300 font-medium ${fontClasses.xs}`}>
                  {chapterContent?.title || t('preview.chapterNumber', { number: String(chapterContent?.chapter_number) })}
                </span>
                <button
                  onClick={goToNextChapter}
                  disabled={!canGoNext}
                  className={`flex items-center gap-0.5 px-1.5 py-0.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 disabled:text-gray-300 dark:disabled:text-gray-600 ${fontClasses.xs}`}
                >
                  {t('preview.nextChapter')}
                  <ChevronRight className="w-3 h-3" />
                </button>
              </div>

              {/* Paragraphs list */}
              <div className="flex-1 overflow-y-auto space-y-2">
                {isLoadingContent ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
                  </div>
                ) : paragraphs.length === 0 ? (
                  <div className={`text-center py-12 text-gray-500 dark:text-gray-400 ${fontClasses.paragraph}`}>
                    {t('preview.noContent')}
                  </div>
                ) : (
                  paragraphs.map((para) => (
                    <div
                      key={para.id}
                      className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-2"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {/* Original */}
                        <div className="min-w-0">
                          <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                            {t('translate.original')}
                          </div>
                          <div className={`text-gray-700 dark:text-gray-300 ${fontClasses.paragraph} leading-relaxed`}>
                            {para.original_text}
                          </div>
                        </div>

                        {/* Translation */}
                        <div className="min-w-0">
                          <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                            {t('translate.translation')}
                          </div>
                          {editingParagraph === para.id ? (
                            <div>
                              <textarea
                                value={editParagraphText}
                                onChange={(e) => setEditParagraphText(e.target.value)}
                                className={`w-full h-16 px-1.5 py-1 border border-gray-300 dark:border-gray-600 rounded ${fontClasses.paragraph} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500`}
                              />
                              <div className="flex gap-1.5 mt-1.5">
                                <button
                                  onClick={() => handleDirectSave(para.id)}
                                  disabled={updateTranslationMutation.isPending}
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

                      {/* Action button */}
                      {editingParagraph !== para.id && (
                        <div className="flex items-center justify-end mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-700">
                          <button
                            onClick={() => handleDirectEdit(para.id, para.translated_text || '')}
                            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Chapter Selection Modal */}
      {showChapterSelection && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className={`font-semibold text-gray-900 dark:text-gray-100 ${fontClasses.heading}`}>
                {t('proofreading.selectChapters')}
              </h3>
              <button
                onClick={() => setShowChapterSelection(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="mb-4 flex items-center justify-between">
                <p className={`text-gray-600 dark:text-gray-400 ${fontClasses.sm}`}>
                  {t('proofreading.selectChaptersHint')}
                </p>
                <button
                  onClick={handleSelectAllChapters}
                  className={`px-3 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded ${fontClasses.sm}`}
                >
                  {selectedChaptersForProofreading.size === orderedChapterIds.length
                    ? t('common.deselectAll')
                    : t('common.selectAll')}
                </button>
              </div>

              {/* Chapter list */}
              <div>
                {toc && toc.length > 0 ? (
                  <TreeChapterList
                    toc={toc}
                    selectedChapterId={null}
                    onSelectChapter={toggleChapterSelection}
                    fontClasses={fontClasses}
                    expandAll={true}
                    showCheckboxes={true}
                    selectedChapterIds={selectedChaptersForProofreading}
                    chapterStatsMap={chapterStatsMap}
                  />
                ) : chapters?.length ? (
                  <div className="space-y-1">
                    {chapters.map((chapter) => (
                      <label
                        key={chapter.id}
                        className={`flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.paragraph}`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedChaptersForProofreading.has(chapter.id)}
                          onChange={() => toggleChapterSelection(chapter.id)}
                          className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="flex-1 text-gray-900 dark:text-gray-100">
                          {chapter.title || t('preview.chapterNumber', { number: String(chapter.chapter_number) })}
                        </span>
                        <span className={`${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                          {chapter.translated_count} / {chapter.paragraph_count}
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    {t('preview.noChapters')}
                  </div>
                )}
              </div>
            </div>

            {/* Content Filter Option */}
            <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-amber-50 dark:bg-amber-900/20">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeNonMain}
                  onChange={(e) => setIncludeNonMain(e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600 text-amber-600 focus:ring-amber-500"
                />
                <div className="flex-1">
                  <span className={`text-gray-900 dark:text-gray-100 ${fontClasses.paragraph}`}>
                    {t('proofreading.includeNonMain')}
                  </span>
                  <p className={`text-gray-500 dark:text-gray-400 ${fontClasses.xs}`}>
                    {t('proofreading.includeNonMainHint')}
                  </p>
                </div>
              </label>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
              <span className={`text-gray-600 dark:text-gray-400 ${fontClasses.sm}`}>
                {t('proofreading.chaptersSelected', { count: String(selectedChaptersForProofreading.size) })}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowChapterSelection(false)}
                  className={`px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.button}`}
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleStartProofreading}
                  disabled={selectedChaptersForProofreading.size === 0}
                  className={`px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed ${fontClasses.button}`}
                >
                  {t('common.continue')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Preview Modal */}
      {projectId && (
        <PreviewModal
          isOpen={showPreviewModal}
          onClose={() => setShowPreviewModal(false)}
          projectId={projectId}
        />
      )}

      <PromptPreviewModal
        isOpen={showPromptPreview}
        onClose={() => setShowPromptPreview(false)}
        promptType="proofreading"
        projectId={projectId}
        variables={{
          // Project info
          'project.title': context.project?.epub_title || context.project?.name || '',
          'project.author': context.project?.epub_author || '',
          'project.author_background': context.project?.author_background || '',
          // Content (placeholders)
          'content.source': '(Original text will be provided during proofreading)',
          'content.target': '(Current translation will be provided)',
          // Derived from analysis (placeholders - real values come from backend)
          'derived.writing_style': '',
          'derived.tone': '',
          'derived.terminology_table': '',
          'derived.author_name': '',
          'derived.author_biography': context.project?.author_background || '',
          // Boolean flags (placeholders)
          'derived.has_analysis': false,
          'derived.has_writing_style': false,
          'derived.has_tone': false,
          'derived.has_terminology': false,
        }}
        onConfirm={handlePromptConfirm}
        isLoading={startMutation.isPending}
      />
    </div>
  )
}
