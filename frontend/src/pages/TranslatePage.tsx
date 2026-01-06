import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Play,
  Eye,
  Download,
  Settings,
  Loader2,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import { api } from '../services/api/client'
import { useSettingsStore } from '../stores/settingsStore'
import { useTranslation } from '../stores/appStore'

export function TranslatePage() {
  const { t } = useTranslation()
  const { projectId } = useParams<{ projectId: string }>()
  const [mode, setMode] = useState<'author_based' | 'optimization'>('author_based')
  const [authorBackground, setAuthorBackground] = useState('')
  const [customPrompts, setCustomPrompts] = useState('')

  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: !!projectId,
  })

  const { data: tasks } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.getProjectTasks(projectId!),
    enabled: !!projectId,
    refetchInterval: 2000, // Poll for updates
  })

  const startMutation = useMutation({
    mutationFn: api.startTranslation,
  })

  const latestTask = tasks?.[0]
  const isRunning = latestTask?.status === 'processing'

  const handleStart = () => {
    if (!projectId || !activeConfig || !activeConfig.hasApiKey) {
      alert(t('translate.configLlmFirst'))
      return
    }

    startMutation.mutate({
      project_id: projectId,
      mode,
      config_id: configId || undefined,
      author_background: authorBackground || undefined,
      custom_prompts: customPrompts ? customPrompts.split('\n').filter(Boolean) : undefined,
    })
  }

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
      </div>
    )
  }

  if (!project) {
    return <div>{t('common.projectNotFound')}</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Project header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{project.name}</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {project.author || t('home.unknownAuthor')} · {project.total_chapters} {t('home.chapters')} ·{' '}
            {project.total_paragraphs} {t('home.paragraphs')}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/preview/${projectId}`}
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <Eye className="w-4 h-4" />
            {t('common.preview')}
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <Settings className="w-4 h-4" />
            {t('common.settings')}
          </Link>
        </div>
      </div>

      {/* Translation config */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">{t('translate.translationConfig')}</h2>

        {/* Mode selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {t('translate.translationMode')}
          </label>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setMode('author_based')}
              className={`p-4 border rounded-lg text-left transition-colors ${
                mode === 'author_based'
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
              }`}
            >
              <div className="font-medium text-gray-900 dark:text-gray-100">{t('translate.authorBasedMode')}</div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {t('translate.authorBasedDesc')}
              </p>
            </button>
            <button
              onClick={() => setMode('optimization')}
              className={`p-4 border rounded-lg text-left transition-colors ${
                mode === 'optimization'
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
              }`}
            >
              <div className="font-medium text-gray-900 dark:text-gray-100">{t('translate.optimizationMode')}</div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {t('translate.optimizationDesc')}
              </p>
            </button>
          </div>
        </div>

        {/* Author background */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {t('translate.authorBackground')}
          </label>
          <textarea
            value={authorBackground}
            onChange={(e) => setAuthorBackground(e.target.value)}
            placeholder={t('translate.authorBackgroundPlaceholder')}
            className="w-full h-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
        </div>

        {/* Custom prompts */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {t('translate.customPrompts')}
          </label>
          <textarea
            value={customPrompts}
            onChange={(e) => setCustomPrompts(e.target.value)}
            placeholder={t('translate.customPromptsPlaceholder')}
            className="w-full h-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
        </div>

        {/* LLM provider info */}
        <div className={`p-4 rounded-lg mb-6 ${activeConfig ? 'bg-gray-50 dark:bg-gray-700/50' : 'bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800'}`}>
          <div className="flex items-center justify-between">
            <div>
              {activeConfig ? (
                <>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {t('translate.currentLlmConfig')}
                    <span className="font-medium text-gray-900 dark:text-gray-100 ml-1">
                      {activeConfig.name}
                    </span>
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {activeConfig.model}
                  </p>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-600 dark:text-yellow-500" />
                  <span className="text-sm text-yellow-700 dark:text-yellow-400">
                    {t('translate.configLlmWarning')}
                  </span>
                </div>
              )}
            </div>
            <Link
              to="/settings"
              className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center"
            >
              {activeConfig ? t('translate.change') : t('translate.configure')} <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleStart}
            disabled={isRunning || !activeConfig || !activeConfig.hasApiKey}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {t('translate.translating')}
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                {t('translate.startTranslation')}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress */}
      {latestTask && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">{t('translate.translationProgress')}</h2>

          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600 dark:text-gray-400">
                {latestTask.completed_paragraphs} / {latestTask.total_paragraphs} {t('home.paragraphs')}
              </span>
              <span className="text-gray-900 dark:text-gray-100 font-medium">
                {Math.round(latestTask.progress * 100)}%
              </span>
            </div>
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${latestTask.progress * 100}%` }}
              />
            </div>
          </div>

          <div className="flex items-center justify-between text-sm">
            <span
              className={`px-2 py-1 rounded ${
                latestTask.status === 'completed'
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                  : latestTask.status === 'processing'
                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                  : latestTask.status === 'failed'
                  ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              {latestTask.status === 'completed'
                ? t('translate.statusCompleted')
                : latestTask.status === 'processing'
                ? t('translate.statusProcessing')
                : latestTask.status === 'paused'
                ? t('translate.statusPaused')
                : latestTask.status === 'failed'
                ? t('translate.statusFailed')
                : t('translate.statusPending')}
            </span>

            {latestTask.status === 'completed' && (
              <button className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700">
                <Download className="w-4 h-4" />
                {t('translate.exportEpub')}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
