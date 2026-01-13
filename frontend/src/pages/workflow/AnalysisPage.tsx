import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Play, Check, RefreshCw, ArrowRight, BookOpen, FileText } from 'lucide-react'
import { api, Project, WorkflowStatus, AnalysisProgressEvent } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptPreviewModal } from '../../components/common/PromptPreviewModal'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'
import { AnalysisFieldCard } from '../../components/workflow/AnalysisFieldCard'
import { AnalysisStreamingPreview } from '../../components/workflow/AnalysisStreamingPreview'

interface OutletContext {
  project: Project
  workflowStatus: WorkflowStatus
  refetchWorkflow: () => void
}

// Progress step labels for display
const STEP_LABELS: Record<string, string> = {
  loading: 'analysis.progress.loading',
  sampling: 'analysis.progress.sampling',
  building_prompt: 'analysis.progress.buildingPrompt',
  analyzing: 'analysis.progress.analyzing',
  parsing: 'analysis.progress.parsing',
  saving: 'analysis.progress.saving',
  complete: 'analysis.progress.complete',
  error: 'common.error',
  warning: 'common.warning',
}

// Known field i18n keys mapping
const FIELD_I18N_KEYS: Record<string, string> = {
  author_bio: 'analysis.authorBio',
  writing_style: 'analysis.writingStyle',
  tone: 'analysis.tone',
  target_audience: 'analysis.targetAudience',
  genre_conventions: 'analysis.genreConventions',
  key_terminology: 'analysis.keyTerminology',
  terminology: 'analysis.keyTerminology',
  themes: 'analysis.themes',
  summary: 'analysis.summary',
}

export function AnalysisPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const { project, workflowStatus, refetchWorkflow } = useOutletContext<OutletContext>()

  // LLM config from settings store
  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // Global analyzing state for header display
  const setGlobalIsAnalyzing = useAppStore((state) => state.setIsAnalyzing)

  // Font size from app store
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  // Form state - stores the raw_analysis as editable form data
  const [formData, setFormData] = useState<Record<string, unknown>>({})

  // Prompt preview state
  const [showPromptPreview, setShowPromptPreview] = useState(false)

  // Streaming state
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [progressEvent, setProgressEvent] = useState<AnalysisProgressEvent | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const abortRef = useRef<{ abort: () => void } | null>(null)

  // Fetch existing analysis
  const { data: analysis, isLoading: analysisLoading, error: fetchError } = useQuery({
    queryKey: ['analysis', projectId],
    queryFn: () => api.getAnalysis(projectId!),
    enabled: !!projectId,
    retry: false,
  })

  // Update form when analysis loads
  useEffect(() => {
    if (analysis?.raw_analysis) {
      setFormData(analysis.raw_analysis)
    }
  }, [analysis])

  // Cancel any processing task on mount (after page refresh)
  useEffect(() => {
    const analysisProgress = workflowStatus?.analysis_progress
    if (analysisProgress?.status === 'processing' && projectId) {
      // User refreshed during analysis - cancel it
      api.cancelAnalysisTask(projectId).catch(console.error)
      refetchWorkflow()
    }
  }, []) // Only run on mount

  // Sync analyzing state to global store for header display
  useEffect(() => {
    setGlobalIsAnalyzing(isAnalyzing)
    return () => {
      // Clear analyzing state when leaving the page
      setGlobalIsAnalyzing(false)
    }
  }, [isAnalyzing, setGlobalIsAnalyzing])

  // Cleanup abort on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])

  // Start streaming analysis
  const startAnalysisStream = useCallback((customSystemPrompt?: string, customUserPrompt?: string) => {
    if (!projectId) return

    setIsAnalyzing(true)
    setProgressEvent(null)
    setAnalysisError(null)

    // Clear form data and cache immediately to show empty state during re-analysis
    setFormData({})
    queryClient.setQueryData(['analysis', projectId], null)

    const stream = api.startAnalysisStream(
      projectId,
      {
        config_id: configId || undefined,
        sample_count: 20,
        custom_system_prompt: customSystemPrompt,
        custom_user_prompt: customUserPrompt,
      },
      // onProgress - real-time SSE updates
      (event) => {
        setProgressEvent(event)
      },
      // onComplete
      (rawAnalysis) => {
        setIsAnalyzing(false)
        abortRef.current = null
        setProgressEvent(null)
        setFormData(rawAnalysis)
        queryClient.invalidateQueries({ queryKey: ['analysis', projectId] })
        refetchWorkflow()
      },
      // onError
      (error) => {
        setIsAnalyzing(false)
        abortRef.current = null
        setProgressEvent(null)
        setAnalysisError(error)
      }
    )

    abortRef.current = stream
  }, [projectId, configId, queryClient, refetchWorkflow])

  // Handler for prompt confirmation
  const handlePromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    setShowPromptPreview(false)
    startAnalysisStream(systemPrompt, userPrompt)
  }

  // Open prompt preview instead of directly starting analysis
  const handleAnalyzeClick = () => {
    setShowPromptPreview(true)
  }

  // Cancel analysis
  const handleCancelAnalysis = useCallback(async () => {
    setIsAnalyzing(false)
    setProgressEvent(null)

    // Abort SSE stream if active
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }

    // Call backend cancel API
    if (projectId) {
      try {
        await api.cancelAnalysisTask(projectId)
        refetchWorkflow()
      } catch (error) {
        console.error('Failed to cancel analysis task:', error)
      }
    }
  }, [projectId, refetchWorkflow])

  // Update/save state
  const [isSaving, setIsSaving] = useState(false)

  // Update analysis handler
  const handleUpdateAnalysis = useCallback(async (confirm: boolean) => {
    if (!projectId) return
    setIsSaving(true)
    try {
      await api.updateAnalysis(projectId, {
        updates: formData,
        confirm,
      })
      queryClient.invalidateQueries({ queryKey: ['analysis', projectId] })
      queryClient.invalidateQueries({ queryKey: ['workflowStatus', projectId] })
    } finally {
      setIsSaving(false)
    }
  }, [projectId, formData, queryClient])

  // Handle field changes - supports nested paths
  const handleFieldChange = (key: string, value: string) => {
    setFormData((prev) => {
      // Try to parse as JSON if it looks like JSON
      let parsedValue: unknown = value
      if (value.trim().startsWith('{') || value.trim().startsWith('[')) {
        try {
          parsedValue = JSON.parse(value)
        } catch {
          // Keep as string if parsing fails
        }
      }
      return { ...prev, [key]: parsedValue }
    })
  }

  const handleConfirm = async () => {
    try {
      await handleUpdateAnalysis(true)
      // Refetch workflow status to ensure ProjectLayout has updated data
      await refetchWorkflow()
      // Navigate immediately after successful confirmation
      navigate(`/project/${projectId}/translate`)
    } catch (error) {
      console.error('Failed to confirm analysis:', error)
    }
  }

  const handleContinue = () => {
    navigate(`/project/${projectId}/translate`)
  }

  // Check if analysis has actual content (not just an empty record)
  const hasAnalysisContent = analysis?.raw_analysis &&
    Object.keys(analysis.raw_analysis).length > 0
  const hasAnalysis = analysis && !fetchError && hasAnalysisContent

  // Get all fields from formData, excluding internal fields
  const analysisFields = Object.entries(formData).filter(
    ([key]) => !key.startsWith('_')
  )

  return (
    <div className="space-y-6">
      {/* Action Bar - unified format */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          {/* Left side: Title */}
          <div className="flex items-center gap-3">
            <h2 className={`font-semibold text-gray-900 dark:text-gray-100 ${fontClasses.heading}`}>
              {t('workflow.analysis')}
            </h2>
          </div>

          {/* Right side: All action buttons */}
          <div className="flex items-center gap-2">
            {/* LLM Config selector */}
            <LLMConfigSelector />

            {/* View prompt button */}
            <button
              onClick={() => setShowPromptPreview(true)}
              disabled={!hasLLMConfig}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 text-sm"
            >
              <FileText className="w-4 h-4" />
              {t('prompts.viewPrompt')}
            </button>

            {/* Analyze/Cancel button */}
            {isAnalyzing ? (
              <button
                onClick={handleCancelAnalysis}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
              >
                {t('common.cancel')}
              </button>
            ) : (
              <button
                onClick={handleAnalyzeClick}
                disabled={!hasLLMConfig || isAnalyzing}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {hasAnalysis ? (
                  <RefreshCw className="w-4 h-4" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {hasAnalysis ? t('analysis.reanalyze') : t('analysis.startAnalysis')}
              </button>
            )}

            {/* Confirm button - only when has analysis */}
            {hasAnalysis && (
              <button
                onClick={handleConfirm}
                disabled={isSaving || analysis?.user_confirmed}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${
                  analysis?.user_confirmed
                    ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 cursor-default'
                    : 'bg-green-600 text-white hover:bg-green-700 disabled:opacity-50'
                }`}
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {analysis?.user_confirmed ? t('analysis.confirmed') : t('analysis.confirmAnalysis')}
              </button>
            )}

            {/* Continue button - only when confirmed */}
            {analysis?.user_confirmed && (
              <button
                onClick={handleContinue}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                {t('workflow.continueToTranslation')}
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {analysisError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {t('common.error')}: {analysisError}
          </p>
        )}
      </div>

      {/* Analysis Progress */}
      {isAnalyzing && progressEvent && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
            {t('analysis.analyzing')}
          </h3>

          {/* Progress bar */}
          <div className="mb-4">
            <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-1">
              <span>{t(STEP_LABELS[progressEvent.step] || progressEvent.step)}</span>
              <span>{progressEvent.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${progressEvent.progress}%` }}
              />
            </div>
          </div>

          {/* Streaming preview during analysis - improved UI */}
          {progressEvent.step === 'analyzing' && progressEvent.partial_content ? (
            <AnalysisStreamingPreview
              partialContent={progressEvent.partial_content}
              progress={progressEvent.progress}
              message={progressEvent.message}
            />
          ) : (
            /* Status message for non-analyzing steps */
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {progressEvent.message}
            </p>
          )}
        </div>
      )}

      {/* Analysis Results - hide when analyzing */}
      {!isAnalyzing && (
        analysisLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : hasAnalysis ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">
              {t('analysis.results')}
            </h3>

            {/* Dynamic fields rendering with cards */}
            <div className="space-y-4">
              {analysisFields.map(([key, value]) => (
                <AnalysisFieldCard
                  key={key}
                  fieldKey={key}
                  value={value}
                  onChange={handleFieldChange}
                  i18nKey={FIELD_I18N_KEYS[key]}
                />
              ))}

              {analysisFields.length === 0 && (
                <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                  {t('analysis.noFields')}
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-12 shadow-sm border border-gray-200 dark:border-gray-700 text-center">
            <BookOpen className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              {t('analysis.noAnalysis')}
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {t('analysis.selectLLMAndStart')}
            </p>
          </div>
        )
      )}

      {/* Prompt Preview Modal */}
      <PromptPreviewModal
        isOpen={showPromptPreview}
        onClose={() => setShowPromptPreview(false)}
        promptType="analysis"
        projectId={projectId}
        variables={{
          // Simple keys for backwards compatibility
          title: project?.epub_title || project?.name || '',
          author: project?.epub_author || '',
          sample_paragraphs: '(Sample paragraphs will be loaded during analysis)',
          // Namespaced keys (canonical format)
          'project.title': project?.epub_title || project?.name || '',
          'project.author': project?.epub_author || '',
          'content.sample_paragraphs': '(Sample paragraphs will be loaded during analysis)',
        }}
        onConfirm={handlePromptConfirm}
        isLoading={isAnalyzing}
      />
    </div>
  )
}
