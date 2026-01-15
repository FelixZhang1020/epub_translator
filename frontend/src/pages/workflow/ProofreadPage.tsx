import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useOutletContext, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  X,
  Edit2,
  Loader2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  FileCheck,
  Save,
  MessageSquare,
  Lock,
  Unlock,
  Sparkles,
  Check,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptTemplateSelector } from '../../components/common/PromptTemplateSelector'
import { TreeChapterList } from '../../components/common/TreeChapterList'
import { WorkflowChapterList } from '../../components/workflow/WorkflowChapterList'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import {
  useOrderedChapterIds,
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

  // Session and suggestion state
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('pending')

  // Chapter state - for chapter list sidebar
  const [selectedChapter, setSelectedChapter] = useState<string | null>(
    searchParams.get('chapter') || null
  )

  // Keyboard navigation state
  const [focusedSuggestionIndex, setFocusedSuggestionIndex] = useState<number>(0)

  // Custom prompts from template selector (used when user edits in modal)
  const [customSystemPrompt, setCustomSystemPrompt] = useState<string | undefined>()
  const [customUserPrompt, setCustomUserPrompt] = useState<string | undefined>()

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
    enabled: !!selectedSession,
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
      setShowChapterSelection(false)
    },
    onError: (error: Error) => {
      console.error('Failed to start proofreading:', error)
      alert(t('proofreading.startFailed') + ': ' + error.message)
    },
  })

  // Handler for prompt confirmation from the selector modal
  const handlePromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    // Store custom prompts
    setCustomSystemPrompt(systemPrompt)
    setCustomUserPrompt(userPrompt)
    // Start proofreading with custom prompts
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
    // Start proofreading with selected chapters and current prompts
    const chapterIds = selectedChaptersForProofreading.size > 0
      ? Array.from(selectedChaptersForProofreading)
      : undefined
    startMutation.mutate({
      customSystemPrompt,
      customUserPrompt,
      chapterIds,
      includeNonMain,
    })
  }

  // Build chapter stats map for sidebar - show confirmed (proofread) count
  const chapterStatsMap = useMemo(() => {
    const map = new Map<string, { translated: number; total: number }>()
    chapters?.forEach(chapter => {
      map.set(chapter.id, {
        translated: chapter.confirmed_count,  // Show proofread (confirmed) count in sidebar
        total: chapter.paragraph_count,
      })
    })
    return map
  }, [chapters])

  // Build chapter stats map for selection modal - show translated count
  const chapterSelectionStatsMap = useMemo(() => {
    const map = new Map<string, { translated: number; total: number }>()
    chapters?.forEach(chapter => {
      map.set(chapter.id, {
        translated: chapter.translated_count,  // Show translated count in selection modal
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
      setEditingCurrentTranslation(null)
    },
    onError: (error: Error) => {
      console.error('Failed to update translation:', error)
      alert(t('common.error') + ': ' + error.message)
      // Reset editing state so user can try again or cancel
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

  // Confirm proofreading completion mutation
  const confirmProofreadingMutation = useMutation({
    mutationFn: async () => {
      return api.confirmProofreading(projectId!)
    },
    onSuccess: async () => {
      // Invalidate and refetch workflow status BEFORE navigation
      await queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
      await context?.refetchWorkflow()
      // Small delay to ensure React Query cache has updated
      await new Promise(resolve => setTimeout(resolve, 100))
      // Navigate after workflow status is confirmed updated
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
      if (!suggestions?.length) return
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
  }, [suggestions, statusFilter, focusedSuggestionIndex, editingCurrentTranslation])

  // Stats for current session - based on lock status (is_confirmed)
  const pendingCount = suggestions?.filter(s => !s.is_confirmed).length || 0
  const acceptedCount = suggestions?.filter(s => s.is_confirmed).length || 0


  // Get model display name
  const getModelName = (modelId: string) => {
    const model = models?.find(m => m.id === modelId)
    return model?.display_name || modelId
  }

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Action Bar - unified format */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-gray-700 mb-2">
        <div className="flex flex-wrap items-center gap-3">
          {/* Left Group: Back + LLM + Prompt */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/project/${projectId}/translate`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-sm font-medium transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">{t('common.back')}</span>
            </button>
            <LLMConfigSelector />
            <PromptTemplateSelector
              promptType="proofreading"
              projectId={projectId}
              variables={{
                'project.title': context.project?.epub_title || context.project?.name || '',
                'project.author': context.project?.epub_author || '',
                'content.source': t('prompts.placeholderOriginal'),
                'content.target': t('prompts.placeholderTarget'),
              }}
              disabled={!hasLLMConfig}
              onConfirm={handlePromptConfirm}
              isLoading={startMutation.isPending}
              compact
            />
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right Group: Start + Next */}
          <div className="flex items-center gap-2">
            {/* Start proofreading button */}
            <button
              onClick={handleStartClick}
              disabled={startMutation.isPending || currentSession?.status === 'processing'}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {startMutation.isPending || currentSession?.status === 'processing' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{t('proofreading.start')}</span>
            </button>

            {/* Next button */}
            <button
              onClick={() => confirmProofreadingMutation.mutate()}
              disabled={confirmProofreadingMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {confirmProofreadingMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{t('common.next')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main content area with chapter panel */}
      <div className="flex flex-1 min-h-0 overflow-x-auto">
        {/* Chapter list sidebar - always visible */}
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
          {/* No session yet */}
          {!sessions?.length && !isLoadingSessions && (
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
          {currentSession?.status === 'failed' && (
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
          {currentSession?.status === 'processing' && (
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
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
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
          {currentSession?.status === 'completed' && (
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

                      return (
                        <div
                          key={suggestion.id}
                          className={`bg-white dark:bg-gray-800 rounded border p-2 transition-all ${
                            suggestion.is_confirmed
                              ? 'border-green-200 dark:border-green-800'
                              : focusedSuggestionIndex === index && statusFilter === 'pending'
                                ? 'border-blue-400 dark:border-blue-500 ring-2 ring-blue-100 dark:ring-blue-900'
                                : 'border-gray-200 dark:border-gray-700'
                          }`}
                        >
                          {/* Grid for panels - 2 columns matching TranslateWorkflowPage */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {/* Left: Original text */}
                            <div className="min-w-0">
                              <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                                {t('translate.original')}
                              </div>
                              <div className={`text-gray-700 dark:text-gray-300 ${fontClasses.paragraph} leading-relaxed`}>
                                {suggestion.original_text}
                              </div>
                            </div>

                            {/* Right: Translation */}
                            <div className="min-w-0">
                              <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                                {t('translate.translation')}
                              </div>
                              {editingCurrentTranslation === suggestion.paragraph_id ? (
                                <div>
                                  <textarea
                                    value={editCurrentText}
                                    onChange={(e) => setEditCurrentText(e.target.value)}
                                    className={`w-full h-16 px-1.5 py-1 border border-gray-300 dark:border-gray-600 rounded ${fontClasses.paragraph} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500`}
                                  />
                                  <div className="flex gap-1.5 mt-1.5">
                                    <button
                                      onClick={() => {
                                        updateTranslationMutation.mutate({
                                          paragraphId: suggestion.paragraph_id,
                                          text: editCurrentText,
                                        })
                                      }}
                                      disabled={updateTranslationMutation.isPending}
                                      className={`flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700 ${fontClasses.xs}`}
                                    >
                                      {updateTranslationMutation.isPending ? (
                                        <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                      ) : (
                                        <Save className="w-2.5 h-2.5" />
                                      )}
                                      {t('common.save')}
                                    </button>
                                    <button
                                      onClick={() => setEditingCurrentTranslation(null)}
                                      className={`flex items-center gap-0.5 px-1.5 py-0.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                                    >
                                      <X className="w-2.5 h-2.5" />
                                      {t('common.cancel')}
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <div className={`${fontClasses.paragraph} leading-relaxed ${suggestion.current_translation || suggestion.original_translation ? 'text-blue-700 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500 italic'}`}>
                                  {suggestion.current_translation || suggestion.original_translation || t('common.noTranslation')}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Feedback section - compact inline */}
                          {suggestion.explanation && (
                            <div className={`mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 ${fontClasses.sm} text-gray-600 dark:text-gray-400`}>
                              <div className="flex items-start gap-1.5">
                                <MessageSquare className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                                <span className="text-gray-600 dark:text-gray-400">{suggestion.explanation}</span>
                              </div>
                            </div>
                          )}

                          {/* LLM Recommendation - show if available */}
                          {recommendations.has(suggestion.paragraph_id) && (
                            <div className={`mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 ${fontClasses.sm}`}>
                              <div className="flex items-start gap-1.5 mb-1.5">
                                <Sparkles className="w-3.5 h-3.5 text-purple-500 mt-0.5 flex-shrink-0" />
                                <span className="text-purple-700 dark:text-purple-300">{recommendations.get(suggestion.paragraph_id)}</span>
                              </div>
                              <div className="flex items-center gap-1.5 ml-5">
                                <button
                                  onClick={() => handleApplyRecommendation(suggestion.paragraph_id)}
                                  disabled={updateTranslationMutation.isPending}
                                  className={`flex items-center gap-0.5 px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 ${fontClasses.xs}`}
                                >
                                  {updateTranslationMutation.isPending ? (
                                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                  ) : (
                                    <Check className="w-2.5 h-2.5" />
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
                                  className={`flex items-center gap-0.5 px-1.5 py-0.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                                >
                                  <X className="w-2.5 h-2.5" />
                                  {t('common.dismiss')}
                                </button>
                              </div>
                            </div>
                          )}

                          {/* Action buttons - matching TranslateWorkflowPage footer style */}
                          <div className="flex items-center justify-end gap-1.5 mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-700">
                            {/* Improvement level indicator */}
                            {improvementLevel !== 'none' && (
                              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                improvementLevel === 'critical'
                                  ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                  : improvementLevel === 'recommended'
                                    ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
                                    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                              }`}>
                                {improvementLevel === 'critical' ? 'Critical' : improvementLevel === 'recommended' ? 'Recommended' : 'Optional'}
                              </span>
                            )}

                            {/* Spacer */}
                            <div className="flex-1" />

                            {/* Recommend button - only show if has feedback and not confirmed */}
                            {suggestion.explanation && !suggestion.is_confirmed && !recommendations.has(suggestion.paragraph_id) && (
                              <button
                                onClick={() => handleGetRecommendation(
                                  suggestion.paragraph_id,
                                  suggestion.original_text || '',
                                  suggestion.current_translation || suggestion.original_translation,
                                  suggestion.explanation || ''
                                )}
                                disabled={loadingRecommendation === suggestion.paragraph_id || !hasLLMConfig}
                                className="flex items-center gap-0.5 px-1.5 py-0.5 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded text-[10px] disabled:opacity-50"
                              >
                                {loadingRecommendation === suggestion.paragraph_id ? (
                                  <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                ) : (
                                  <Sparkles className="w-2.5 h-2.5" />
                                )}
                                {t('proofreading.askLLM')}
                              </button>
                            )}

                            {/* Edit button */}
                            <button
                              onClick={() => {
                                setEditingCurrentTranslation(suggestion.paragraph_id)
                                setEditCurrentText(suggestion.current_translation || suggestion.original_translation)
                              }}
                              disabled={suggestion.is_confirmed}
                              className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-[10px] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <Edit2 className="w-2.5 h-2.5" />
                              {t('common.edit')}
                            </button>

                            {/* Lock/Unlock button */}
                            <button
                              onClick={() => confirmTranslationMutation.mutate({
                                paragraphId: suggestion.paragraph_id,
                                isConfirmed: !suggestion.is_confirmed
                              })}
                              disabled={confirmTranslationMutation.isPending}
                              className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition-colors ${suggestion.is_confirmed
                                ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 hover:bg-orange-100 dark:hover:bg-orange-900/50 hover:text-orange-700 dark:hover:text-orange-400'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-green-100 dark:hover:bg-green-900/50 hover:text-green-700 dark:hover:text-green-400'
                              }`}
                            >
                              {confirmTranslationMutation.isPending ? (
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              ) : suggestion.is_confirmed ? (
                                <Lock className="w-2.5 h-2.5" />
                              ) : (
                                <Unlock className="w-2.5 h-2.5" />
                              )}
                              {suggestion.is_confirmed ? t('translate.locked') : t('translate.unlocked')}
                            </button>
                          </div>
                        </div>
                      )
                    })
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
                    chapterStatsMap={chapterSelectionStatsMap}
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

    </div>
  )
}

