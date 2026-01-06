import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X, RotateCcw, Send, FileText, Code, List, Loader2, Save, Check } from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

interface PromptPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (systemPrompt?: string, userPrompt?: string) => void
  promptType: 'analysis' | 'translation' | 'reasoning' | 'proofreading'
  variables: Record<string, unknown>
  title?: string
  isLoading?: boolean
}

type TabType = 'system' | 'user' | 'variables'

export function PromptPreviewModal({
  isOpen,
  onClose,
  onConfirm,
  promptType,
  variables,
  title,
  isLoading = false,
}: PromptPreviewModalProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('system')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [userPrompt, setUserPrompt] = useState('')
  const [isModified, setIsModified] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Fetch prompt template
  const { data: template, isLoading: templateLoading } = useQuery({
    queryKey: ['prompt-template', promptType],
    queryFn: () => api.getPromptTemplate(promptType),
    enabled: isOpen,
  })

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: () => api.previewPrompt(
      promptType,
      variables,
      isModified ? systemPrompt : undefined,
      isModified ? userPrompt : undefined,
    ),
  })

  // Save mutation - permanently saves to .md files
  const saveMutation = useMutation({
    mutationFn: () => api.updatePromptTemplate(promptType, systemPrompt, userPrompt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompt-template', promptType] })
      setIsModified(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    },
  })

  // Load template when fetched
  useEffect(() => {
    if (template) {
      setSystemPrompt(template.system_prompt)
      setUserPrompt(template.user_prompt_template)
      setIsModified(false)
      // Auto-preview with variables
      previewMutation.mutate()
    }
  }, [template])

  // Handle prompt changes
  const handleSystemPromptChange = (value: string) => {
    setSystemPrompt(value)
    setIsModified(true)
  }

  const handleUserPromptChange = (value: string) => {
    setUserPrompt(value)
    setIsModified(true)
  }

  // Reset to template defaults
  const handleReset = () => {
    if (template) {
      setSystemPrompt(template.system_prompt)
      setUserPrompt(template.user_prompt_template)
      setIsModified(false)
      previewMutation.mutate()
    }
  }

  // Refresh preview
  const handleRefreshPreview = () => {
    previewMutation.mutate()
  }

  // Confirm and execute
  const handleConfirm = () => {
    // Only pass custom prompts if modified
    if (isModified) {
      const finalSystemPrompt = previewMutation.data?.system_prompt || systemPrompt
      const finalUserPrompt = previewMutation.data?.user_prompt || userPrompt
      onConfirm(finalSystemPrompt, finalUserPrompt)
    } else {
      // Use default prompts (pass undefined)
      onConfirm(undefined, undefined)
    }
  }

  if (!isOpen) return null

  const tabs: { id: TabType; labelKey: string; icon: typeof FileText }[] = [
    { id: 'system', labelKey: 'prompts.systemPrompt', icon: FileText },
    { id: 'user', labelKey: 'prompts.userPrompt', icon: Code },
    { id: 'variables', labelKey: 'prompts.variables', icon: List },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {title || t('prompts.title')}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 px-6">
          {tabs.map(({ id, labelKey, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === id
                  ? 'text-blue-600 border-blue-600 dark:text-blue-400 dark:border-blue-400'
                  : 'text-gray-500 border-transparent hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t(labelKey)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {templateLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full" />
            </div>
          ) : (
            <>
              {activeTab === 'system' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t('prompts.systemPrompt')}
                    </label>
                    <div className="flex items-center gap-3">
                      {isModified && (
                        <span className="text-xs text-amber-600 dark:text-amber-400">
                          {t('prompts.modified')}
                        </span>
                      )}
                      <button
                        onClick={handleRefreshPreview}
                        disabled={previewMutation.isPending}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400"
                      >
                        <RotateCcw className={`w-3 h-3 ${previewMutation.isPending ? 'animate-spin' : ''}`} />
                        {t('prompts.refreshPreview')}
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={systemPrompt}
                    onChange={(e) => handleSystemPromptChange(e.target.value)}
                    className="w-full h-48 px-4 py-3 border rounded-lg bg-gray-50 dark:bg-gray-900 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 font-mono text-sm resize-none"
                    placeholder={t('prompts.systemPromptPlaceholder')}
                  />

                  {/* Rendered Preview */}
                  <div className="mt-4">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                      {t('prompts.renderedPreview')}
                    </label>
                    <div className="p-4 border rounded-lg bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 max-h-64 overflow-auto">
                      <pre className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                        {previewMutation.data?.system_prompt || t('prompts.clickRefresh')}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'user' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t('prompts.userPrompt')}
                    </label>
                    <button
                      onClick={handleRefreshPreview}
                      disabled={previewMutation.isPending}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400"
                    >
                      <RotateCcw className={`w-3 h-3 ${previewMutation.isPending ? 'animate-spin' : ''}`} />
                      {t('prompts.refreshPreview')}
                    </button>
                  </div>
                  <textarea
                    value={userPrompt}
                    onChange={(e) => handleUserPromptChange(e.target.value)}
                    className="w-full h-48 px-4 py-3 border rounded-lg bg-gray-50 dark:bg-gray-900 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 font-mono text-sm resize-none"
                    placeholder={t('prompts.userPromptPlaceholder')}
                  />

                  {/* Rendered Preview */}
                  <div className="mt-4">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                      {t('prompts.renderedPreview')}
                    </label>
                    <div className="p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
                      <pre className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                        {previewMutation.data?.user_prompt || t('prompts.clickRefresh')}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'variables' && (
                <div className="space-y-4">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t('prompts.availableVariables')}
                  </label>
                  <div className="space-y-2">
                    {template?.variables.map((variable) => (
                      <div
                        key={variable}
                        className="flex items-start gap-4 p-3 border rounded-lg bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700"
                      >
                        <code className="text-sm font-mono text-blue-600 dark:text-blue-400 whitespace-nowrap">
                          {`{{${variable}}}`}
                        </code>
                        <div className="flex-1 text-sm text-gray-600 dark:text-gray-400 break-all">
                          {formatVariableValue(variables[variable])}
                        </div>
                      </div>
                    ))}
                    {(!template?.variables || template.variables.length === 0) && (
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {t('prompts.noVariables')}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              disabled={!isModified || saveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              {t('prompts.reset')}
            </button>
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!isModified || saveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {saveMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : saveSuccess ? (
                <Check className="w-4 h-4" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {saveSuccess ? t('prompts.saved') : t('prompts.save')}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleConfirm}
              disabled={templateLoading || isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              {t('prompts.send')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatVariableValue(value: unknown): string {
  if (value === undefined || value === null) {
    return '(empty)'
  }
  if (typeof value === 'object') {
    const str = JSON.stringify(value, null, 2)
    return str.length > 200 ? str.slice(0, 200) + '...' : str
  }
  const str = String(value)
  return str.length > 200 ? str.slice(0, 200) + '...' : str
}
