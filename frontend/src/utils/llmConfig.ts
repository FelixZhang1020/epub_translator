import { LLMConfig } from '../stores/settingsStore'
import { ModelInfo } from '../services/api/client'

// Provider order (same as PROVIDER_CONFIG in backend)
const PROVIDER_ORDER: Record<string, number> = {
  openai: 0,
  anthropic: 1,
  gemini: 2,
  qwen: 3,
  deepseek: 4,
  ollama: 5,
  openrouter: 6,
}

/**
 * Sort LLM configs by: default first, then by provider order, then by price (high to low)
 * @param configs - Array of LLM configurations to sort
 * @param models - Array of model info for price lookup
 * @returns Sorted array of LLM configurations
 */
export function sortLLMConfigs(configs: LLMConfig[], models?: ModelInfo[]): LLMConfig[] {
  if (!configs.length) return []

  // Create a map of model prices for quick lookup
  const modelPriceMap = new Map<string, number>()
  if (models) {
    for (const m of models) {
      modelPriceMap.set(m.id, m.input_cost_per_million)
    }
  }

  return [...configs].sort((a, b) => {
    // Default first
    if (a.isDefault !== b.isDefault) {
      return a.isDefault ? -1 : 1
    }

    // Then by provider order
    const providerA = PROVIDER_ORDER[a.provider] ?? 99
    const providerB = PROVIDER_ORDER[b.provider] ?? 99
    if (providerA !== providerB) {
      return providerA - providerB
    }

    // Then by price (high to low)
    const priceA = modelPriceMap.get(a.model) ?? 0
    const priceB = modelPriceMap.get(b.model) ?? 0
    return priceB - priceA
  })
}

