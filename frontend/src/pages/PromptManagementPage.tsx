import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Trash2,
  Edit3,
  X,
  Save,
  Lock,
  Star,
  RefreshCw,
  FileText,
  ChevronDown,
  ChevronRight,
  BookOpen,
  Languages,
  Sparkles,
  FileCheck,
  PanelRightOpen,
  PanelRightClose,
  Variable,
  Code,
  Check,
} from 'lucide-react'
import { api, PromptTemplateDB, Project, ProjectVariable, CreateProjectVariableRequest, UpdateProjectVariableRequest } from '../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../stores/appStore'
import { VariablePanel } from '../components/prompts/VariablePanel'
import type { PromptStage } from '../data/variableRegistry'
import { safeTruncate } from '../utils/text'

type PromptCategory = 'analysis' | 'translation' | 'optimization' | 'proofreading'

const CATEGORIES: PromptCategory[] = ['analysis', 'translation', 'optimization', 'proofreading']

const CATEGORY_ICONS: Record<PromptCategory, React.ComponentType<{ className?: string }>> = {
  analysis: BookOpen,
  translation: Languages,
  optimization: Sparkles,
  proofreading: FileCheck,
}

// Template Editor Modal
function TemplateEditor({
  template,
  onSave,
  onCancel,
  isNew = false,
}: {
  template: Partial<PromptTemplateDB>
  onSave: (data: {
    name: string
    display_name: string
    category: string
    template_name: string
    system_prompt: string
  }) => void
  onCancel: () => void
  isNew?: boolean
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [displayName, setDisplayName] = useState(template.display_name || '')
  const [category, setCategory] = useState<PromptCategory>(
    (template.category as PromptCategory) || 'translation'
  )
  const [templateName, setTemplateName] = useState(template.template_name || '')
  const [systemPrompt, setSystemPrompt] = useState(template.system_prompt || '')
  const [showVariablePanel, setShowVariablePanel] = useState(true)

  // Ref for textarea to support cursor position insertion
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSave = () => {
    if (!displayName.trim() || !systemPrompt.trim()) return
    // For new templates, require template_name
    if (isNew && !templateName.trim()) return
    // For existing non-default templates, allow renaming
    const finalTemplateName = isNew ? templateName.trim() : templateName.trim() || template.template_name || ''
    onSave({
      name: displayName.trim(),
      display_name: displayName.trim(),
      category,
      template_name: finalTemplateName,
      system_prompt: systemPrompt,
    })
  }

  // Handle variable insertion at cursor position
  const handleInsertVariable = (variableRef: string) => {
    const textarea = textareaRef.current
    if (!textarea) {
      // Fallback: append to end
      setSystemPrompt((prev) => prev + variableRef)
      return
    }

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const newValue =
      systemPrompt.substring(0, start) + variableRef + systemPrompt.substring(end)

    setSystemPrompt(newValue)

    // Set cursor position after inserted text
    const newCursorPos = start + variableRef.length

    // Focus and set cursor position after state update
    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(newCursorPos, newCursorPos)
    }, 0)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>
            {isNew ? t('promptManagement.addTemplate') : t('promptManagement.editTemplate')}
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowVariablePanel(!showVariablePanel)}
              className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
              title={showVariablePanel ? 'Hide variables' : 'Show variables'}
            >
              {showVariablePanel ? (
                <PanelRightClose className="w-5 h-5" />
              ) : (
                <PanelRightOpen className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={onCancel}
              className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Form with Variable Panel */}
        <div className="flex-1 overflow-hidden flex">
          {/* Main Form */}
          <div className={`flex-1 overflow-y-auto p-4 space-y-4 ${showVariablePanel ? 'border-r border-gray-200 dark:border-gray-700' : ''}`}>
            {/* Name and Category Row */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                  {t('promptManagement.displayName')}
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t('promptManagement.displayNamePlaceholder')}
                  disabled={!isNew && template.template_name === 'default'}
                  className={`w-full px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100 dark:disabled:bg-gray-600`}
                />
              </div>
              <div>
                <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                  {t('promptManagement.category')}
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as PromptCategory)}
                  disabled={!isNew && template.template_name === 'default'}
                  className={`w-full px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100 dark:disabled:bg-gray-600`}
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {t(`promptManagement.categories.${cat}`)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* File Name - editable for new templates and non-default existing templates */}
            {(isNew || template.template_name !== 'default') && (
              <div>
                <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                  {t('promptManagement.fileName')}
                  {isNew && <span className="text-red-500 ml-1">*</span>}
                </label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  placeholder="my-template-name"
                  disabled={template.template_name === 'default'}
                  className={`w-full px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100 dark:disabled:bg-gray-600`}
                />
                <p className={`mt-1 ${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                  {t('promptManagement.fileNameHint')}
                </p>
              </div>
            )}

            {/* System Prompt */}
            <div className="flex-1">
              <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                {t('prompts.systemPrompt')}
              </label>
              <textarea
                ref={textareaRef}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder={t('prompts.systemPromptPlaceholder')}
                rows={12}
                className={`w-full px-3 py-2 ${fontClasses.sm} font-mono border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none`}
              />
            </div>

          </div>

          {/* Variable Panel */}
          {showVariablePanel && (
            <div className="w-80 flex-shrink-0 p-4 overflow-y-auto bg-gray-50 dark:bg-gray-900/50">
              <VariablePanel
                stage={category as PromptStage}
                onInsert={handleInsertVariable}
                templateContent={systemPrompt}
                compact={false}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onCancel}
            className={`px-4 py-2 ${fontClasses.sm} text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors`}
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={!displayName.trim() || !systemPrompt.trim()}
            className={`flex items-center gap-2 px-4 py-2 ${fontClasses.sm} bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
          >
            <Save className="w-4 h-4" />
            {t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

// Template Card Component
function TemplateCard({
  template,
  isDefault,
  onEdit,
  onDelete,
  onSetDefault,
}: {
  template: PromptTemplateDB
  isDefault: boolean
  onEdit: () => void
  onDelete: () => void
  onSetDefault: () => void
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const [expanded, setExpanded] = useState(false)

  const CategoryIcon = CATEGORY_ICONS[template.category as PromptCategory] || FileText
  const isBuiltin = template.template_name === 'default'

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <CategoryIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          <div>
            <div className="flex items-center gap-2">
              <span className={`${fontClasses.base} font-medium text-gray-900 dark:text-white`}>
                {template.display_name}
              </span>
              {isDefault && (
                <span title={t('prompts.defaultTemplate')}>
                  <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                </span>
              )}
              {isBuiltin && (
                <span title={t('prompts.builtinTemplate')}>
                  <Lock className="w-4 h-4 text-gray-400" />
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                {t(`promptManagement.categories.${template.category}`)}
              </span>
              <span className={`${fontClasses.xs} text-gray-400`}>•</span>
              <code className={`${fontClasses.xs} font-mono text-gray-400 dark:text-gray-500`}>
                {template.template_name}.md
              </code>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Set as default button - only show if not already default */}
          {!isDefault && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onSetDefault()
              }}
              className="p-1.5 text-gray-400 hover:text-amber-500 dark:text-gray-500 dark:hover:text-amber-400 transition-colors"
              title={t('promptManagement.setAsDefault')}
            >
              <Star className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit()
            }}
            className="p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 transition-colors"
          >
            <Edit3 className="w-4 h-4" />
          </button>
          {!isBuiltin && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              className="p-1.5 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {expanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-3 space-y-3">
          {/* File Name */}
          <div className="flex items-center gap-2">
            <label className={`${fontClasses.xs} font-medium text-gray-500 dark:text-gray-400`}>
              {t('promptManagement.fileName')}:
            </label>
            <code className={`${fontClasses.xs} font-mono px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded`}>
              system.{template.template_name}.md
            </code>
          </div>
          {/* System Prompt */}
          <div>
            <label className={`block ${fontClasses.xs} font-medium text-gray-500 dark:text-gray-400 mb-1`}>
              {t('prompts.systemPrompt')}
            </label>
            <pre className={`${fontClasses.xs} font-mono bg-gray-50 dark:bg-gray-900 p-3 rounded-md text-gray-800 dark:text-gray-200 whitespace-pre-wrap max-h-64 overflow-y-auto`}>
              {template.system_prompt}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

// Category Section
function CategorySection({
  category,
  templates,
  defaultTemplate,
  onEdit,
  onDelete,
  onSetDefault,
}: {
  category: PromptCategory
  templates: PromptTemplateDB[]
  defaultTemplate: string
  onEdit: (template: PromptTemplateDB) => void
  onDelete: (template: PromptTemplateDB) => void
  onSetDefault: (template: PromptTemplateDB) => void
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const [collapsed, setCollapsed] = useState(false)

  const CategoryIcon = CATEGORY_ICONS[category]
  const categoryTemplates = templates.filter((t) => t.category === category)

  if (categoryTemplates.length === 0) return null

  return (
    <div className="space-y-2">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 w-full text-left"
      >
        {collapsed ? (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
        <CategoryIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
        <span className={`${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300`}>
          {t(`promptManagement.categories.${category}`)}
        </span>
        <span className={`${fontClasses.xs} text-gray-400`}>({categoryTemplates.length})</span>
      </button>

      {!collapsed && (
        <div className="pl-6 space-y-2">
          {categoryTemplates.map((template) => (
            <TemplateCard
              key={`${template.category}-${template.template_name}`}
              template={template}
              isDefault={template.template_name === defaultTemplate}
              onEdit={() => onEdit(template)}
              onDelete={() => onDelete(template)}
              onSetDefault={() => onSetDefault(template)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// Project Selector
function ProjectSelector({
  projects,
  selectedProjectId,
  onSelect,
}: {
  projects: Project[]
  selectedProjectId: string | null
  onSelect: (projectId: string | null) => void
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedProject = projects.find((p) => p.id === selectedProjectId)
  const displayName = selectedProject
    ? `${selectedProject.name}${selectedProject.author ? ` (${selectedProject.author})` : ''}`
    : t('promptManagement.selectProject')

  return (
    <div>
      <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-2`}>
        {t('promptManagement.selectProject')}
      </label>
      <div className="relative w-full max-w-md" ref={dropdownRef}>
        {/* Trigger button */}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className={`w-full flex items-center gap-2 px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors`}
        >
          {selectedProject?.is_favorite && (
            <Star className="w-4 h-4 text-amber-500 fill-amber-500 flex-shrink-0" />
          )}
          <span className="flex-1 text-left truncate">{displayName}</span>
          <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {/* Dropdown menu */}
        {isOpen && (
          <div className="absolute top-full left-0 mt-1 w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50 py-1 max-h-64 overflow-y-auto">
            {projects.map((project) => {
              const isSelected = project.id === selectedProjectId
              const projectDisplayName = `${project.name}${project.author ? ` (${project.author})` : ''}`

              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => {
                    onSelect(project.id)
                    setIsOpen(false)
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 ${fontClasses.base} ${
                    isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                  }`}
                >
                  <div className="w-5 flex-shrink-0">
                    {project.is_favorite && (
                      <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                    )}
                  </div>
                  <span className="flex-1 text-gray-900 dark:text-gray-100 truncate">
                    {projectDisplayName}
                  </span>
                  {isSelected && (
                    <Check className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export function PromptManagementPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [editingTemplate, setEditingTemplate] = useState<PromptTemplateDB | null>(null)
  const [isAddingTemplate, setIsAddingTemplate] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)

  // Fetch templates (directly from filesystem via API)
  const { data: templates = [], isLoading: templatesLoading } = useQuery({
    queryKey: ['promptTemplates'],
    queryFn: () => api.getPromptTemplates(),
  })

  // Fetch default templates configuration
  const { data: defaultsData } = useQuery({
    queryKey: ['promptDefaults'],
    queryFn: () => api.getDefaultTemplates(),
  })
  const defaults = defaultsData?.defaults || {}

  // Fetch projects for project selector
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })

  // Auto-select first favorite project when projects load
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      // Projects are sorted by is_favorite desc, so first favorite is at the start
      const favoriteProject = projects.find((p) => p.is_favorite)
      if (favoriteProject) {
        setSelectedProjectId(favoriteProject.id)
      }
    }
  }, [projects, selectedProjectId])

  // Create template mutation
  const createMutation = useMutation({
    mutationFn: api.createPromptTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] })
      setIsAddingTemplate(false)
    },
  })

  // Update template mutation
  const updateMutation = useMutation({
    mutationFn: ({ category, templateName, data }: { category: string; templateName: string; data: Parameters<typeof api.updatePromptTemplate>[2] }) =>
      api.updatePromptTemplate(category, templateName, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] })
      setEditingTemplate(null)
    },
  })

  // Delete template mutation
  const deleteMutation = useMutation({
    mutationFn: ({ category, templateName }: { category: string; templateName: string }) =>
      api.deletePromptTemplate(category, templateName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] })
    },
  })

  // Set default template mutation
  const setDefaultMutation = useMutation({
    mutationFn: ({ category, templateName }: { category: string; templateName: string }) =>
      api.setDefaultTemplate(category, templateName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptDefaults'] })
    },
  })

  const handleDeleteTemplate = (template: PromptTemplateDB) => {
    // Cannot delete builtin templates
    if (template.template_name === 'default') {
      alert(t('promptManagement.cannotDeleteBuiltin'))
      return
    }
    if (confirm(t('promptManagement.confirmDelete'))) {
      deleteMutation.mutate({ category: template.category, templateName: template.template_name })
    }
  }

  const handleSetDefault = (template: PromptTemplateDB) => {
    setDefaultMutation.mutate({ category: template.category, templateName: template.template_name })
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`${fontClasses.title} font-bold text-gray-900 dark:text-white`}>
            {t('promptManagement.title')}
          </h1>
          <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400 mt-1`}>
            {t('promptManagement.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsAddingTemplate(true)}
            className={`flex items-center gap-2 px-4 py-2 ${fontClasses.sm} bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors`}
          >
            <Plus className="w-4 h-4" />
            {t('promptManagement.addTemplate')}
          </button>
        </div>
      </div>

      {/* Global Templates Section */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="mb-4">
          <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>
            {t('promptManagement.globalTemplates')}
          </h2>
          <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400 mt-1`}>
            {t('promptManagement.globalTemplatesDesc')}
          </p>
        </div>

        {templatesLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" />
            <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
              {t('promptManagement.noTemplates')}
            </p>
            <button
              onClick={() => setIsAddingTemplate(true)}
              className={`mt-3 ${fontClasses.sm} text-blue-600 dark:text-blue-400 hover:underline`}
            >
              {t('promptManagement.addFirstTemplate')}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {CATEGORIES.map((category) => (
              <CategorySection
                key={category}
                category={category}
                templates={templates}
                defaultTemplate={defaults[category] || 'default'}
                onEdit={setEditingTemplate}
                onDelete={handleDeleteTemplate}
                onSetDefault={handleSetDefault}
              />
            ))}
          </div>
        )}
      </section>

      {/* Project-Specific Prompts Section */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="mb-4">
          <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>
            {t('promptManagement.projectPrompts')}
          </h2>
          <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400 mt-1`}>
            {t('promptManagement.projectPromptsDesc')}
          </p>
        </div>

        <ProjectSelector
          projects={projects}
          selectedProjectId={selectedProjectId}
          onSelect={setSelectedProjectId}
        />

        {!selectedProjectId && (
          <div className="text-center py-8 mt-4">
            <BookOpen className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" />
            <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
              {t('promptManagement.noProjectSelected')}
            </p>
          </div>
        )}

        {selectedProjectId && (
          <>
            <ProjectPromptConfigs projectId={selectedProjectId} />
            <ProjectVariablesManager projectId={selectedProjectId} />
          </>
        )}
      </section>

      {/* Template Editor Modal */}
      {(isAddingTemplate || editingTemplate) && (
        <TemplateEditor
          template={editingTemplate || {}}
          isNew={isAddingTemplate}
          onSave={async (data) => {
            if (editingTemplate) {
              const originalName = editingTemplate.template_name
              const newName = data.template_name

              // Check if template name changed (rename)
              if (newName && newName !== originalName && originalName !== 'default') {
                try {
                  // First rename the template
                  await api.renamePromptTemplate(editingTemplate.category, originalName, newName)
                  // Then update the content and display name with the new name
                  await api.updatePromptTemplate(editingTemplate.category, newName, {
                    system_prompt: data.system_prompt,
                    display_name: data.display_name
                  })
                  queryClient.invalidateQueries({ queryKey: ['promptTemplates'] })
                  setEditingTemplate(null)
                } catch (error) {
                  console.error('Failed to rename template:', error)
                  alert('Failed to rename template. The name may already exist or be invalid.')
                }
              } else {
                // Just update content and display name
                updateMutation.mutate({
                  category: editingTemplate.category,
                  templateName: originalName,
                  data: {
                    system_prompt: data.system_prompt,
                    display_name: data.display_name
                  }
                })
              }
            } else {
              createMutation.mutate(data)
            }
          }}
          onCancel={() => {
            setIsAddingTemplate(false)
            setEditingTemplate(null)
          }}
        />
      )}
    </div>
  )
}

// User Prompt Editor Modal
function UserPromptEditor({
  category,
  currentPrompt,
  hasCustomPrompt = false,
  onSave,
  onReset,
  onCancel,
}: {
  category: PromptCategory
  currentPrompt: string
  hasCustomPrompt?: boolean
  onSave: (prompt: string) => void
  onReset?: () => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [userPrompt, setUserPrompt] = useState(currentPrompt)
  const [showVariablePanel, setShowVariablePanel] = useState(true)

  // Ref for textarea to support cursor position insertion
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const CategoryIcon = CATEGORY_ICONS[category]

  // Handle variable insertion at cursor position
  const handleInsertVariable = (variableRef: string) => {
    const textarea = textareaRef.current
    if (!textarea) {
      setUserPrompt((prev) => prev + variableRef)
      return
    }

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const newValue =
      userPrompt.substring(0, start) + variableRef + userPrompt.substring(end)

    setUserPrompt(newValue)

    const newCursorPos = start + variableRef.length

    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(newCursorPos, newCursorPos)
    }, 0)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-5xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <CategoryIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>
              {t('promptManagement.editUserPrompt')} - {t(`promptManagement.categories.${category}`)}
            </h2>
            {hasCustomPrompt && (
              <span className={`${fontClasses.xs} px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded`}>
                {t('prompts.modified')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowVariablePanel(!showVariablePanel)}
              className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
              title={showVariablePanel ? 'Hide variables' : 'Show variables'}
            >
              {showVariablePanel ? (
                <PanelRightClose className="w-5 h-5" />
              ) : (
                <PanelRightOpen className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={onCancel}
              className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content with Variable Panel */}
        <div className="flex-1 overflow-hidden flex">
          {/* Main Editor */}
          <div className={`flex-1 overflow-y-auto p-4 ${showVariablePanel ? 'border-r border-gray-200 dark:border-gray-700' : ''}`}>
            <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-2`}>
              {t('prompts.userPrompt')}
            </label>
            <textarea
              ref={textareaRef}
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              placeholder={t('prompts.userPromptPlaceholder')}
              rows={16}
              className={`w-full px-3 py-2 ${fontClasses.sm} font-mono border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none`}
            />
          </div>

          {/* Variable Panel */}
          {showVariablePanel && (
            <div className="w-80 flex-shrink-0 p-4 overflow-y-auto bg-gray-50 dark:bg-gray-900/50">
              <VariablePanel
                stage={category as PromptStage}
                onInsert={handleInsertVariable}
                templateContent={userPrompt}
                compact={false}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700">
          <div>
            {hasCustomPrompt && onReset && (
              <button
                onClick={onReset}
                className={`flex items-center gap-2 px-4 py-2 ${fontClasses.sm} text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/20 rounded-md transition-colors`}
              >
                <RefreshCw className="w-4 h-4" />
                {t('promptManagement.resetToDefault')}
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onCancel}
              className={`px-4 py-2 ${fontClasses.sm} text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors`}
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={() => onSave(userPrompt)}
              className={`flex items-center gap-2 px-4 py-2 ${fontClasses.sm} bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors`}
            >
              <Save className="w-4 h-4" />
              {t('common.save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Project Prompt Configs Component
function ProjectPromptConfigs({
  projectId,
}: {
  projectId: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [editingCategory, setEditingCategory] = useState<PromptCategory | null>(null)

  // Fetch project configs
  const { data: configs = [], isLoading } = useQuery({
    queryKey: ['projectPromptConfigs', projectId],
    queryFn: () => api.getProjectPromptConfigs(projectId),
  })

  // Update config mutation (creates or updates)
  const updateMutation = useMutation({
    mutationFn: ({ category, data }: { category: string; data: Parameters<typeof api.updateProjectPromptConfig>[2] }) =>
      api.updateProjectPromptConfig(projectId, category, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projectPromptConfigs', projectId] })
    },
  })

  // Reset user prompt mutation
  const resetMutation = useMutation({
    mutationFn: (category: string) => api.resetProjectUserPrompt(projectId, category),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projectPromptConfigs', projectId] })
    },
  })

  const handleSaveUserPrompt = (category: PromptCategory, prompt: string) => {
    updateMutation.mutate({
      category,
      data: {
        custom_user_prompt: prompt,  // If provided, saves to project file
      },
    })
    setEditingCategory(null)
  }

  const handleResetUserPrompt = (category: PromptCategory) => {
    if (window.confirm(t('promptManagement.confirmResetPrompt'))) {
      resetMutation.mutate(category)
      setEditingCategory(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 mt-4">
        <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <>
      <div className="mt-6 space-y-3">
        {CATEGORIES.map((category) => {
          const config = configs.find((c) => c.category === category)
          const CategoryIcon = CATEGORY_ICONS[category]
          const hasCustomUserPrompt = config?.has_custom_user_prompt || false

          return (
            <div
              key={category}
              className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden"
            >
              <div
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                onClick={() => setEditingCategory(category)}
              >
                <div className="flex items-center gap-2">
                  <CategoryIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                  <h3 className={`${fontClasses.base} font-medium text-gray-900 dark:text-white`}>
                    {t(`promptManagement.categories.${category}`)}
                  </h3>
                  {hasCustomUserPrompt && (
                    <span className={`${fontClasses.xs} px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded`}>
                      {t('prompts.modified')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {hasCustomUserPrompt && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleResetUserPrompt(category)
                      }}
                      className="p-1.5 text-gray-500 hover:text-orange-600 dark:text-gray-400 dark:hover:text-orange-400 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                      title={t('promptManagement.resetToDefault')}
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingCategory(category)
                    }}
                    className="p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                    title={t('common.edit')}
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Preview of resolved user prompt */}
              {config?.resolved_user_prompt && (
                <div className="px-3 py-2 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-600">
                  <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 font-mono truncate`}>
                    {config.resolved_user_prompt.length > 100
                      ? safeTruncate(config.resolved_user_prompt, 100)
                      : config.resolved_user_prompt}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* User Prompt Editor Modal */}
      {editingCategory && (
        <UserPromptEditor
          category={editingCategory}
          currentPrompt={configs.find((c) => c.category === editingCategory)?.resolved_user_prompt || ''}
          hasCustomPrompt={configs.find((c) => c.category === editingCategory)?.has_custom_user_prompt || false}
          onSave={(prompt) => handleSaveUserPrompt(editingCategory, prompt)}
          onReset={() => handleResetUserPrompt(editingCategory)}
          onCancel={() => setEditingCategory(null)}
        />
      )}
    </>
  )
}

// Variable Type options
const VARIABLE_TYPES = ['string', 'number', 'boolean', 'json'] as const
type VariableValueType = typeof VARIABLE_TYPES[number]

// Variable Editor Modal
function VariableEditor({
  variable,
  onSave,
  onCancel,
  isNew = false,
}: {
  variable: Partial<ProjectVariable>
  onSave: (data: { name: string; value: string; value_type: VariableValueType; description?: string }) => void
  onCancel: () => void
  isNew?: boolean
}) {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [name, setName] = useState(variable.name || '')
  const [value, setValue] = useState(variable.value || '')
  const [valueType, setValueType] = useState<VariableValueType>(
    (variable.value_type as VariableValueType) || 'string'
  )
  const [description, setDescription] = useState(variable.description || '')
  const [jsonError, setJsonError] = useState<string | null>(null)

  // Validate JSON when type is json
  const validateJson = (val: string) => {
    if (valueType !== 'json') {
      setJsonError(null)
      return true
    }
    try {
      JSON.parse(val)
      setJsonError(null)
      return true
    } catch {
      setJsonError('Invalid JSON format')
      return false
    }
  }

  const handleSave = () => {
    if (!name.trim() || !value.trim()) return
    if (!validateJson(value)) return

    onSave({
      name: name.trim(),
      value: value.trim(),
      value_type: valueType,
      description: description.trim() || undefined,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Variable className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>
              {isNew ? t('promptManagement.addVariable') : t('promptManagement.editVariable')}
            </h2>
          </div>
          <button
            onClick={onCancel}
            className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Name and Type Row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                {t('promptManagement.variableName')}
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value.replace(/[^a-zA-Z0-9_]/g, ''))}
                placeholder={t('promptManagement.variableNamePlaceholder')}
                disabled={!isNew}
                className={`w-full px-3 py-2 ${fontClasses.base} font-mono border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:bg-gray-100 dark:disabled:bg-gray-600`}
              />
              {isNew && (
                <p className={`mt-1 ${fontClasses.xs} text-gray-400`}>
                  {t('promptManagement.variableHelpText').split('.')[0]}
                </p>
              )}
            </div>
            <div>
              <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
                {t('promptManagement.variableType')}
              </label>
              <select
                value={valueType}
                onChange={(e) => {
                  setValueType(e.target.value as VariableValueType)
                  if (e.target.value === 'json') {
                    validateJson(value)
                  } else {
                    setJsonError(null)
                  }
                }}
                className={`w-full px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
              >
                {VARIABLE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(`promptManagement.variableTypes.${type}`)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Value */}
          <div>
            <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
              {t('promptManagement.variableValue')}
            </label>
            <textarea
              value={value}
              onChange={(e) => {
                setValue(e.target.value)
                if (valueType === 'json') {
                  validateJson(e.target.value)
                }
              }}
              placeholder={
                valueType === 'json'
                  ? '{"key": "value"}'
                  : t('promptManagement.variableValuePlaceholder')
              }
              rows={valueType === 'json' ? 6 : 3}
              className={`w-full px-3 py-2 ${fontClasses.sm} font-mono border rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                jsonError
                  ? 'border-red-500 dark:border-red-400'
                  : 'border-gray-300 dark:border-gray-600'
              }`}
            />
            {jsonError && (
              <p className={`mt-1 ${fontClasses.xs} text-red-500`}>{jsonError}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className={`block ${fontClasses.sm} font-medium text-gray-700 dark:text-gray-300 mb-1`}>
              {t('promptManagement.variableDescription')}
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('promptManagement.variableDescriptionPlaceholder')}
              className={`w-full px-3 py-2 ${fontClasses.base} border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
            />
          </div>

          {/* Preview */}
          <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-md">
            <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 mb-1`}>
              Usage in templates:
            </p>
            <code className={`${fontClasses.sm} font-mono text-blue-600 dark:text-blue-400`}>
              {`{{user.${name || 'variable_name'}}}`}
            </code>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onCancel}
            className={`px-4 py-2 ${fontClasses.sm} text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors`}
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !value.trim() || !!jsonError}
            className={`flex items-center gap-2 px-4 py-2 ${fontClasses.sm} bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
          >
            <Save className="w-4 h-4" />
            {t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

// Project Variables Manager Component
function ProjectVariablesManager({
  projectId,
}: {
  projectId: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  const [isAddingVariable, setIsAddingVariable] = useState(false)
  const [editingVariable, setEditingVariable] = useState<ProjectVariable | null>(null)

  // Fetch project variables
  const { data: variables = [], isLoading } = useQuery({
    queryKey: ['projectVariables', projectId],
    queryFn: () => api.getProjectVariables(projectId),
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateProjectVariableRequest) =>
      api.createProjectVariable(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projectVariables', projectId] })
      setIsAddingVariable(false)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ name, data }: { name: string; data: UpdateProjectVariableRequest }) =>
      api.updateProjectVariable(projectId, name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projectVariables', projectId] })
      setEditingVariable(null)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deleteProjectVariable(projectId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projectVariables', projectId] })
    },
  })

  const handleSaveVariable = (data: { name: string; value: string; value_type: VariableValueType; description?: string }) => {
    if (editingVariable) {
      updateMutation.mutate({
        name: editingVariable.name,
        data: {
          value: data.value,
          value_type: data.value_type,
          description: data.description,
        },
      })
    } else {
      createMutation.mutate(data)
    }
  }

  const handleDeleteVariable = (name: string) => {
    if (window.confirm(t('promptManagement.confirmDelete'))) {
      deleteMutation.mutate(name)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <RefreshCw className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="mt-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Code className="w-5 h-5 text-purple-500" />
          <h3 className={`${fontClasses.base} font-medium text-gray-900 dark:text-white`}>
            {t('promptManagement.projectVariables')}
          </h3>
        </div>
        <button
          onClick={() => setIsAddingVariable(true)}
          className={`flex items-center gap-1 px-3 py-1.5 ${fontClasses.sm} text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded-md transition-colors`}
        >
          <Plus className="w-4 h-4" />
          {t('promptManagement.addVariable')}
        </button>
      </div>

      <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 mb-4`}>
        {t('promptManagement.projectVariablesDesc')}
      </p>

      {/* Variables List */}
      {variables.length === 0 ? (
        <div className="text-center py-6 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
          <Variable className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
          <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
            {t('promptManagement.noVariables')}
          </p>
          <button
            onClick={() => setIsAddingVariable(true)}
            className={`mt-2 ${fontClasses.sm} text-purple-600 dark:text-purple-400 hover:underline`}
          >
            {t('promptManagement.addFirstVariable')}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {variables.map((variable) => (
            <div
              key={variable.id}
              className="flex items-start justify-between p-3 border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <code className={`${fontClasses.sm} font-mono text-blue-600 dark:text-blue-400`}>
                    {`{{user.${variable.name}}}`}
                  </code>
                  <span className={`${fontClasses.xs} px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded`}>
                    {t(`promptManagement.variableTypes.${variable.value_type}`)}
                  </span>
                </div>
                {variable.description && (
                  <p className={`mt-1 ${fontClasses.xs} text-gray-500 dark:text-gray-400`}>
                    {variable.description}
                  </p>
                )}
                <p className={`mt-1 ${fontClasses.xs} font-mono text-gray-400 dark:text-gray-500 truncate`}>
                  {variable.value.length > 50 ? safeTruncate(variable.value, 50) : variable.value}
                </p>
              </div>
              <div className="flex items-center gap-1 ml-2">
                <button
                  onClick={() => setEditingVariable(variable)}
                  className="p-1.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                  title={t('common.edit')}
                >
                  <Edit3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDeleteVariable(variable.name)}
                  className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                  title={t('common.delete')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Variable Editor Modal */}
      {(isAddingVariable || editingVariable) && (
        <VariableEditor
          variable={editingVariable || {}}
          isNew={isAddingVariable}
          onSave={handleSaveVariable}
          onCancel={() => {
            setIsAddingVariable(false)
            setEditingVariable(null)
          }}
        />
      )}
    </div>
  )
}
