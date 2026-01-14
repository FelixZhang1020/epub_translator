import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronDown,
  Star,
  Check,
  FileText,
  Loader2,
} from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'
import { PromptPreviewModal } from './PromptPreviewModal'

// =============================================================================
// Types
// =============================================================================

export interface PromptTemplateSelectorProps {
  promptType: 'analysis' | 'translation' | 'proofreading' | 'optimization'
  projectId?: string
  variables: Record<string, unknown>
  disabled?: boolean
  /** Callback when template selection changes */
  onTemplateChange?: (templateName: string) => void
  /** Callback when user confirms prompts from the preview modal */
  onConfirm?: (systemPrompt?: string, userPrompt?: string) => void
  /** Whether a task is loading/running */
  isLoading?: boolean
  /** Current selected template name (controlled mode) */
  selectedTemplate?: string
  /** Compact mode - smaller width */
  compact?: boolean
}

interface TemplateOption {
  name: string
  displayName: string
  systemPrompt: string
  userPrompt: string
}

// =============================================================================
// Main Component
// =============================================================================

export function PromptTemplateSelector({
  promptType,
  projectId,
  variables,
  disabled = false,
  onTemplateChange,
  onConfirm,
  isLoading = false,
  selectedTemplate: controlledSelected,
  compact = false,
}: PromptTemplateSelectorProps) {
  const { t } = useTranslation()
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [internalSelected, setInternalSelected] = useState<string>('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Use controlled or internal state
  const selectedName = controlledSelected ?? internalSelected

  // Fetch available templates - cache indefinitely since templates rarely change
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['prompt-templates', promptType],
    queryFn: () => api.getPromptTemplates(promptType),
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60, // Keep in cache for 1 hour
  })

  // Fetch default template name - cache indefinitely
  const { data: defaultData } = useQuery({
    queryKey: ['prompt-default', promptType],
    queryFn: () => api.getDefaultTemplate(promptType),
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60,
  })

  const defaultTemplateName = defaultData?.template_name || 'default'

  // Build template options
  const templateOptions: TemplateOption[] = (templatesData || []).map(t => ({
    name: t.template_name,
    displayName: t.display_name,
    systemPrompt: t.system_prompt,
    userPrompt: t.user_prompt,
  }))

  // Initialize with default template (the starred one from defaults.json)
  useEffect(() => {
    if (!controlledSelected && templateOptions.length > 0 && !internalSelected) {
      // Always use the default template from defaults.json
      const defaultTemplate = templateOptions.find(t => t.name === defaultTemplateName)
      if (defaultTemplate) {
        setInternalSelected(defaultTemplate.name)
        onTemplateChange?.(defaultTemplate.name)
      }
    }
  }, [templateOptions, defaultTemplateName, controlledSelected, internalSelected, onTemplateChange])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle template selection
  const handleSelect = useCallback((name: string) => {
    if (!controlledSelected) {
      setInternalSelected(name)
    }
    onTemplateChange?.(name)
    setIsDropdownOpen(false)
  }, [controlledSelected, onTemplateChange])

  // Handle modal confirm
  const handleModalConfirm = useCallback((systemPrompt?: string, userPrompt?: string) => {
    setIsModalOpen(false)
    onConfirm?.(systemPrompt, userPrompt)
  }, [onConfirm])

  // Handle click on the view/edit icon
  const handleViewClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation() // Prevent dropdown from opening
    setIsModalOpen(true)
  }, [])

  const selected = templateOptions.find(o => o.name === selectedName)
  const isSelectedDefault = selectedName === defaultTemplateName
  const isReady = !templatesLoading && templateOptions.length > 0

  // Get display name - prefer the actual selected template's display name
  const displayName = selected?.displayName || t('prompts.selectTemplate')

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Integrated Button: Dropdown + View Icon */}
      <div className={`flex items-center border rounded-lg bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 ${
        disabled || !isReady ? 'opacity-50 cursor-not-allowed' : ''
      }`}>
        {/* Main dropdown trigger */}
        <button
          type="button"
          onClick={() => !disabled && isReady && setIsDropdownOpen(!isDropdownOpen)}
          disabled={disabled || !isReady}
          className={`flex items-center gap-2 px-3 py-1.5 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:cursor-not-allowed transition-colors text-sm rounded-l-lg ${
            compact ? 'min-w-[120px]' : 'min-w-[150px]'
          }`}
        >
          {templatesLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <>
              {isSelectedDefault && (
                <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500 flex-shrink-0" />
              )}
              <span className="truncate flex-1 text-left">
                {displayName}
              </span>
              <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </>
          )}
        </button>

        {/* Divider */}
        <div className="w-px h-6 bg-gray-300 dark:bg-gray-600" />

        {/* View/Edit button */}
        <button
          type="button"
          onClick={handleViewClick}
          disabled={disabled || !isReady}
          className="px-2 py-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300 disabled:cursor-not-allowed transition-colors rounded-r-lg"
          title={t('prompts.viewPrompt')}
        >
          <FileText className="w-4 h-4" />
        </button>
      </div>

      {/* Dropdown Menu */}
      {isDropdownOpen && (
        <div className="absolute top-full left-0 mt-1 w-full min-w-[200px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl z-50 max-h-64 overflow-auto">
          {templateOptions.map((option) => {
            const isOptionDefault = option.name === defaultTemplateName
            const isSelected = option.name === selectedName

            return (
              <button
                key={option.name}
                type="button"
                onClick={() => handleSelect(option.name)}
                className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-900 dark:text-gray-100 text-sm transition-colors ${
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

      {/* Prompt Preview Modal */}
      <PromptPreviewModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleModalConfirm}
        promptType={promptType}
        projectId={projectId}
        variables={variables}
        isLoading={isLoading}
      />
    </div>
  )
}

export default PromptTemplateSelector
