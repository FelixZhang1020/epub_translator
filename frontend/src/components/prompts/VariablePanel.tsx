/**
 * VariablePanel - displays available template variables with insertion support
 */

import { useState } from 'react'
import {
  BookOpen,
  FileText,
  GitBranch,
  Sparkles,
  User,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Info,
  AlertCircle,
  Search,
} from 'lucide-react'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import {
  VARIABLE_REGISTRY,
  getVariablesByCategory,
  validateTemplateVariables,
  type PromptStage,
  type VariableCategoryInfo,
  type VariableDefinition,
} from '../../data/variableRegistry'

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  BookOpen,
  FileText,
  GitBranch,
  Sparkles,
  User,
}

interface VariablePanelProps {
  /** Current prompt stage to filter available variables */
  stage: PromptStage
  /** Callback when a variable is clicked for insertion */
  onInsert?: (variableRef: string) => void
  /** Current template content for validation */
  templateContent?: string
  /** Show compact mode (less details) */
  compact?: boolean
}

export function VariablePanel({
  stage,
  onInsert,
  templateContent,
  compact = false,
}: VariablePanelProps) {
  const { t, language } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(VARIABLE_REGISTRY.map((c) => c.id))
  )
  const [searchQuery, setSearchQuery] = useState('')
  const [copiedVar, setCopiedVar] = useState<string | null>(null)

  // Get variables filtered by stage
  const categories = getVariablesByCategory(stage)

  // Validate current template if provided
  const validation = templateContent
    ? validateTemplateVariables(templateContent, stage)
    : null

  // Filter by search query
  const filteredCategories = categories
    .map((category) => ({
      ...category,
      variables: category.variables.filter((v) => {
        if (!searchQuery) return true
        const query = searchQuery.toLowerCase()
        return (
          v.name.toLowerCase().includes(query) ||
          v.fullName.toLowerCase().includes(query) ||
          v.description.toLowerCase().includes(query) ||
          v.descriptionZh.includes(query)
        )
      }),
    }))
    .filter((category) => category.variables.length > 0)

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(categoryId)) {
        next.delete(categoryId)
      } else {
        next.add(categoryId)
      }
      return next
    })
  }

  const handleInsert = (variable: VariableDefinition) => {
    const ref = `{{${variable.fullName}}}`
    if (onInsert) {
      onInsert(ref)
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(ref)
      setCopiedVar(variable.fullName)
      setTimeout(() => setCopiedVar(null), 2000)
    }
  }

  const handleCopy = (variable: VariableDefinition) => {
    const ref = `{{${variable.fullName}}}`
    navigator.clipboard.writeText(ref)
    setCopiedVar(variable.fullName)
    setTimeout(() => setCopiedVar(null), 2000)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className={`${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300`}>
          {t('promptManagement.availableVariables')}
        </h3>
        <span className={`${fontClasses.xs} text-gray-400`}>
          {t(`promptManagement.categories.${stage}`)}
        </span>
      </div>

      {/* Search */}
      <div className="relative mb-3">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={t('promptManagement.searchVariables')}
          className={`w-full pl-8 pr-3 py-1.5 ${fontClasses.sm} border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500`}
        />
      </div>

      {/* Validation Summary */}
      {validation && (validation.invalid.length > 0 || validation.warnings.length > 0) && (
        <div className="mb-3 space-y-1">
          {validation.invalid.length > 0 && (
            <div className={`flex items-center gap-1.5 ${fontClasses.xs} text-red-600 dark:text-red-400`}>
              <AlertCircle className="w-3.5 h-3.5" />
              <span>
                {t('promptManagement.undefinedVariables')}: {validation.invalid.join(', ')}
              </span>
            </div>
          )}
          {validation.warnings.length > 0 && (
            <div className={`flex items-center gap-1.5 ${fontClasses.xs} text-amber-600 dark:text-amber-400`}>
              <Info className="w-3.5 h-3.5" />
              <span>
                {t('promptManagement.stageUnavailable')}: {validation.warnings.join(', ')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Variable List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {filteredCategories.map((category) => (
          <CategorySection
            key={category.id}
            category={category}
            expanded={expandedCategories.has(category.id)}
            onToggle={() => toggleCategory(category.id)}
            onInsert={handleInsert}
            onCopy={handleCopy}
            copiedVar={copiedVar}
            compact={compact}
            language={language}
            fontClasses={fontClasses}
            usedVars={validation?.valid || []}
          />
        ))}

        {filteredCategories.length === 0 && (
          <div className={`text-center py-4 ${fontClasses.sm} text-gray-400`}>
            {searchQuery
              ? t('promptManagement.noVariablesFound')
              : t('promptManagement.noVariablesForStage')}
          </div>
        )}
      </div>

      {/* Help Text */}
      <div className={`mt-3 pt-3 border-t border-gray-200 dark:border-gray-600 ${fontClasses.xs} text-gray-400`}>
        <p>{t('promptManagement.variableHelpText')}</p>
      </div>
    </div>
  )
}

interface CategorySectionProps {
  category: VariableCategoryInfo
  expanded: boolean
  onToggle: () => void
  onInsert: (variable: VariableDefinition) => void
  onCopy: (variable: VariableDefinition) => void
  copiedVar: string | null
  compact: boolean
  language: string
  fontClasses: typeof fontSizeClasses.medium
  usedVars: string[]
}

function CategorySection({
  category,
  expanded,
  onToggle,
  onInsert,
  onCopy,
  copiedVar,
  compact,
  language,
  fontClasses,
  usedVars,
}: CategorySectionProps) {
  const Icon = CATEGORY_ICONS[category.icon] || FileText

  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
      {/* Category Header */}
      <button
        onClick={onToggle}
        className="flex items-center gap-2 w-full px-3 py-2 bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
        <Icon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
        <span className={`${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300`}>
          {language === 'zh' ? category.labelZh : category.label}
        </span>
        <span className={`${fontClasses.xs} text-gray-400`}>
          ({category.variables.length})
        </span>
      </button>

      {/* Variables List */}
      {expanded && (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {category.variables.map((variable) => (
            <VariableItem
              key={variable.fullName}
              variable={variable}
              onInsert={() => onInsert(variable)}
              onCopy={() => onCopy(variable)}
              copied={copiedVar === variable.fullName}
              compact={compact}
              language={language}
              fontClasses={fontClasses}
              isUsed={usedVars.includes(variable.fullName) || usedVars.includes(variable.name)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface VariableItemProps {
  variable: VariableDefinition
  onInsert: () => void
  onCopy: () => void
  copied: boolean
  compact: boolean
  language: string
  fontClasses: typeof fontSizeClasses.medium
  isUsed: boolean
}

function VariableItem({
  variable,
  onInsert,
  onCopy,
  copied,
  compact,
  language,
  fontClasses,
  isUsed,
}: VariableItemProps) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <div
      className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors ${
        isUsed ? 'bg-green-50/50 dark:bg-green-900/10' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        {/* Variable Name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <button
              onClick={onInsert}
              className={`${fontClasses.sm} font-mono text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline truncate`}
              title={`{{${variable.fullName}}}`}
            >
              {`{{${variable.fullName}}}`}
            </button>
            {variable.required && (
              <span className={`${fontClasses.xs} text-red-500`}>*</span>
            )}
            {isUsed && (
              <Check className="w-3.5 h-3.5 text-green-500" />
            )}
          </div>
          {!compact && (
            <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 truncate mt-0.5`}>
              {language === 'zh' ? variable.descriptionZh : variable.description}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Details"
          >
            <Info className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onCopy}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Copy"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-500" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Details Panel */}
      {showDetails && (
        <div className={`mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded ${fontClasses.xs}`}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Type:</span>
              <span className="ml-1 text-gray-700 dark:text-gray-300 font-mono">
                {variable.type}
              </span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Source:</span>
              <span className="ml-1 text-gray-700 dark:text-gray-300 font-mono">
                {variable.source}
              </span>
            </div>
          </div>
          {variable.example && (
            <div className="mt-1">
              <span className="text-gray-500 dark:text-gray-400">Example:</span>
              <code className="ml-1 text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 px-1 rounded">
                {variable.example.length > 60
                  ? variable.example.substring(0, 60) + '...'
                  : variable.example}
              </code>
            </div>
          )}
          {variable.structure && (
            <div className="mt-1">
              <span className="text-gray-500 dark:text-gray-400">Structure:</span>
              <span className="ml-1 text-gray-700 dark:text-gray-300">
                {variable.structure}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Compact variable badge for inline display
 */
export function VariableBadge({
  variable,
  onClick,
}: {
  variable: VariableDefinition
  onClick?: () => void
}) {
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 px-2 py-0.5 ${fontClasses.xs} font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors`}
    >
      {`{{${variable.name}}}`}
    </button>
  )
}
