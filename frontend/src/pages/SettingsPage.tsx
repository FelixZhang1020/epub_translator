import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Check,
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  Star,
  StarOff,
  Edit3,
  X,
  Save,
  Eye,
  EyeOff,
  Key,
  Type,
  Copy,
  Files,
  Thermometer,
} from 'lucide-react'
import { api, ModelInfo, ProviderInfo } from '../services/api/client'
import { useSettingsStore, LLMConfig } from '../stores/settingsStore'
import { useTranslation, useAppStore, FontSize, fontSizeClasses } from '../stores/appStore'

// Format cost for display ($/M = per million tokens)
function formatCost(costPerMillion: number): string {
  if (costPerMillion === 0) return 'Free'
  if (costPerMillion < 0.01) return `$${costPerMillion.toFixed(4)}/M`
  if (costPerMillion < 1) return `$${costPerMillion.toFixed(2)}/M`
  return `$${costPerMillion.toFixed(1)}/M`
}

// Format context window
function formatContextWindow(tokens: number | null): string {
  if (!tokens) return 'N/A'
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(0)}K`
  return `${tokens}`
}


// Config editor component
function ConfigEditor({
  config,
  providers,
  models,
  onSave,
  onCancel,
  onTestExisting,
  isNew = false,
}: {
  config: Partial<LLMConfig>
  providers: ProviderInfo[]
  models: ModelInfo[]
  onSave: (config: { name: string; provider: string; model: string; temperature: number; isDefault: boolean; apiKey?: string }) => void
  onCancel: () => void
  onTestExisting?: (id: string) => Promise<{ success: boolean; message: string }>
  isNew?: boolean
}) {
  const { t } = useTranslation()
  const [name, setName] = useState(config.name || '')
  const [provider, setProvider] = useState(config.provider || '')
  const [model, setModel] = useState(config.model || '')
  const [apiKey, setApiKey] = useState(config.apiKey || '')
  const [temperature, setTemperature] = useState(config.temperature ?? 0.7)
  const [isDefault, setIsDefault] = useState(config.isDefault || false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiKeyCopied, setApiKeyCopied] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [isTestingExisting, setIsTestingExisting] = useState(false)

  const testMutation = useMutation({
    mutationFn: api.testConnection,
    onSuccess: (data) => setTestResult(data),
    onError: (error) => setTestResult({ success: false, message: String(error) }),
  })

  // Get selected provider info
  const selectedProvider = providers.find(p => p.name === provider)
  const isManualModel = selectedProvider?.manual_model || false

  // Filter models by provider
  const providerModels = useMemo(() => {
    if (!provider || isManualModel) return []
    return models.filter(m => m.provider === provider)
  }, [models, provider, isManualModel])

  // Get selected model info
  const selectedModel = models.find(m => m.id === model)

  // Auto-select first model when provider changes
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider)
    const newProviderInfo = providers.find(p => p.name === newProvider)
    if (newProviderInfo?.manual_model) {
      // For manual model providers, clear the model
      setModel('')
    } else {
      const firstModel = models.find(m => m.provider === newProvider)
      if (firstModel) {
        setModel(firstModel.id)
      } else {
        setModel('')
      }
    }
    setTestResult(null)
  }

  const handleTest = async () => {
    // If editing existing config and no new API key entered, test using stored key
    if (!isNew && config.id && !apiKey && config.hasApiKey && onTestExisting) {
      setTestResult(null)
      setIsTestingExisting(true)
      try {
        const result = await onTestExisting(config.id)
        setTestResult(result)
      } catch (error) {
        setTestResult({ success: false, message: String(error) })
      } finally {
        setIsTestingExisting(false)
      }
    } else if (model && apiKey) {
      // Test with newly entered API key
      testMutation.mutate({ model, api_key: apiKey })
    }
  }

  // Can test if: (has model AND has API key) OR (editing existing config with stored key)
  const canTest = (model && apiKey) || (!isNew && config.id && config.hasApiKey && !apiKey)
  const isTesting = testMutation.isPending || isTestingExisting

  const handleSave = () => {
    // For new configs, API key is required
    // For editing existing configs, API key is optional (only update if provided)
    if (!name.trim() || !provider || !model) {
      alert(t('settings.fillAllFields'))
      return
    }
    if (isNew && !apiKey.trim()) {
      alert(t('settings.fillAllFields'))
      return
    }
    const saveConfig: { name: string; provider: string; model: string; temperature: number; isDefault: boolean; apiKey?: string } = {
      name: name.trim(),
      provider,
      model,
      temperature,
      isDefault,
    }
    if (apiKey.trim()) {
      saveConfig.apiKey = apiKey.trim()
    }
    onSave(saveConfig)
  }

  const handleCopyApiKey = async () => {
    if (!apiKey) return
    try {
      await navigator.clipboard.writeText(apiKey)
      setApiKeyCopied(true)
      setTimeout(() => setApiKeyCopied(false), 1500)
    } catch {
      setApiKeyCopied(false)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          {isNew ? t('settings.addNew') : t('settings.editConfig')}
        </h3>
        <button
          onClick={onCancel}
          className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-4">
        {/* Config name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('settings.configName')} *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('settings.configNamePlaceholder')}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
          />
        </div>

        {/* Provider dropdown */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('settings.provider')} *
          </label>
          <select
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">{t('settings.selectProvider')}</option>
            {providers.map((p) => (
              <option key={p.name} value={p.name}>
                {t(`providers.${p.name}`)}
              </option>
            ))}
          </select>
        </div>

        {/* Model selection - dropdown or text input based on provider */}
        {provider && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('settings.model')} *
            </label>
            {isManualModel ? (
              /* Manual model input for Ollama/OpenRouter */
              <div>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => {
                    setModel(e.target.value)
                    setTestResult(null)
                  }}
                  placeholder={provider === 'ollama' ? 'llama3.1, qwen2.5, etc.' : 'openai/gpt-4o, anthropic/claude-3.5-sonnet, etc.'}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {provider === 'ollama' ? t('settings.modelHintOllama') : t('settings.modelHintOpenRouter')}
                </p>
              </div>
            ) : (
              /* Dropdown for providers with predefined models */
              <>
                <select
                  value={model}
                  onChange={(e) => {
                    setModel(e.target.value)
                    setTestResult(null)
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="">{t('settings.selectModel')}</option>
                  {providerModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} - {t('settings.input')}: {formatCost(m.input_cost_per_million)} / {t('settings.output')}: {formatCost(m.output_cost_per_million)}
                    </option>
                  ))}
                </select>

                {/* Selected model info */}
                {selectedModel && (
                  <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm">
                    <div className="grid grid-cols-2 gap-2 text-gray-600 dark:text-gray-400">
                      <div>{t('settings.context')}: {formatContextWindow(selectedModel.context_window)}</div>
                      <div>{t('settings.maxOutput')}: {formatContextWindow(selectedModel.max_tokens)}</div>
                      <div>{t('settings.input')}: {formatCost(selectedModel.input_cost_per_million)}</div>
                      <div>{t('settings.output')}: {formatCost(selectedModel.output_cost_per_million)}</div>
                    </div>
                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-500">
                      {t('settings.estCostWithCurrency', {
                        amount: ((10000 / 4 * (selectedModel.input_cost_per_million / 1000000)) + (15000 / 4 * (selectedModel.output_cost_per_million / 1000000))).toFixed(4),
                      })}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* API Key */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('settings.apiKey')} {isNew ? '*' : ''}
          </label>
          <div className="relative">
            <input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                setTestResult(null)
              }}
              placeholder={isNew ? t('settings.apiKeyPlaceholder') : (config.maskedApiKey || t('settings.apiKeyPlaceholderEdit'))}
              className="w-full px-3 py-2 pr-20 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
            />
            {apiKey && (
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopyApiKey}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  title={t('common.copy')}
                >
                  {apiKeyCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  title={showApiKey ? t('common.hide') : t('common.show')}
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            )}
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {isNew ? t('settings.apiKeyHint') : t('settings.apiKeyHintEdit')}
          </p>
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            <span className="flex items-center gap-1.5">
              <Thermometer className="w-4 h-4" />
              {t('settings.temperature')}
            </span>
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
            <input
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => {
                const val = parseFloat(e.target.value)
                if (!isNaN(val) && val >= 0 && val <= 2) {
                  setTemperature(val)
                }
              }}
              className="w-20 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center"
            />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {t('settings.temperatureHint')}
          </p>
        </div>

        {/* Set as default */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="isDefault"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
            className="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500 bg-white dark:bg-gray-700"
          />
          <label htmlFor="isDefault" className="text-sm text-gray-700 dark:text-gray-300">
            {t('settings.setAsDefault')}
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleTest}
            disabled={!canTest || isTesting}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:cursor-not-allowed"
          >
            {isTesting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('settings.testing')}
              </>
            ) : (
              t('settings.testConnection')
            )}
          </button>

          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Save className="w-4 h-4" />
            {t('common.save')}
          </button>

          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            {t('common.cancel')}
          </button>

          {testResult && (
            <div
              className={`flex items-center gap-2 ml-auto ${
                testResult.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              }`}
            >
              {testResult.success ? (
                <Check className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              <span className="text-sm">{testResult.message}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Config card component
function ConfigCard({
  config,
  models,
  isActive,
  onEdit,
  onDelete,
  onSetDefault,
  onSetActive,
  onDuplicate,
}: {
  config: LLMConfig
  models: ModelInfo[]
  isActive: boolean
  onEdit: () => void
  onDelete: () => void
  onSetDefault: () => void
  onSetActive: () => void
  onDuplicate: () => void
}) {
  const { t } = useTranslation()
  const modelInfo = models.find(m => m.id === config.model)

  return (
    <div
      className={`p-4 border rounded-lg transition-all ${
        isActive
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 ring-2 ring-blue-200 dark:ring-blue-800'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 cursor-pointer" onClick={onSetActive}>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900 dark:text-white">{config.name}</span>
            {config.isDefault && (
              <span className="px-2 py-0.5 text-xs bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-400 rounded-full">
                {t('settings.default')}
              </span>
            )}
            {isActive && (
              <span className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 rounded-full">
                {t('settings.active')}
              </span>
            )}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {modelInfo?.display_name || config.model} · T:{config.temperature}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-500 mt-1">
            <Key className="w-3 h-3" />
            <span className="font-mono">
              {config.hasApiKey ? config.maskedApiKey : t('settings.apiKeyMissing')}
            </span>
          </div>
          {modelInfo && (
            <div className="text-xs text-gray-500 dark:text-gray-500 mt-1">
              {t('settings.input')}: {formatCost(modelInfo.input_cost_per_million)} / {t('settings.output')}: {formatCost(modelInfo.output_cost_per_million)}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onSetDefault}
            className={`p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 ${
              config.isDefault ? 'text-yellow-500' : 'text-gray-400 dark:text-gray-500'
            }`}
            title={config.isDefault ? t('settings.default') : t('settings.setAsDefault')}
          >
            {config.isDefault ? <Star className="w-4 h-4 fill-current" /> : <StarOff className="w-4 h-4" />}
          </button>
          <button
            onClick={onDuplicate}
            className="p-1.5 rounded text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300"
            title={t('settings.duplicate')}
          >
            <Files className="w-4 h-4" />
          </button>
          <button
            onClick={onEdit}
            className="p-1.5 rounded text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300"
            title={t('common.edit')}
          >
            <Edit3 className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-red-600 dark:hover:text-red-400"
            title={t('common.delete')}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// App Settings Section Component
function AppSettingsSection() {
  const { t } = useTranslation()
  const { fontSize, setFontSize, resetPanelWidths } = useAppStore()
  const fontClasses = fontSizeClasses[fontSize]

  const fontSizeOptions: { value: FontSize; label: string }[] = [
    { value: 'small', label: t('fontSize.small') },
    { value: 'medium', label: t('fontSize.medium') },
    { value: 'large', label: t('fontSize.large') },
  ]

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-8">
      <div className="flex items-center gap-2 mb-4">
        <Type className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <h2 className={`${fontClasses.heading} font-semibold text-gray-900 dark:text-white`}>{t('appSettings.title')}</h2>
      </div>
      <p className={`${fontClasses.base} text-gray-600 dark:text-gray-400 mb-4`}>{t('appSettings.subtitle')}</p>

      <div className="space-y-4">
        {/* Font Size */}
        <div>
          <label className={`block ${fontClasses.label} font-medium text-gray-700 dark:text-gray-300 mb-2`}>
            {t('fontSize.title')}
          </label>
          <div className="flex gap-2">
            {fontSizeOptions.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setFontSize(value)}
                className={`px-4 py-2 rounded-lg border transition-colors ${fontClasses.button} ${
                  fontSize === value
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Panel Widths */}
        <div>
          <label className={`block ${fontClasses.label} font-medium text-gray-700 dark:text-gray-300 mb-2`}>
            {t('appSettings.panelWidths')}
          </label>
          <p className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 mb-2`}>
            {t('appSettings.panelWidthsHint')}
          </p>
          <button
            onClick={resetPanelWidths}
            className={`px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${fontClasses.button}`}
          >
            {t('appSettings.resetPanelWidths')}
          </button>
        </div>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const {
    llmConfigs,
    activeConfigId,
    addLLMConfig,
    updateLLMConfig,
    deleteLLMConfig,
    setDefaultConfig,
    setActiveConfig,
    testConfig,
    duplicateLLMConfig,
  } = useSettingsStore()

  const [isAdding, setIsAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [duplicatingConfig, setDuplicatingConfig] = useState<LLMConfig | null>(null)
  const [duplicateName, setDuplicateName] = useState('')

  // Fetch providers
  const { data: providers, isLoading: providersLoading } = useQuery({
    queryKey: ['providers'],
    queryFn: api.getProviders,
  })

  // Fetch models
  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  // Filter providers - include those with models OR manual_model providers
  const availableProviders = useMemo(() => {
    if (!providers) return []
    return providers.filter(p => p.model_count > 0 || p.manual_model)
  }, [providers])

  // Sort configs: default first, then by provider, then by price (high to low)
  const sortedConfigs = useMemo(() => {
    if (!llmConfigs.length) return []

    // Create a map of model prices for quick lookup
    const modelPriceMap = new Map<string, number>()
    if (models) {
      for (const m of models) {
        modelPriceMap.set(m.id, m.input_cost_per_million)
      }
    }

    // Provider order (same as PROVIDER_CONFIG in backend)
    const providerOrder: Record<string, number> = {
      openai: 0,
      anthropic: 1,
      gemini: 2,
      qwen: 3,
      deepseek: 4,
      ollama: 5,
      openrouter: 6,
    }

    return [...llmConfigs].sort((a, b) => {
      // Default first
      if (a.isDefault !== b.isDefault) {
        return a.isDefault ? -1 : 1
      }
      // Then by provider order
      const providerA = providerOrder[a.provider] ?? 99
      const providerB = providerOrder[b.provider] ?? 99
      if (providerA !== providerB) {
        return providerA - providerB
      }
      // Then by price (high to low)
      const priceA = modelPriceMap.get(a.model) ?? 0
      const priceB = modelPriceMap.get(b.model) ?? 0
      return priceB - priceA
    })
  }, [llmConfigs, models])

  const handleAdd = async (config: { name: string; provider: string; model: string; temperature: number; isDefault: boolean; apiKey?: string }) => {
    if (!config.apiKey) {
      alert(t('settings.fillAllFields'))
      return
    }
    await addLLMConfig({ ...config, apiKey: config.apiKey })
    setIsAdding(false)
  }

  const handleUpdate = async (id: string, config: { name: string; provider: string; model: string; temperature: number; isDefault: boolean; apiKey?: string }) => {
    await updateLLMConfig(id, config)
    setEditingId(null)
  }

  const handleDelete = (id: string, name: string) => {
    if (confirm(t('settings.confirmDelete', { name }))) {
      deleteLLMConfig(id)
    }
  }

  const handleDuplicateClick = (config: LLMConfig) => {
    setDuplicatingConfig(config)
    setDuplicateName(`${config.name} (Copy)`)
  }

  const handleDuplicateConfirm = async () => {
    if (duplicatingConfig && duplicateName.trim()) {
      await duplicateLLMConfig(duplicatingConfig.id, duplicateName.trim())
      setDuplicatingConfig(null)
      setDuplicateName('')
    }
  }

  const handleDuplicateCancel = () => {
    setDuplicatingConfig(null)
    setDuplicateName('')
  }

  if (providersLoading || modelsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  const editingConfig = editingId ? llmConfigs.find(c => c.id === editingId) : null

  return (
    <div className="max-w-3xl mx-auto">
      {/* App Settings Section */}
      <AppSettingsSection />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className={`${fontClasses.title} font-bold text-gray-900 dark:text-white`}>{t('settings.title')}</h1>
          <p className={`${fontClasses.base} text-gray-600 dark:text-gray-400 mt-1`}>{t('settings.subtitle')}</p>
        </div>
        {!isAdding && !editingId && (
          <button
            onClick={() => setIsAdding(true)}
            className={`flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 ${fontClasses.button}`}
          >
            <Plus className="w-4 h-4" />
            {t('settings.addConfig')}
          </button>
        )}
      </div>

      {/* Add new config form */}
      {isAdding && (
        <div className="mb-6">
          <ConfigEditor
            config={{ isDefault: llmConfigs.length === 0 }}
            providers={availableProviders}
            models={models || []}
            onSave={handleAdd}
            onCancel={() => setIsAdding(false)}
            isNew
          />
        </div>
      )}

      {/* Edit config form */}
      {editingConfig && (
        <div className="mb-6">
          <ConfigEditor
            config={editingConfig}
            providers={availableProviders}
            models={models || []}
            onSave={(config) => handleUpdate(editingConfig.id, config)}
            onCancel={() => setEditingId(null)}
            onTestExisting={testConfig}
          />
        </div>
      )}

      {/* Config list */}
      {!isAdding && !editingId && (
        <div className="space-y-3">
          {llmConfigs.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
              <p className={`${fontClasses.base} text-gray-500 dark:text-gray-400 mb-4`}>{t('settings.noConfigs')}</p>
              <button
                onClick={() => setIsAdding(true)}
                className={`${fontClasses.button} text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium`}
              >
                {t('settings.addFirstConfig')}
              </button>
            </div>
          ) : (
            sortedConfigs.map((config) => (
              <ConfigCard
                key={config.id}
                config={config}
                models={models || []}
                isActive={activeConfigId === config.id}
                onEdit={() => setEditingId(config.id)}
                onDelete={() => handleDelete(config.id, config.name)}
                onSetDefault={() => setDefaultConfig(config.id)}
                onSetActive={() => setActiveConfig(config.id)}
                onDuplicate={() => handleDuplicateClick(config)}
              />
            ))
          )}
        </div>
      )}

      {/* Help text */}
      {llmConfigs.length > 0 && !isAdding && !editingId && (
        <div className={`mt-6 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg ${fontClasses.base} text-gray-600 dark:text-gray-400`}>
          <p><strong>{t('settings.tip')}:</strong> {t('settings.tipContent')}</p>
          <p className="mt-1">{t('settings.tipDefaultContent')}</p>
        </div>
      )}

      {/* Duplicate Modal */}
      {duplicatingConfig && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={handleDuplicateCancel}
          />
          {/* Modal */}
          <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('settings.duplicate')}
              </h3>
              <button
                onClick={handleDuplicateCancel}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('settings.duplicatePrompt')}
              </label>
              <input
                type="text"
                value={duplicateName}
                onChange={(e) => setDuplicateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleDuplicateConfirm()
                  if (e.key === 'Escape') handleDuplicateCancel()
                }}
                autoFocus
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleDuplicateCancel}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleDuplicateConfirm}
                disabled={!duplicateName.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                <Files className="w-4 h-4" />
                {t('settings.duplicate')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
