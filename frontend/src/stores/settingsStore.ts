import { create } from 'zustand'
import { api, LLMConfiguration, CreateLLMConfigRequest, UpdateLLMConfigRequest } from '../services/api/client'

// LLM Configuration type (frontend view)
export interface LLMConfig {
  id: string
  name: string
  provider: string
  model: string
  apiKey?: string  // Only for creating/updating, not stored in frontend
  hasApiKey: boolean  // Whether backend has API key
  maskedApiKey: string  // First 4 + last 4 chars for display (e.g., "sk-ab••••••••cd")
  temperature: number  // LLM temperature (0.0-2.0)
  isDefault: boolean
  isActive: boolean
}

interface SettingsState {
  // Multiple LLM configurations
  llmConfigs: LLMConfig[]
  activeConfigId: string | null
  // Loading state
  isLoading: boolean
  error: string | null
  _isHydrated: boolean

  // Actions for LLM configs
  loadConfigs: () => Promise<void>
  addLLMConfig: (config: Omit<LLMConfig, 'id' | 'hasApiKey' | 'isActive' | 'maskedApiKey'> & { apiKey: string }) => Promise<string>
  updateLLMConfig: (id: string, updates: Partial<Omit<LLMConfig, 'id' | 'hasApiKey' | 'maskedApiKey'>>) => Promise<void>
  deleteLLMConfig: (id: string) => Promise<void>
  setDefaultConfig: (id: string) => Promise<void>
  setActiveConfig: (id: string) => Promise<void>
  testConfig: (id: string) => Promise<{ success: boolean; message: string }>
  duplicateLLMConfig: (id: string, newName: string) => Promise<string>

  // Get current active config
  getActiveConfig: () => LLMConfig | null
  getDefaultConfig: () => LLMConfig | null
  getActiveConfigId: () => string | null
}

// Convert backend config to frontend format
const toFrontendConfig = (config: LLMConfiguration): LLMConfig => ({
  id: config.id,
  name: config.name,
  provider: config.provider,
  model: config.model,
  hasApiKey: config.has_api_key,
  maskedApiKey: config.masked_api_key || '',
  temperature: config.temperature ?? 0.7,
  isDefault: config.is_default,
  isActive: config.is_active,
})

export const useSettingsStore = create<SettingsState>()((set, get) => ({
  llmConfigs: [],
  activeConfigId: null,
  isLoading: false,
  error: null,
  _isHydrated: false,

  loadConfigs: async () => {
    set({ isLoading: true, error: null })
    try {
      const configs = await api.getLLMConfigurations()
      const frontendConfigs = configs.map(toFrontendConfig)
      const activeConfig = frontendConfigs.find(c => c.isActive)

      set({
        llmConfigs: frontendConfigs,
        activeConfigId: activeConfig?.id || frontendConfigs.find(c => c.isDefault)?.id || null,
        isLoading: false,
        _isHydrated: true,
      })
    } catch (error) {
      console.error('Failed to load LLM configurations:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to load configurations',
        isLoading: false,
        _isHydrated: true,
      })
    }
  },

  addLLMConfig: async (config) => {
    set({ isLoading: true, error: null })
    try {
      const request: CreateLLMConfigRequest = {
        name: config.name,
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey,
        temperature: config.temperature,
        is_default: config.isDefault,
        is_active: get().llmConfigs.length === 0 ? true : config.isDefault,
      }

      const created = await api.createLLMConfiguration(request)
      const frontendConfig = toFrontendConfig(created)

      set((state) => ({
        llmConfigs: [...state.llmConfigs.map(c =>
          frontendConfig.isDefault ? { ...c, isDefault: false } : c
        ), frontendConfig],
        activeConfigId: frontendConfig.isActive ? frontendConfig.id : state.activeConfigId,
        isLoading: false,
      }))

      return created.id
    } catch (error) {
      console.error('Failed to add LLM configuration:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to add configuration',
        isLoading: false,
      })
      throw error
    }
  },

  updateLLMConfig: async (id, updates) => {
    set({ isLoading: true, error: null })
    try {
      const request: UpdateLLMConfigRequest = {}
      if (updates.name !== undefined) request.name = updates.name
      if (updates.provider !== undefined) request.provider = updates.provider
      if (updates.model !== undefined) request.model = updates.model
      if (updates.apiKey !== undefined) request.api_key = updates.apiKey
      if (updates.temperature !== undefined) request.temperature = updates.temperature
      if (updates.isDefault !== undefined) request.is_default = updates.isDefault
      if (updates.isActive !== undefined) request.is_active = updates.isActive

      const updated = await api.updateLLMConfiguration(id, request)
      const frontendConfig = toFrontendConfig(updated)

      set((state) => ({
        llmConfigs: state.llmConfigs.map((config) => {
          if (config.id === id) {
            return frontendConfig
          }
          // If setting this as default, unset others
          if (updates.isDefault && config.id !== id) {
            return { ...config, isDefault: false }
          }
          return config
        }),
        isLoading: false,
      }))
    } catch (error) {
      console.error('Failed to update LLM configuration:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to update configuration',
        isLoading: false,
      })
      throw error
    }
  },

  deleteLLMConfig: async (id) => {
    set({ isLoading: true, error: null })
    try {
      await api.deleteLLMConfiguration(id)

      const state = get()
      const configToDelete = state.llmConfigs.find(c => c.id === id)
      const remainingConfigs = state.llmConfigs.filter(c => c.id !== id)

      // If deleting the default, make the first remaining one default
      let newConfigs = remainingConfigs
      if (configToDelete?.isDefault && remainingConfigs.length > 0) {
        newConfigs = remainingConfigs.map((c, i) =>
          i === 0 ? { ...c, isDefault: true } : c
        )
      }

      // If deleting the active config, switch to default or first
      let newActiveId = state.activeConfigId
      if (state.activeConfigId === id) {
        const defaultConfig = newConfigs.find(c => c.isDefault)
        newActiveId = defaultConfig?.id || newConfigs[0]?.id || null
      }

      set({
        llmConfigs: newConfigs,
        activeConfigId: newActiveId,
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to delete LLM configuration:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to delete configuration',
        isLoading: false,
      })
      throw error
    }
  },

  setDefaultConfig: async (id) => {
    await get().updateLLMConfig(id, { isDefault: true })
  },

  setActiveConfig: async (id) => {
    set({ isLoading: true, error: null })
    try {
      await api.activateLLMConfiguration(id)
      set((state) => ({
        llmConfigs: state.llmConfigs.map(c => ({
          ...c,
          isActive: c.id === id,
        })),
        activeConfigId: id,
        isLoading: false,
      }))
    } catch (error) {
      console.error('Failed to set active configuration:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to set active configuration',
        isLoading: false,
      })
      throw error
    }
  },

  testConfig: async (id) => {
    try {
      const result = await api.testLLMConfiguration(id)
      return { success: result.success, message: result.message }
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Test failed',
      }
    }
  },

  duplicateLLMConfig: async (id, newName) => {
    set({ isLoading: true, error: null })
    try {
      const duplicated = await api.duplicateLLMConfiguration(id, newName)
      const frontendConfig = toFrontendConfig(duplicated)

      set((state) => ({
        llmConfigs: [...state.llmConfigs, frontendConfig],
        isLoading: false,
      }))

      return duplicated.id
    } catch (error) {
      console.error('Failed to duplicate LLM configuration:', error)
      set({
        error: error instanceof Error ? error.message : 'Failed to duplicate configuration',
        isLoading: false,
      })
      throw error
    }
  },

  getActiveConfig: () => {
    const state = get()
    if (state.activeConfigId) {
      return state.llmConfigs.find(c => c.id === state.activeConfigId) || null
    }
    return state.llmConfigs.find(c => c.isActive) ||
           state.llmConfigs.find(c => c.isDefault) ||
           state.llmConfigs[0] || null
  },

  getDefaultConfig: () => {
    return get().llmConfigs.find(c => c.isDefault) || null
  },

  getActiveConfigId: () => {
    const config = get().getActiveConfig()
    return config?.id || null
  },
}))

// Hook to check if store is ready (hydrated)
export const useSettingsHydrated = () => useSettingsStore((state) => state._isHydrated)

