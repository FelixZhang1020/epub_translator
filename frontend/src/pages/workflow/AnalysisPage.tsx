import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Play, RefreshCw, ArrowRight, BookOpen } from 'lucide-react'
import { api, Project, WorkflowStatus, AnalysisProgressEvent } from '../../services/api/client'
import { useTranslation, useAppStore } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptTemplateSelector } from '../../components/common/PromptTemplateSelector'
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

  // Form state - stores the raw_analysis as editable form data
  const [formData, setFormData] = useState<Record<string, unknown>>({})

  // Custom prompts from template selector (used when user edits in modal)
  const [customSystemPrompt, setCustomSystemPrompt] = useState<string | undefined>()
  const [customUserPrompt, setCustomUserPrompt] = useState<string | undefined>()

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

  // Handler for prompt confirmation from the selector modal
  const handlePromptConfirm = (systemPrompt?: string, userPrompt?: string) => {
    // Store custom prompts
    setCustomSystemPrompt(systemPrompt)
    setCustomUserPrompt(userPrompt)
    // Start analysis with custom prompts
    startAnalysisStream(systemPrompt, userPrompt)
  }

  // Start analysis with current prompts
  const handleAnalyzeClick = () => {
    startAnalysisStream(customSystemPrompt, customUserPrompt)
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

  // Check if analysis has actual content (not just an empty record)
  const hasAnalysisContent = analysis?.raw_analysis &&
    Object.keys(analysis.raw_analysis).length > 0
  const hasAnalysis = analysis && !fetchError && hasAnalysisContent

  // Get all fields from formData, excluding internal fields
  const analysisFields = Object.entries(formData).filter(
    ([key]) => !key.startsWith('_')
  )

  return (
    <div className="flex flex-col gap-2">
      {/* Action Bar - unified format */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="flex flex-wrap items-center gap-3">
          {/* Left Group: LLM + Prompt (no Back - first stage) */}
          <div className="flex items-center gap-2">
            <LLMConfigSelector />
            <PromptTemplateSelector
              promptType="analysis"
              projectId={projectId}
              variables={{
                'project.title': project?.epub_title || project?.name || '',
                'project.author': project?.epub_author || '',
                'content.sample_paragraphs': t('prompts.placeholderSamples'),
              }}
              disabled={!hasLLMConfig}
              onConfirm={handlePromptConfirm}
              isLoading={isAnalyzing}
            />
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right Group: Actions + Next */}
          <div className="flex items-center gap-2">
            {/* Analyze/Cancel button */}
            {isAnalyzing ? (
              <button
                onClick={handleCancelAnalysis}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium transition-colors"
              >
                {t('common.cancel')}
              </button>
            ) : (
              <button
                onClick={handleAnalyzeClick}
                disabled={!hasLLMConfig || isAnalyzing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
              >
                {hasAnalysis ? (
                  <RefreshCw className="w-4 h-4" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">
                  {hasAnalysis ? t('analysis.reanalyze') : t('analysis.startAnalysis')}
                </span>
              </button>
            )}

            {/* Next button - confirms & navigates */}
            <button
              onClick={handleConfirm}
              disabled={!hasAnalysis || isSaving || isAnalyzing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{t('common.next')}</span>
            </button>
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

    </div>
  )
}
