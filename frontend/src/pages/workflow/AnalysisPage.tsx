import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Play, Check, RefreshCw, ArrowRight, BookOpen, FileText } from 'lucide-react'
import { api, Project, WorkflowStatus, AnalysisProgressEvent } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { PromptPreviewModal } from '../../components/common/PromptPreviewModal'
import { LLMConfigSelector } from '../../components/common/LLMConfigSelector'

interface OutletContext {
  project: Project
  workflowStatus: WorkflowStatus
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

// Helper to format field names for display
function formatFieldName(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// Helper to render a value based on its type
function renderValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

export function AnalysisPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const { project } = useOutletContext<OutletContext>()

  // LLM config from settings store
  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // Form state - stores the raw_analysis as editable form data
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [isDirty, setIsDirty] = useState(false)

  // Prompt preview state
  const [showPromptPreview, setShowPromptPreview] = useState(false)

  // Streaming progress state
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

  // Cleanup abort on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [])

  // Start streaming analysis
  const startAnalysisStream = useCallback((customSystemPrompt?: string, customUserPrompt?: string) => {
    if (!projectId) return

    setIsAnalyzing(true)
    setProgressEvent(null)
    setAnalysisError(null)

    const stream = api.startAnalysisStream(
      projectId,
      {
        config_id: configId || undefined,
        sample_count: 20,
        custom_system_prompt: customSystemPrompt,
        custom_user_prompt: customUserPrompt,
      },
      // onProgress
      (event) => {
        setProgressEvent(event)
      },
      // onComplete
      (rawAnalysis) => {
        setIsAnalyzing(false)
        setFormData(rawAnalysis)
        queryClient.invalidateQueries({ queryKey: ['analysis', projectId] })
      },
      // onError
      (error) => {
        setIsAnalyzing(false)
        setAnalysisError(error)
      }
    )

    abortRef.current = stream
  }, [projectId, configId, queryClient])

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
  const handleCancelAnalysis = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setIsAnalyzing(false)
    setProgressEvent(null)
  }, [])

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
      queryClient.invalidateQueries({ queryKey: ['workflow-status', projectId] })
      setIsDirty(false)
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
    setIsDirty(true)
  }

  const handleSave = () => {
    handleUpdateAnalysis(false)
  }

  const handleConfirm = () => {
    handleUpdateAnalysis(true)
  }

  const handleContinue = () => {
    navigate(`/project/${projectId}/translate`)
  }

  const hasAnalysis = analysis && !fetchError

  // Get all fields from formData, excluding internal fields
  const analysisFields = Object.entries(formData).filter(
    ([key]) => !key.startsWith('_')
  )

  return (
    <div className="space-y-6">
      {/* LLM Configuration */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('analysis.llmConfig')}
            </h2>
            <LLMConfigSelector />
            <button
              onClick={() => setShowPromptPreview(true)}
              disabled={!hasLLMConfig}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
            >
              <FileText className="w-4 h-4" />
              {t('prompts.viewPrompt')}
            </button>
          </div>
          <div className="flex items-center gap-3">
            {isAnalyzing ? (
              <button
                onClick={handleCancelAnalysis}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                {t('common.cancel')}
              </button>
            ) : (
              <button
                onClick={handleAnalyzeClick}
                disabled={!hasLLMConfig || isAnalyzing}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {hasAnalysis ? (
                  <RefreshCw className="w-4 h-4" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {hasAnalysis ? t('analysis.reanalyze') : t('analysis.startAnalysis')}
              </button>
            )}
          </div>
        </div>

        {analysisError && (
          <p className="mt-4 text-sm text-red-600">
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

          {/* Status message */}
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {progressEvent.message}
          </p>

          {/* Partial content preview during analysis */}
          {progressEvent.step === 'analyzing' && progressEvent.partial_content && (
            <div className="mt-4">
              <p className="text-xs text-gray-500 dark:text-gray-500 mb-1">
                {t('analysis.preview')}:
              </p>
              <pre className="bg-gray-100 dark:bg-gray-900 rounded p-3 text-xs text-gray-700 dark:text-gray-300 overflow-x-auto max-h-32 overflow-y-auto">
                {progressEvent.partial_content}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Analysis Results */}
      {analysisLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      ) : hasAnalysis ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('analysis.results')}
            </h2>
            {analysis.user_confirmed && (
              <span className="flex items-center gap-1 text-green-600 text-sm">
                <Check className="w-4 h-4" />
                {t('analysis.confirmed')}
              </span>
            )}
          </div>

          {/* Dynamic fields rendering */}
          <div className="space-y-6">
            {analysisFields.map(([key, value]) => {
              const isObject = typeof value === 'object' && value !== null
              const displayValue = renderValue(value)

              return (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {formatFieldName(key)}
                  </label>
                  <textarea
                    value={displayValue}
                    onChange={(e) => handleFieldChange(key, e.target.value)}
                    rows={isObject ? 6 : 3}
                    className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 ${
                      isObject ? 'font-mono text-sm' : ''
                    }`}
                  />
                </div>
              )
            })}

            {analysisFields.length === 0 && (
              <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                {t('analysis.noFields')}
              </p>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                disabled={!isDirty || isSaving}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
              >
                {t('common.save')}
              </button>
              <button
                onClick={handleConfirm}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {t('analysis.confirmAnalysis')}
              </button>
            </div>

            {analysis.user_confirmed && (
              <button
                onClick={handleContinue}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                {t('workflow.continueToTranslation')}
                <ArrowRight className="w-4 h-4" />
              </button>
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
      )}

      {/* Prompt Preview Modal */}
      <PromptPreviewModal
        isOpen={showPromptPreview}
        onClose={() => setShowPromptPreview(false)}
        promptType="analysis"
        variables={{
          title: project?.name || '',
          author: project?.author || 'Unknown',
          sample_paragraphs: '(Sample paragraphs will be loaded during analysis)',
        }}
        onConfirm={handlePromptConfirm}
        isLoading={isAnalyzing}
      />
    </div>
  )
}
