import { useState, useEffect, useCallback, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  X,
  RotateCcw,
  Send,
  FileText,
  Code,
  Loader2,
  ChevronDown,
  Star,
  Check,
  RefreshCw,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

// =============================================================================
// Types
// =============================================================================

interface PromptPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (systemPrompt?: string, userPrompt?: string) => void
  promptType: 'analysis' | 'translation' | 'proofreading' | 'optimization'
  variables: Record<string, unknown>
  title?: string
  isLoading?: boolean
  projectId?: string
}

type TabType = 'system' | 'user'

interface TemplateOption {
  name: string
  displayName: string
  systemPrompt: string
  userPrompt: string
}

// =============================================================================
// Template Dropdown Component
// =============================================================================

function TemplateDropdown({
  options,
  selectedName,
  defaultName,
  onSelect,
  disabled,
}: {
  options: TemplateOption[]
  selectedName: string
  defaultName: string
  onSelect: (name: string) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selected = options.find(o => o.name === selectedName)
  const isDefault = selectedName === defaultName

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-2 border rounded-lg bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-700 min-w-[200px] justify-between text-sm disabled:opacity-50 transition-colors"
      >
        <div className="flex items-center gap-2 truncate">
          {isDefault && (
            <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500 flex-shrink-0" />
          )}
          <span className="truncate">{selected?.displayName || t('prompts.selectTemplate')}</span>
        </div>
        <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-full min-w-[240px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl z-50 max-h-64 overflow-auto">
          {options.map((option) => {
            const isOptionDefault = option.name === defaultName
            const isSelected = option.name === selectedName

            return (
              <button
                key={option.name}
                type="button"
                onClick={() => {
                  onSelect(option.name)
                  setIsOpen(false)
                }}
                className={`w-full text-left px-3 py-2.5 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-900 dark:text-gray-100 text-sm transition-colors ${
                  isSelected ? 'bg-blue-50 dark:bg-blue-900/30' : ''
                }`}
              >
                <div className="w-5 flex-shrink-0">
                  {isOptionDefault && <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />}
                </div>
                <span className="flex-1 truncate">{option.displayName}</span>
                {isSelected && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PromptPreviewModal({
  isOpen,
  onClose,
  onConfirm,
  promptType,
  variables,
  title,
  isLoading = false,
  projectId,
}: PromptPreviewModalProps) {
  const { t } = useTranslation()

  // UI State
  const [activeTab, setActiveTab] = useState<TabType>('system')

  // System prompt state
  const [systemTemplateName, setSystemTemplateName] = useState('default')
  const [systemPromptOriginal, setSystemPromptOriginal] = useState('')
  const [systemPromptEdited, setSystemPromptEdited] = useState('')
  const [systemPromptRendered, setSystemPromptRendered] = useState('')

  // User prompt state (from project, no template selection)
  const [userPromptOriginal, setUserPromptOriginal] = useState('')
  const [userPromptEdited, setUserPromptEdited] = useState('')
  const [userPromptRendered, setUserPromptRendered] = useState('')

  // Fetch available templates (for system prompt only) - cache indefinitely
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['prompt-templates', promptType],
    queryFn: () => api.getPromptTemplates(promptType),
    enabled: isOpen,
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60, // Keep in cache for 1 hour
  })

  // Fetch default template name - cache indefinitely
  const { data: defaultData } = useQuery({
    queryKey: ['prompt-default', promptType],
    queryFn: () => api.getDefaultTemplate(promptType),
    enabled: isOpen,
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60,
  })

  // Fetch project-resolved prompts (for user prompt) - cache for 10 minutes
  const { data: projectPromptsData, isLoading: projectPromptsLoading } = useQuery({
    queryKey: ['project-resolved-prompts', projectId, promptType],
    queryFn: () => api.getProjectResolvedPrompts(projectId!, promptType),
    enabled: isOpen && !!projectId,
    staleTime: 1000 * 60 * 10, // 10 minutes - project prompts may change
    gcTime: 1000 * 60 * 30,
  })

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: (params: { systemPrompt: string; userPrompt: string }) =>
      api.previewPrompt(promptType, variables, params.systemPrompt, params.userPrompt),
    onSuccess: (data) => {
      setSystemPromptRendered(data.system_prompt)
      setUserPromptRendered(data.user_prompt)
    },
  })

  // Build template options (for system prompt only)
  const templateOptions: TemplateOption[] = (templatesData || []).map(t => ({
    name: t.template_name,
    displayName: t.display_name,
    systemPrompt: t.system_prompt,
    userPrompt: t.user_prompt,
  }))

  const defaultTemplateName = defaultData?.template_name || 'default'

  // Initialize when modal opens and data is ready
  useEffect(() => {
    if (!isOpen || templateOptions.length === 0) return

    // Find default template for system prompt
    const defaultTemplate = templateOptions.find(t => t.name === defaultTemplateName) || templateOptions[0]
    if (!defaultTemplate) return

    // Initialize system prompt from template
    setSystemTemplateName(defaultTemplate.name)
    setSystemPromptOriginal(defaultTemplate.systemPrompt)
    setSystemPromptEdited(defaultTemplate.systemPrompt)

    // Initialize user prompt from project-resolved prompts (if available) or default template
    const userPrompt = projectPromptsData?.user_prompt || defaultTemplate.userPrompt
    setUserPromptOriginal(userPrompt)
    setUserPromptEdited(userPrompt)

    // Trigger initial preview
    previewMutation.mutate({
      systemPrompt: defaultTemplate.systemPrompt,
      userPrompt: userPrompt,
    })
  }, [isOpen, templateOptions.length, defaultTemplateName, projectPromptsData])

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setActiveTab('system')
      setSystemTemplateName('default')
      setSystemPromptOriginal('')
      setSystemPromptEdited('')
      setSystemPromptRendered('')
      setUserPromptOriginal('')
      setUserPromptEdited('')
      setUserPromptRendered('')
    }
  }, [isOpen])

  // Handle system template selection
  const handleSystemTemplateSelect = useCallback((name: string) => {
    const template = templateOptions.find(t => t.name === name)
    if (!template) return

    setSystemTemplateName(name)
    setSystemPromptOriginal(template.systemPrompt)
    setSystemPromptEdited(template.systemPrompt)

    previewMutation.mutate({
      systemPrompt: template.systemPrompt,
      userPrompt: userPromptEdited,
    })
  }, [templateOptions, userPromptEdited, previewMutation])

  // Handle system prompt edit
  const handleSystemPromptChange = useCallback((value: string) => {
    setSystemPromptEdited(value)
  }, [])

  // Handle user prompt edit
  const handleUserPromptChange = useCallback((value: string) => {
    setUserPromptEdited(value)
  }, [])

  // Reset system prompt to original
  const handleResetSystemPrompt = useCallback(() => {
    setSystemPromptEdited(systemPromptOriginal)
    previewMutation.mutate({
      systemPrompt: systemPromptOriginal,
      userPrompt: userPromptEdited,
    })
  }, [systemPromptOriginal, userPromptEdited, previewMutation])

  // Reset user prompt to original
  const handleResetUserPrompt = useCallback(() => {
    setUserPromptEdited(userPromptOriginal)
    previewMutation.mutate({
      systemPrompt: systemPromptEdited,
      userPrompt: userPromptOriginal,
    })
  }, [userPromptOriginal, systemPromptEdited, previewMutation])

  // Refresh preview
  const handleRefreshPreview = useCallback(() => {
    previewMutation.mutate({
      systemPrompt: systemPromptEdited,
      userPrompt: userPromptEdited,
    })
  }, [systemPromptEdited, userPromptEdited, previewMutation])

  // Handle confirm
  const handleConfirm = useCallback(() => {
    // Send the edited templates (not rendered) so backend can substitute per-item content
    // The preview shows what the final prompt looks like, but we need the templates
    // for backend to substitute actual paragraph content (content.source, content.target, etc.)
    onConfirm(systemPromptEdited, userPromptEdited)
  }, [systemPromptEdited, userPromptEdited, onConfirm])

  // Computed state
  const isSystemEdited = systemPromptEdited !== systemPromptOriginal
  const isUserEdited = userPromptEdited !== userPromptOriginal
  const isDataLoading = templatesLoading || projectPromptsLoading || templateOptions.length === 0

  if (!isOpen) return null

  // Current tab data
  const currentPromptEdited = activeTab === 'system' ? systemPromptEdited : userPromptEdited
  const currentPromptRendered = activeTab === 'system' ? systemPromptRendered : userPromptRendered
  const currentIsEdited = activeTab === 'system' ? isSystemEdited : isUserEdited
  const handlePromptChange = activeTab === 'system' ? handleSystemPromptChange : handleUserPromptChange
  const handleReset = activeTab === 'system' ? handleResetSystemPrompt : handleResetUserPrompt

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {title || t('prompts.title')}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t(`promptManagement.categories.${promptType}`)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-6">
          <button
            type="button"
            onClick={() => setActiveTab('system')}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === 'system'
                ? 'text-blue-600 border-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'text-gray-500 border-transparent hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            <FileText className="w-4 h-4" />
            {t('prompts.systemPrompt')}
            {isSystemEdited && <span className="w-2 h-2 rounded-full bg-amber-500" />}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('user')}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === 'user'
                ? 'text-blue-600 border-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'text-gray-500 border-transparent hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            <Code className="w-4 h-4" />
            {t('prompts.userPrompt')}
            {isUserEdited && <span className="w-2 h-2 rounded-full bg-amber-500" />}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {isDataLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                <span className="text-sm text-gray-500">{t('prompts.loading')}</span>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Template Selector - Only for System Prompt */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {activeTab === 'system' && (
                    <>
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {t('prompts.selectTemplate')}
                      </label>
                      <TemplateDropdown
                        options={templateOptions}
                        selectedName={systemTemplateName}
                        defaultName={defaultTemplateName}
                        onSelect={handleSystemTemplateSelect}
                      />
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {currentIsEdited && (
                    <>
                      <span className="text-xs text-amber-600 dark:text-amber-400 px-2 py-1 rounded bg-amber-50 dark:bg-amber-900/20">
                        {t('prompts.modified')}
                      </span>
                      <button
                        type="button"
                        onClick={handleReset}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 px-2 py-1"
                      >
                        <RotateCcw className="w-3 h-3" />
                        {t('prompts.reset')}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Editor */}
              <div>
                <textarea
                  value={currentPromptEdited}
                  onChange={(e) => handlePromptChange(e.target.value)}
                  className="w-full h-48 px-4 py-3 border rounded-lg bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 font-mono text-sm resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  placeholder={activeTab === 'system' ? t('prompts.systemPromptPlaceholder') : t('prompts.userPromptPlaceholder')}
                />
              </div>

              {/* Rendered Preview */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t('prompts.renderedPreview')}
                  </label>
                  <button
                    type="button"
                    onClick={handleRefreshPreview}
                    disabled={previewMutation.isPending}
                    className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${previewMutation.isPending ? 'animate-spin' : ''}`} />
                    {t('prompts.refreshPreview')}
                  </button>
                </div>
                <div className={`p-4 border rounded-lg max-h-40 overflow-auto ${
                  activeTab === 'system'
                    ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'
                    : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                }`}>
                  {previewMutation.isPending ? (
                    <div className="flex items-center gap-2 text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-sm">{t('prompts.loading')}</span>
                    </div>
                  ) : previewMutation.isError ? (
                    <div className="text-red-600 dark:text-red-400 text-sm">
                      {String(previewMutation.error)}
                    </div>
                  ) : currentPromptRendered ? (
                    <pre className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                      {currentPromptRendered}
                    </pre>
                  ) : (
                    <span className="text-sm text-gray-500">{t('prompts.clickRefresh')}</span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            {isSystemEdited && (
              <span className="flex items-center gap-1 px-2 py-1 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                <FileText className="w-3 h-3" />
                {t('prompts.systemModified')}
              </span>
            )}
            {isUserEdited && (
              <span className="flex items-center gap-1 px-2 py-1 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                <Code className="w-3 h-3" />
                {t('prompts.userModified')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isDataLoading || isLoading || !systemPromptRendered || !userPromptRendered}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
