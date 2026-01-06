import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Check,
  X,
  Edit2,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  FileCheck,
  Save,
  FileText,
  ChevronLeft,
  ChevronRight,
  CheckCheck,
  Eye,
  MessageSquare,
  BookOpen,
} from 'lucide-react'
import { api, ProofreadingSuggestion, TocItem } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptPreviewModal } from '../../components/common/PromptPreviewModal'
import { TreeChapterList } from '../../components/common/TreeChapterList'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import { ResizeHandle } from '../../components/common/ResizeHandle'
import { PreviewModal } from '../../components/preview/PreviewModal'

// Helper function to flatten TOC into ordered chapter IDs
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
  } | null
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
  const queryClient = useQueryClient()
  const context = useOutletContext<WorkflowContext>()

  // App store for font size, panel widths
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const panelWidths = useAppStore((state) => state.panelWidths)
  const setPanelWidth = useAppStore((state) => state.setPanelWidth)

  // Settings store for LLM config
  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // Panel width constraints
  const MIN_CHAPTER_LIST_WIDTH = 120
  const MAX_CHAPTER_LIST_WIDTH = 400

  // Resize handler
  const handleChapterListResize = useCallback((delta: number) => {
    const newWidth = Math.max(
      MIN_CHAPTER_LIST_WIDTH,
      Math.min(MAX_CHAPTER_LIST_WIDTH, panelWidths.chapterList + delta)
    )
    setPanelWidth('chapterList', newWidth)
  }, [panelWidths.chapterList, setPanelWidth])

  // View mode state
  const [viewMode, setViewMode] = useState<ViewMode>('llm-suggestions')

  // Session and suggestion state
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [editingSuggestion, setEditingSuggestion] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set())

  // Chapter state (for all-translations mode)
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [editingParagraph, setEditingParagraph] = useState<string | null>(null)
  const [editParagraphText, setEditParagraphText] = useState('')

  // Keyboard navigation state
  const [focusedSuggestionIndex, setFocusedSuggestionIndex] = useState<number>(0)

  // Prompt preview state
  const [showPromptPreview, setShowPromptPreview] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)

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
  const orderedChapterIds = useMemo(() => {
    if (toc && toc.length > 0) {
      return flattenTocToChapterIds(toc)
    }
    return chapters?.map(c => c.id) || []
  }, [toc, chapters])

  // Auto-select first chapter when viewing all translations
  useEffect(() => {
    if (viewMode === 'all-translations' && orderedChapterIds.length > 0 && !selectedChapter) {
      setSelectedChapter(orderedChapterIds[0])
    }
  }, [viewMode, orderedChapterIds, selectedChapter])

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
    mutationFn: async (params?: { customSystemPrompt?: string; customUserPrompt?: string }) => {
      return api.startProofreading(projectId!, {
        config_id: configId || undefined,
        custom_system_prompt: params?.customSystemPrompt,
        custom_user_prompt: params?.customUserPrompt,
      })
    },
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['proofreadingSessions', projectId] })
      setSelectedSession(session.id)
      setViewMode('llm-suggestions')
    },
  })

  // Handler for prompt confirmation
  const handlePromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    setShowPromptPreview(false)
    startMutation.mutate({
      customSystemPrompt: systemPrompt,
      customUserPrompt: userPrompt,
    })
  }

  // Open prompt preview
  const handleStartClick = () => {
    setShowPromptPreview(true)
  }

  // Update suggestion mutation
  const updateSuggestionMutation = useMutation({
    mutationFn: async ({ id, action, text }: { id: string; action: string; text?: string }) => {
      return api.updateSuggestion(id, { action, modified_text: text })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proofreadingSuggestions', selectedSession] })
      setEditingSuggestion(null)
    },
  })

  // Apply suggestions mutation
  const applyMutation = useMutation({
    mutationFn: async () => {
      return api.applySuggestions(selectedSession!)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proofreadingSuggestions', selectedSession] })
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId] })
      context?.refetchWorkflow()
    },
  })

  // Update translation mutation (for direct editing)
  const updateTranslationMutation = useMutation({
    mutationFn: ({ paragraphId, text }: { paragraphId: string; text: string }) =>
      api.updateTranslation(paragraphId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapter', projectId, selectedChapter] })
      setEditingParagraph(null)
    },
  })

  // Handle actions
  const handleAccept = (id: string) => {
    updateSuggestionMutation.mutate({ id, action: 'accept' })
  }

  const handleReject = (id: string) => {
    updateSuggestionMutation.mutate({ id, action: 'reject' })
  }

  const handleModify = (id: string) => {
    updateSuggestionMutation.mutate({ id, action: 'modify', text: editText })
  }

  const handleEdit = (suggestion: ProofreadingSuggestion) => {
    setEditingSuggestion(suggestion.id)
    setEditText(suggestion.suggested_translation)
  }

  // Batch operations
  const handleSelectAll = () => {
    const pendingSuggestions = suggestions?.filter(s => s.status === 'pending') || []
    setSelectedSuggestions(new Set(pendingSuggestions.map(s => s.id)))
  }

  const handleDeselectAll = () => {
    setSelectedSuggestions(new Set())
  }

  const handleBatchAccept = async () => {
    for (const id of selectedSuggestions) {
      await updateSuggestionMutation.mutateAsync({ id, action: 'accept' })
    }
    setSelectedSuggestions(new Set())
  }

  const handleBatchReject = async () => {
    for (const id of selectedSuggestions) {
      await updateSuggestionMutation.mutateAsync({ id, action: 'reject' })
    }
    setSelectedSuggestions(new Set())
  }

  const toggleSuggestionSelection = (id: string) => {
    setSelectedSuggestions(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Direct edit handlers
  const handleDirectEdit = (paragraphId: string, currentText: string) => {
    setEditingParagraph(paragraphId)
    setEditParagraphText(currentText || '')
  }

  const handleDirectSave = (paragraphId: string) => {
    updateTranslationMutation.mutate({ paragraphId, text: editParagraphText })
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (viewMode !== 'llm-suggestions' || !suggestions?.length) return
      if (editingSuggestion) return // Disable when editing

      const filteredSuggestions = suggestions.filter(s =>
        statusFilter === 'all' || s.status === statusFilter
      )

      if (filteredSuggestions.length === 0) return

      const currentSuggestion = filteredSuggestions[focusedSuggestionIndex]
      if (!currentSuggestion || currentSuggestion.status !== 'pending') return

      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault()
        handleAccept(currentSuggestion.id)
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault()
        handleReject(currentSuggestion.id)
      } else if (e.key === 'e' || e.key === 'E') {
        e.preventDefault()
        handleEdit(currentSuggestion)
      } else if (e.key === 'ArrowDown' || e.key === 'j') {
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
  }, [viewMode, suggestions, statusFilter, focusedSuggestionIndex, editingSuggestion])

  // Stats for current session
  const pendingCount = suggestions?.filter(s => s.status === 'pending').length || 0
  const acceptedCount = suggestions?.filter(s => s.status === 'accepted' || s.status === 'modified').length || 0
  const rejectedCount = suggestions?.filter(s => s.status === 'rejected').length || 0

  // Get model display name
  const getModelName = (modelId: string) => {
    const model = models?.find(m => m.id === modelId)
    return model?.display_name || modelId
  }

  // Chapter navigation
  const currentChapterIndex = orderedChapterIds.findIndex(id => id === selectedChapter)
  const canGoPrev = currentChapterIndex > 0
  const canGoNext = currentChapterIndex >= 0 && currentChapterIndex < orderedChapterIds.length - 1

  const paragraphs = chapterContent?.paragraphs || []

  return (
    <div className={`h-full flex flex-col ${fontClasses.base}`}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 bg-white dark:bg-gray-800 p-2 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h2 className={`font-medium text-gray-900 dark:text-gray-100 ${fontClasses.heading}`}>{t('proofreading.title')}</h2>
          {currentSession && (
            <span className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
              {t('proofreading.round')} {currentSession.round_number}
            </span>
          )}

          {/* View mode toggle */}
          <div className="flex rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5">
            <button
              onClick={() => setViewMode('llm-suggestions')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md ${fontClasses.sm} font-medium transition-colors ${
                viewMode === 'llm-suggestions'
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
              className={`flex items-center gap-1 px-2 py-1 rounded-md ${fontClasses.sm} font-medium transition-colors ${
                viewMode === 'all-translations'
                  ? 'bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t('proofreading.allTranslations')}</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
            disabled={!hasLLMConfig || startMutation.isPending || currentSession?.status === 'processing'}
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
        </div>
      </div>

      {/* Main content area with optional chapter panel */}
      <div className="flex flex-1 min-h-0">
        {/* Chapter list sidebar - only for all-translations view */}
        {viewMode === 'all-translations' && (
          <>
            <div
              className="hidden lg:flex lg:flex-col flex-shrink-0"
              style={{ width: panelWidths.chapterList }}
            >
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-2 h-full overflow-y-auto">
                <h3 className={`font-medium text-gray-900 dark:text-gray-100 mb-1.5 ${fontClasses.sm}`}>
                  {t('preview.chapterList')}
                </h3>
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
                ) : null}
              </div>
            </div>
            <div className="hidden lg:flex h-full">
              <ResizeHandle onResize={handleChapterListResize} className="h-full" />
            </div>
          </>
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

          {/* Session in progress */}
          {currentSession?.status === 'processing' && viewMode === 'llm-suggestions' && (
            <div className="bg-blue-50 dark:bg-blue-900/30 p-4 rounded-lg mb-4">
              <div className="flex items-center gap-3 mb-2">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400" />
                <span className={`font-medium text-blue-700 dark:text-blue-300 ${fontClasses.base}`}>
                  {t('proofreading.inProgress')}
                </span>
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
          {viewMode === 'llm-suggestions' && currentSession?.status === 'completed' && suggestions && (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Stats bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-white dark:bg-gray-800 p-2 rounded-lg border border-gray-200 dark:border-gray-700 mb-2">
                <div className="flex items-center gap-2 lg:gap-4">
                  <button
                    onClick={() => { setStatusFilter('pending'); setFocusedSuggestionIndex(0) }}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded ${fontClasses.sm} ${
                      statusFilter === 'pending' ? 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    <AlertCircle className="w-4 h-4" />
                    {t('proofreading.pending')} ({pendingCount})
                  </button>
                  <button
                    onClick={() => { setStatusFilter('accepted'); setFocusedSuggestionIndex(0) }}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded ${fontClasses.sm} ${
                      statusFilter === 'accepted' ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    <CheckCircle className="w-4 h-4" />
                    {t('proofreading.accepted')} ({acceptedCount})
                  </button>
                  <button
                    onClick={() => { setStatusFilter('rejected'); setFocusedSuggestionIndex(0) }}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded ${fontClasses.sm} ${
                      statusFilter === 'rejected' ? 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    <XCircle className="w-4 h-4" />
                    {t('proofreading.rejected')} ({rejectedCount})
                  </button>
                  <button
                    onClick={() => { setStatusFilter('all'); setFocusedSuggestionIndex(0) }}
                    className={`px-2 py-1 rounded ${fontClasses.sm} ${
                      statusFilter === 'all' ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    {t('proofreading.all')}
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {/* Batch operations */}
                  {statusFilter === 'pending' && pendingCount > 0 && (
                    <>
                      {selectedSuggestions.size > 0 ? (
                        <>
                          <span className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
                            {selectedSuggestions.size} {t('proofreading.selected')}
                          </span>
                          <button
                            onClick={handleDeselectAll}
                            className={`px-2 py-1 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ${fontClasses.sm}`}
                          >
                            {t('proofreading.deselectAll')}
                          </button>
                          <button
                            onClick={handleBatchAccept}
                            disabled={updateSuggestionMutation.isPending}
                            className={`flex items-center gap-1 px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 ${fontClasses.sm}`}
                          >
                            <CheckCheck className="w-3.5 h-3.5" />
                            {t('proofreading.batchAccept')}
                          </button>
                          <button
                            onClick={handleBatchReject}
                            disabled={updateSuggestionMutation.isPending}
                            className={`flex items-center gap-1 px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 ${fontClasses.sm}`}
                          >
                            <X className="w-3.5 h-3.5" />
                            {t('proofreading.batchReject')}
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={handleSelectAll}
                          className={`px-2 py-1 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ${fontClasses.sm}`}
                        >
                          {t('proofreading.selectAll')}
                        </button>
                      )}
                    </>
                  )}

                  {acceptedCount > 0 && (
                    <button
                      onClick={() => applyMutation.mutate()}
                      disabled={applyMutation.isPending}
                      className={`flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 ${fontClasses.button}`}
                    >
                      {applyMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <ArrowRight className="w-4 h-4" />
                      )}
                      {t('proofreading.applyChanges')} ({acceptedCount})
                    </button>
                  )}
                </div>
              </div>

              {/* Keyboard shortcuts hint */}
              {statusFilter === 'pending' && pendingCount > 0 && (
                <div className={`flex items-center gap-4 mb-2 px-2 py-1 bg-gray-50 dark:bg-gray-800/50 rounded ${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                  <span>{t('proofreading.keyboardShortcuts')}:</span>
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">A</kbd> {t('proofreading.shortcutAccept')}</span>
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">R</kbd> {t('proofreading.shortcutReject')}</span>
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">E</kbd> {t('proofreading.shortcutEdit')}</span>
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">↑↓</kbd> {t('proofreading.shortcutNav')}</span>
                </div>
              )}

              {/* Suggestions list */}
              <div className="flex-1 overflow-y-auto space-y-3">
                {isLoadingSuggestions ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
                  </div>
                ) : suggestions?.length === 0 ? (
                  <div className={`text-center py-12 text-gray-500 dark:text-gray-400 ${fontClasses.paragraph}`}>
                    {statusFilter === 'pending'
                      ? t('proofreading.noPending')
                      : t('proofreading.noSuggestions')}
                  </div>
                ) : (
                  suggestions?.map((suggestion, index) => (
                    <div
                      key={suggestion.id}
                      className={`bg-white dark:bg-gray-800 rounded-lg border p-3 transition-all ${
                        suggestion.status === 'accepted' || suggestion.status === 'modified'
                          ? 'border-green-200 dark:border-green-800'
                          : suggestion.status === 'rejected'
                          ? 'border-red-200 dark:border-red-800'
                          : focusedSuggestionIndex === index && statusFilter === 'pending'
                          ? 'border-blue-400 dark:border-blue-500 ring-2 ring-blue-100 dark:ring-blue-900'
                          : 'border-gray-200 dark:border-gray-700'
                      }`}
                    >
                      {/* Checkbox for batch selection */}
                      {suggestion.status === 'pending' && (
                        <div className="flex items-center mb-2">
                          <button
                            onClick={() => toggleSuggestionSelection(suggestion.id)}
                            className={`p-1 rounded ${
                              selectedSuggestions.has(suggestion.id)
                                ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                                : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                            }`}
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}

                      {/* Original text */}
                      <div className="mb-3">
                        <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                          {t('proofreading.originalText')}
                        </div>
                        <div className={`text-gray-700 dark:text-gray-300 ${fontClasses.paragraph}`}>
                          {suggestion.original_text}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {/* Current translation */}
                        <div>
                          <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                            {t('proofreading.currentTranslation')}
                          </div>
                          <div className={`text-gray-600 dark:text-gray-400 ${fontClasses.paragraph} bg-gray-50 dark:bg-gray-900/50 p-2 rounded`}>
                            {suggestion.original_translation}
                          </div>
                        </div>

                        {/* Suggested translation */}
                        <div>
                          <div className={`${fontClasses.label} text-gray-400 dark:text-gray-500 uppercase mb-1`}>
                            {t('proofreading.suggestedTranslation')}
                          </div>
                          {editingSuggestion === suggestion.id ? (
                            <div>
                              <textarea
                                value={editText}
                                onChange={(e) => setEditText(e.target.value)}
                                className={`w-full h-20 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded ${fontClasses.paragraph} bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500`}
                              />
                              <div className="flex gap-2 mt-2">
                                <button
                                  onClick={() => handleModify(suggestion.id)}
                                  disabled={updateSuggestionMutation.isPending}
                                  className={`flex items-center gap-1 px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 ${fontClasses.xs}`}
                                >
                                  <Save className="w-3 h-3" />
                                  {t('common.save')}
                                </button>
                                <button
                                  onClick={() => setEditingSuggestion(null)}
                                  className={`flex items-center gap-1 px-2 py-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${fontClasses.xs}`}
                                >
                                  <X className="w-3 h-3" />
                                  {t('common.cancel')}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className={`text-blue-700 dark:text-blue-400 ${fontClasses.paragraph} bg-blue-50 dark:bg-blue-900/30 p-2 rounded`}>
                              {suggestion.user_modified_text || suggestion.suggested_translation}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Explanation */}
                      {suggestion.explanation && (
                        <div className={`mt-3 ${fontClasses.sm} text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/50 p-2 rounded`}>
                          <span className="font-medium">{t('proofreading.explanation')}: </span>
                          {suggestion.explanation}
                        </div>
                      )}

                      {/* Actions */}
                      {suggestion.status === 'pending' && (
                        <div className="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                          <button
                            onClick={() => handleEdit(suggestion)}
                            className={`flex items-center gap-1 px-2 py-1 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ${fontClasses.sm}`}
                          >
                            <Edit2 className="w-4 h-4" />
                            {t('common.edit')}
                          </button>
                          <button
                            onClick={() => handleReject(suggestion.id)}
                            disabled={updateSuggestionMutation.isPending}
                            className={`flex items-center gap-1 px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded ${fontClasses.sm}`}
                          >
                            <X className="w-4 h-4" />
                            {t('proofreading.reject')}
                          </button>
                          <button
                            onClick={() => handleAccept(suggestion.id)}
                            disabled={updateSuggestionMutation.isPending}
                            className={`flex items-center gap-1 px-2 py-1 bg-green-600 text-white hover:bg-green-700 rounded ${fontClasses.sm}`}
                          >
                            <Check className="w-4 h-4" />
                            {t('proofreading.accept')}
                          </button>
                        </div>
                      )}

                      {/* Status badge */}
                      {suggestion.status !== 'pending' && (
                        <div className="flex items-center justify-end mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                          <span
                            className={`flex items-center gap-1 px-2 py-1 rounded ${fontClasses.xs} ${
                              suggestion.status === 'accepted' || suggestion.status === 'modified'
                                ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                                : 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300'
                            }`}
                          >
                            {suggestion.status === 'accepted' || suggestion.status === 'modified' ? (
                              <CheckCircle className="w-3 h-3" />
                            ) : (
                              <XCircle className="w-3 h-3" />
                            )}
                            {suggestion.status === 'modified'
                              ? t('proofreading.modified')
                              : suggestion.status === 'accepted'
                              ? t('proofreading.statusAccepted')
                              : t('proofreading.statusRejected')}
                          </span>
                        </div>
                      )}
                    </div>
                  ))
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
                  onClick={() => {
                    if (canGoPrev) {
                      setSelectedChapter(orderedChapterIds[currentChapterIndex - 1])
                    }
                  }}
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
                  onClick={() => {
                    if (canGoNext) {
                      setSelectedChapter(orderedChapterIds[currentChapterIndex + 1])
                    }
                  }}
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
        variables={{
          original_text: '(Original text will be provided during proofreading)',
          current_translation: '(Current translation will be provided)',
          author_biography: '',
          writing_style: '',
          tone: '',
          target_audience: '',
          genre_conventions: '',
        }}
        onConfirm={handlePromptConfirm}
        isLoading={startMutation.isPending}
      />
    </div>
  )
}
