import { useState, useRef, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Settings, Star, Check, AlertCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useSettingsStore, LLMConfig } from '../../stores/settingsStore'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'
import { api } from '../../services/api/client'
import { sortLLMConfigs } from '../../utils/llmConfig'

interface LLMConfigSelectorProps {
  className?: string
}

export function LLMConfigSelector({ className = '' }: LLMConfigSelectorProps) {
  const { t } = useTranslation()
  const { llmConfigs, activeConfigId, setActiveConfig, getActiveConfig } = useSettingsStore()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const activeConfig = getActiveConfig()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Fetch models for sorting by price
  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  // Sort configs using the same logic as SettingsPage
  const sortedConfigs = useMemo(() => {
    return sortLLMConfigs(llmConfigs, models || [])
  }, [llmConfigs, models])

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

  const handleSelect = (config: LLMConfig) => {
    setActiveConfig(config.id)
    setIsOpen(false)
  }

  // No configs available
  if (llmConfigs.length === 0) {
    return (
      <Link
        to="/settings"
        className={`flex items-center gap-2 px-2 lg:px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 rounded-lg border border-amber-200 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/30 ${fontClasses.button} ${className}`}
      >
        <AlertCircle className="w-4 h-4" />
        {t('settings.configureLLM')}
        <Settings className="w-4 h-4" />
      </Link>
    )
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-2 lg:px-3 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${fontClasses.button}`}
      >
        <span className="font-medium text-gray-900 dark:text-gray-100">
          {activeConfig?.name || activeConfig?.model || t('settings.selectConfig')}
        </span>
        {activeConfig?.isDefault && (
          <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
        )}
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50 py-1">
          {/* Config list */}
          <div className="max-h-64 overflow-y-auto">
            {sortedConfigs.map((config) => (
              <button
                key={config.id}
                onClick={() => handleSelect(config)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                  config.id === activeConfigId ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 dark:text-gray-100 truncate">
                      {config.name}
                    </span>
                    {config.isDefault && (
                      <Star className="w-3 h-3 text-amber-500 fill-amber-500 flex-shrink-0" />
                    )}
                  </div>
                  <div className={`${fontClasses.xs} text-gray-500 dark:text-gray-400 truncate`}>
                    {config.provider} / {config.model} · T:{config.temperature}
                  </div>
                </div>
                {config.id === activeConfigId && (
                  <Check className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                )}
              </button>
            ))}
          </div>

          {/* Divider */}
          <div className="border-t border-gray-200 dark:border-gray-700 my-1" />

          {/* Settings link */}
          <Link
            to="/settings"
            onClick={() => setIsOpen(false)}
            className={`flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${fontClasses.button}`}
          >
            <Settings className="w-4 h-4" />
            {t('settings.manageConfigs')}
          </Link>
        </div>
      )}
    </div>
  )
}
