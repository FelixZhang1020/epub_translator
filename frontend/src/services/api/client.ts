import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
})

export interface Project {
  id: string
  name: string
  author: string | null
  status: string
  total_chapters: number
  total_paragraphs: number
  created_at: string
}

export interface Chapter {
  id: string
  chapter_number: number
  title: string | null
  paragraph_count: number
  word_count: number
}

export interface Paragraph {
  id: string
  paragraph_number: number
  original_text: string
  html_tag: string
  translated_text: string | null
  translation_id: string | null
  translation_provider: string | null
  is_manual_edit: boolean
}

export interface ChapterImage {
  src: string
  url?: string  // Full API URL for fetching the image
  alt?: string
  caption?: string
  position: number
  xpath?: string
}

export interface ChapterContent {
  id: string
  chapter_number: number
  title: string | null
  paragraphs: Paragraph[]
  images?: ChapterImage[]
}

export interface TocItem {
  title: string | null
  href: string | null
  chapter_id: string | null
  chapter_number: number | null
  paragraph_count: number | null
  children: TocItem[]
}

export interface TranslationTask {
  id: string
  mode: string
  provider: string
  model: string
  status: string
  progress: number
  completed_paragraphs: number
  total_paragraphs: number
  created_at: string
}

// New LiteLLM types
export interface ProviderInfo {
  name: string
  display_name: string
  api_key_env_var: string
  has_api_key: boolean
  model_count: number
  manual_model: boolean  // If true, user enters model name manually
}

export interface ModelInfo {
  id: string
  provider: string
  display_name: string
  input_cost_per_million: number  // Cost per 1M input tokens in USD
  output_cost_per_million: number // Cost per 1M output tokens in USD
  max_tokens: number | null
  context_window: number | null
}

export interface CostEstimate {
  input_tokens: number
  output_tokens_estimate: number
  input_cost: number
  output_cost_estimate: number
  total_cost_estimate: number
  model: string
}

// Legacy type (for backwards compatibility)
export interface Provider {
  name: string
  display_name: string
  models: { id: string; name: string; context_window: number }[]
}

export interface StartTranslationRequest {
  project_id: string
  mode: string
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  provider?: string
  model?: string
  api_key?: string
  // Translation options
  author_background?: string
  custom_prompts?: string[]
  chapters?: number[]  // Chapter numbers to translate, undefined = all chapters
  custom_system_prompt?: string
  custom_user_prompt?: string
}

// Workflow types
export interface WorkflowStatus {
  project_id: string
  current_step: string
  has_reference_epub: boolean
  analysis_completed: boolean
  translation_completed: boolean
  proofreading_completed: boolean
  analysis_progress?: {
    exists: boolean
    confirmed: boolean
  }
  translation_progress?: {
    has_task: boolean
    task_id?: string
    status?: string
    progress: number
    completed_paragraphs: number
    total_paragraphs: number
  }
  proofreading_progress?: {
    has_session: boolean
    session_id?: string
    status?: string
    round_number: number
    progress: number
    pending_suggestions: number
  }
}

export interface ResumePosition {
  project_id: string
  recommended_step: string
  reason: string
  current_step: string
}

// Reference EPUB types
export interface ReferenceEPUB {
  id: string
  project_id: string
  filename: string
  language: string
  epub_title: string | null
  epub_author: string | null
  total_chapters: number
  total_paragraphs: number
  auto_matched: boolean
  match_quality: number | null
  created_at: string
}

export interface ParagraphMatch {
  id: string
  source_paragraph_id: string
  source_text: string | null
  reference_text: string
  match_type: string
  confidence: number | null
  user_verified: boolean
  user_corrected: boolean
}

export interface MatchingStats {
  matched: number
  unmatched: number
  average_confidence: number
}

export interface ReferenceChapter {
  chapter_number: number
  title: string | null
  paragraph_count: number
}

export interface ReferenceChapterContent {
  chapter_number: number
  title: string | null
  paragraphs: { paragraph_number: number; text: string }[]
}

export interface ReferenceSearchResultItem {
  chapter_number: number
  chapter_title: string | null
  paragraph_number: number
  text: string
  match_start: number
  match_end: number
}

export interface ReferenceSearchResponse {
  query: string
  total_results: number
  results: ReferenceSearchResultItem[]
}

// Translation Reasoning types
export interface TranslationReasoning {
  translation_id: string
  reasoning_text: string
  provider: string
  model: string
}

export interface ReasoningRequest {
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  model?: string
  api_key?: string
  provider?: string
}

// Translation Conversation types
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  suggested_translation: string | null
  suggestion_applied: boolean
  tokens_used: number
  created_at: string
}

export interface Conversation {
  id: string
  translation_id: string
  original_text: string
  initial_translation: string
  current_translation: string
  messages: ConversationMessage[]
  provider: string
  model: string
  total_tokens_used: number
  created_at: string
}

export interface StartConversationRequest {
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  model?: string
  api_key?: string
  provider?: string
}

export interface SendMessageRequest {
  message: string
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  model?: string
  api_key?: string
  provider?: string
}

export interface ApplyTranslationRequest {
  message_id: string
}

// Proofreading types
export interface ProofreadingSession {
  id: string
  project_id: string
  provider: string
  model: string
  status: string
  round_number: number
  progress: number
  total_paragraphs: number
  completed_paragraphs: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface ProofreadingSuggestion {
  id: string
  paragraph_id: string
  original_text: string | null
  original_translation: string
  suggested_translation: string
  explanation: string | null
  status: string
  user_modified_text: string | null
  created_at: string
}

export interface StartProofreadingRequest {
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  model?: string
  api_key?: string
  provider?: string
  // Proofreading options
  chapter_ids?: string[]
  custom_system_prompt?: string
  custom_user_prompt?: string
}

export interface UpdateSuggestionRequest {
  action: string // "accept", "reject", "modify"
  modified_text?: string
}

// Book Analysis types - dynamic structure
export interface BookAnalysis {
  id: string
  project_id: string
  raw_analysis: Record<string, unknown> | null  // Dynamic analysis data
  user_confirmed: boolean
  provider: string | null
  model: string | null
  created_at: string
  confirmed_at: string | null
}

export interface StartAnalysisRequest {
  // Option 1: Use stored config (recommended)
  config_id?: string
  // Option 2: Direct parameters (for backwards compatibility)
  model?: string
  api_key?: string
  provider?: string
  // Analysis options
  sample_count?: number
  custom_system_prompt?: string
  custom_user_prompt?: string
}

export interface UpdateAnalysisRequest {
  updates: Record<string, unknown>  // Dynamic fields to update
  confirm?: boolean
}

// Analysis progress event for streaming
export interface AnalysisProgressEvent {
  step: 'loading' | 'sampling' | 'building_prompt' | 'analyzing' | 'parsing' | 'saving' | 'complete' | 'error' | 'warning'
  progress: number  // 0-100
  message: string
  partial_content?: string  // Partial LLM response during analysis
  analysis_id?: string  // Set on complete
  raw_analysis?: Record<string, unknown>  // Set on complete
}

// LLM Configuration types (stored in backend)
export interface LLMConfiguration {
  id: string
  name: string
  provider: string
  model: string
  base_url: string | null
  temperature: number
  is_default: boolean
  is_active: boolean
  has_api_key: boolean
  masked_api_key: string  // First 4 + last 4 chars for display
  created_at: string
  updated_at: string
  last_used_at: string | null
}

export interface CreateLLMConfigRequest {
  name: string
  provider: string
  model: string
  api_key: string
  base_url?: string
  temperature?: number
  is_default?: boolean
  is_active?: boolean
}

export interface UpdateLLMConfigRequest {
  name?: string
  provider?: string
  model?: string
  api_key?: string
  base_url?: string
  temperature?: number
  is_default?: boolean
  is_active?: boolean
}

export interface ActiveLLMConfig {
  id: string | null
  name: string | null
  provider: string
  model: string
  has_api_key: boolean
  source: 'database' | 'environment'
}

// Prompt types (legacy file-based)
export interface PromptTemplate {
  type: string
  system_prompt: string
  user_prompt_template: string
  variables: string[]
  last_modified: string
}

export interface PromptPreview {
  system_prompt: string
  user_prompt: string
}

// Prompt Template types (database-backed)
export interface PromptTemplateDB {
  id: string
  name: string
  description: string | null
  category: string
  system_prompt: string
  default_user_prompt: string | null
  variables: string[] | null
  is_builtin: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface CreatePromptTemplateRequest {
  name: string
  description?: string
  category: string
  system_prompt: string
  default_user_prompt?: string
  variables?: string[]
  is_default?: boolean
}

export interface UpdatePromptTemplateRequest {
  name?: string
  description?: string
  system_prompt?: string
  default_user_prompt?: string
  variables?: string[]
  is_default?: boolean
}

export interface ProjectPromptConfig {
  id: string
  project_id: string
  category: string
  template_id: string | null
  custom_system_prompt: string | null
  custom_user_prompt: string | null
  use_custom_system: boolean
  use_custom_user: boolean
  created_at: string
  updated_at: string
  template?: PromptTemplateDB | null
}

export interface ProjectPromptConfigRequest {
  template_id?: string | null
  custom_system_prompt?: string
  custom_user_prompt?: string
  use_custom_system?: boolean
  use_custom_user?: boolean
}

// Project Variables types
export interface ProjectVariable {
  id: string
  project_id: string
  name: string
  value: string
  value_type: 'string' | 'number' | 'boolean' | 'json'
  description: string | null
  created_at: string
  updated_at: string
}

export interface CreateProjectVariableRequest {
  name: string
  value: string
  value_type?: 'string' | 'number' | 'boolean' | 'json'
  description?: string
}

export interface UpdateProjectVariableRequest {
  value?: string
  value_type?: 'string' | 'number' | 'boolean' | 'json'
  description?: string
}

export interface AvailableVariable {
  name: string
  description: string
  current_value: unknown
  type?: string
  stages?: string[]
  editable?: boolean
}

export interface AvailableVariablesResponse {
  project: AvailableVariable[]
  content: AvailableVariable[]
  pipeline: AvailableVariable[]
  derived: AvailableVariable[]
  user: AvailableVariable[]
}

export const api = {
  // Projects
  async getProjects(): Promise<Project[]> {
    const { data } = await client.get('/projects')
    return data
  },

  async getProject(id: string): Promise<Project> {
    const { data } = await client.get(`/projects/${id}`)
    return data
  },

  async uploadEpub(file: File): Promise<{ project_id: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await client.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async deleteProject(id: string): Promise<void> {
    await client.delete(`/projects/${id}`)
  },

  // Translation
  async startTranslation(request: StartTranslationRequest): Promise<{ task_id: string }> {
    const { data } = await client.post('/translation/start', request)
    return data
  },

  async getTranslationStatus(taskId: string): Promise<TranslationTask> {
    const { data } = await client.get(`/translation/status/${taskId}`)
    return data
  },

  async pauseTranslation(taskId: string): Promise<void> {
    await client.post(`/translation/pause/${taskId}`)
  },

  async resumeTranslation(taskId: string, options: { config_id?: string; api_key?: string }): Promise<void> {
    await client.post(`/translation/resume/${taskId}`, options)
  },

  async getProjectTasks(projectId: string): Promise<TranslationTask[]> {
    const { data } = await client.get(`/translation/tasks/${projectId}`)
    return data
  },

  // Preview
  async getChapters(projectId: string): Promise<Chapter[]> {
    const { data } = await client.get(`/preview/${projectId}/chapters`)
    return data
  },

  async getToc(projectId: string): Promise<TocItem[]> {
    const { data } = await client.get(`/preview/${projectId}/toc`)
    return data
  },

  async getChapterContent(projectId: string, chapterId: string): Promise<ChapterContent> {
    const { data } = await client.get(`/preview/${projectId}/chapter/${chapterId}`)
    return data
  },

  async updateTranslation(paragraphId: string, translatedText: string): Promise<void> {
    await client.put(`/preview/paragraph/${paragraphId}`, {
      translated_text: translatedText,
    })
  },

  // Export
  async exportEpub(projectId: string): Promise<Blob> {
    const { data } = await client.post(`/export/${projectId}`, null, {
      responseType: 'blob',
    })
    return data
  },

  // LLM Settings (New LiteLLM endpoints)
  async getProviders(): Promise<ProviderInfo[]> {
    const { data } = await client.get('/llm/providers')
    return data
  },

  async getModels(provider?: string): Promise<ModelInfo[]> {
    const { data } = await client.get('/llm/models', {
      params: provider ? { provider } : undefined,
    })
    return data
  },

  async getProviderModels(provider: string): Promise<ModelInfo[]> {
    const { data } = await client.get(`/llm/models/${provider}`)
    return data
  },

  async testConnection(request: {
    model: string
    api_key?: string
  }): Promise<{ success: boolean; message: string; model: string }> {
    const { data } = await client.post('/llm/test', request)
    return data
  },

  async estimateCost(request: {
    model: string
    text: string
    output_ratio?: number
  }): Promise<CostEstimate> {
    const { data } = await client.post('/llm/estimate-cost', request)
    return data
  },

  // LLM Configurations (stored in backend database)
  async getLLMConfigurations(): Promise<LLMConfiguration[]> {
    const { data } = await client.get('/llm/configurations')
    return data
  },

  async getActiveLLMConfiguration(): Promise<ActiveLLMConfig> {
    const { data } = await client.get('/llm/configurations/active')
    return data
  },

  async getLLMConfiguration(configId: string): Promise<LLMConfiguration> {
    const { data } = await client.get(`/llm/configurations/${configId}`)
    return data
  },

  async createLLMConfiguration(request: CreateLLMConfigRequest): Promise<LLMConfiguration> {
    const { data } = await client.post('/llm/configurations', request)
    return data
  },

  async updateLLMConfiguration(configId: string, request: UpdateLLMConfigRequest): Promise<LLMConfiguration> {
    const { data } = await client.put(`/llm/configurations/${configId}`, request)
    return data
  },

  async deleteLLMConfiguration(configId: string): Promise<void> {
    await client.delete(`/llm/configurations/${configId}`)
  },

  async activateLLMConfiguration(configId: string): Promise<{ status: string; id: string }> {
    const { data } = await client.post(`/llm/configurations/${configId}/activate`)
    return data
  },

  async testLLMConfiguration(configId: string): Promise<{ success: boolean; message: string; config_id: string; model?: string }> {
    const { data } = await client.post(`/llm/configurations/${configId}/test`)
    return data
  },

  async duplicateLLMConfiguration(configId: string, newName: string): Promise<LLMConfiguration> {
    const { data } = await client.post(`/llm/configurations/${configId}/duplicate`, { new_name: newName })
    return data
  },

  // Workflow
  async getWorkflowStatus(projectId: string): Promise<WorkflowStatus> {
    const { data } = await client.get(`/workflow/${projectId}/status`)
    return data
  },

  async updateWorkflowStep(projectId: string, step: string): Promise<{ project_id: string; current_step: string }> {
    const { data } = await client.put(`/workflow/${projectId}/step`, { step })
    return data
  },

  async getResumePosition(projectId: string): Promise<ResumePosition> {
    const { data } = await client.get(`/workflow/${projectId}/resume`)
    return data
  },

  // Book Analysis
  async startAnalysis(projectId: string, request: StartAnalysisRequest): Promise<BookAnalysis> {
    const { data } = await client.post(`/analysis/${projectId}/start`, request)
    return data
  },

  /**
   * Start analysis with streaming progress updates via SSE.
   * Returns an EventSource that emits progress events.
   */
  startAnalysisStream(
    projectId: string,
    request: StartAnalysisRequest,
    onProgress: (event: AnalysisProgressEvent) => void,
    onComplete: (analysis: Record<string, unknown>) => void,
    onError: (error: string) => void
  ): { abort: () => void } {
    const controller = new AbortController()

    // Build request body
    const body = JSON.stringify({
      config_id: request.config_id,
      model: request.model,
      api_key: request.api_key,
      provider: request.provider,
      sample_count: request.sample_count ?? 20,
      custom_system_prompt: request.custom_system_prompt,
      custom_user_prompt: request.custom_user_prompt,
    })

    // Use fetch for SSE with POST (use same base path as axios client)
    fetch(`/api/v1/analysis/${projectId}/start-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Parse SSE events from buffer
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6)) as AnalysisProgressEvent
                onProgress(event)

                if (event.step === 'complete' && event.raw_analysis) {
                  onComplete(event.raw_analysis)
                } else if (event.step === 'error') {
                  onError(event.message)
                }
              } catch {
                // Ignore parse errors for incomplete JSON
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(err.message || 'Stream connection failed')
        }
      })

    return {
      abort: () => controller.abort(),
    }
  },

  async getAnalysis(projectId: string): Promise<BookAnalysis> {
    const { data } = await client.get(`/analysis/${projectId}`)
    return data
  },

  async updateAnalysis(projectId: string, request: UpdateAnalysisRequest): Promise<BookAnalysis> {
    const { data } = await client.put(`/analysis/${projectId}`, request)
    return data
  },

  async regenerateAnalysisField(projectId: string, field: string, model: string, apiKey?: string): Promise<BookAnalysis> {
    const { data } = await client.post(`/analysis/${projectId}/regenerate`, {
      field,
      model,
      api_key: apiKey,
    })
    return data
  },

  // Reference EPUB
  async uploadReferenceEpub(projectId: string, file: File): Promise<ReferenceEPUB> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await client.post(`/reference/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async getReferenceEpub(projectId: string): Promise<ReferenceEPUB> {
    const { data } = await client.get(`/reference/${projectId}`)
    return data
  },

  async autoMatchParagraphs(projectId: string): Promise<MatchingStats> {
    const { data } = await client.post(`/reference/${projectId}/match`)
    return data
  },

  async getMatches(projectId: string, chapterId?: string, limit?: number, offset?: number): Promise<ParagraphMatch[]> {
    const { data } = await client.get(`/reference/${projectId}/matches`, {
      params: { chapter_id: chapterId, limit, offset },
    })
    return data
  },

  async updateMatch(projectId: string, matchId: string, referenceText: string): Promise<ParagraphMatch> {
    const { data } = await client.put(`/reference/${projectId}/match/${matchId}`, {
      reference_text: referenceText,
    })
    return data
  },

  async verifyMatch(projectId: string, matchId: string): Promise<{ status: string; match_id: string }> {
    const { data } = await client.post(`/reference/${projectId}/match/${matchId}/verify`)
    return data
  },

  async deleteReferenceEpub(projectId: string): Promise<void> {
    await client.delete(`/reference/${projectId}`)
  },

  async getReferenceChapters(projectId: string): Promise<ReferenceChapter[]> {
    const { data } = await client.get(`/reference/${projectId}/chapters`)
    return data
  },

  async getReferenceChapterContent(projectId: string, chapterNumber: number): Promise<ReferenceChapterContent> {
    const { data } = await client.get(`/reference/${projectId}/chapter/${chapterNumber}`)
    return data
  },

  async searchReferenceContent(projectId: string, query: string, limit?: number): Promise<ReferenceSearchResponse> {
    const { data } = await client.get(`/reference/${projectId}/search`, {
      params: { q: query, limit },
    })
    return data
  },

  // Translation Reasoning
  async requestReasoning(translationId: string, request: ReasoningRequest): Promise<TranslationReasoning> {
    const { data } = await client.post(`/translation/reasoning/${translationId}`, request)
    return data
  },

  async getReasoning(translationId: string): Promise<TranslationReasoning> {
    const { data } = await client.get(`/translation/reasoning/${translationId}`)
    return data
  },

  // Translation Conversation
  async startConversation(translationId: string, request: StartConversationRequest): Promise<Conversation> {
    const { data } = await client.post(`/translation/conversation/${translationId}/start`, request)
    return data
  },

  async getConversation(translationId: string): Promise<Conversation> {
    const { data } = await client.get(`/translation/conversation/${translationId}`)
    return data
  },

  async sendMessage(translationId: string, request: SendMessageRequest): Promise<ConversationMessage> {
    const { data } = await client.post(`/translation/conversation/${translationId}/message`, request)
    return data
  },

  async applyTranslationSuggestion(translationId: string, messageId: string): Promise<{ status: string; new_translation: string }> {
    const { data } = await client.post(`/translation/conversation/${translationId}/apply`, { message_id: messageId })
    return data
  },

  async clearConversation(translationId: string): Promise<void> {
    await client.delete(`/translation/conversation/${translationId}`)
  },

  // Retranslate single paragraph
  async retranslateParagraph(paragraphId: string, request: {
    config_id?: string
    model?: string
    api_key?: string
    provider?: string
    mode?: string
  }): Promise<{
    paragraph_id: string
    translation_id: string
    translated_text: string
    provider: string
    model: string
    tokens_used: number
  }> {
    const { data } = await client.post(`/translation/retranslate/${paragraphId}`, request)
    return data
  },

  // Clear all translations for a chapter
  async clearChapterTranslations(chapterId: string): Promise<{ deleted_count: number; chapter_id: string }> {
    const { data } = await client.delete(`/translation/chapter/${chapterId}`)
    return data
  },

  // Proofreading
  async startProofreading(projectId: string, request: StartProofreadingRequest): Promise<ProofreadingSession> {
    const { data } = await client.post(`/proofreading/${projectId}/start`, request)
    return data
  },

  async getProofreadingSession(sessionId: string): Promise<ProofreadingSession> {
    const { data } = await client.get(`/proofreading/session/${sessionId}`)
    return data
  },

  async listProofreadingSessions(projectId: string): Promise<ProofreadingSession[]> {
    const { data } = await client.get(`/proofreading/${projectId}/sessions`)
    return data
  },

  async getProofreadingSuggestions(sessionId: string, status?: string, limit?: number, offset?: number): Promise<ProofreadingSuggestion[]> {
    const { data } = await client.get(`/proofreading/${sessionId}/suggestions`, {
      params: { status, limit, offset },
    })
    return data
  },

  async updateSuggestion(suggestionId: string, request: UpdateSuggestionRequest): Promise<ProofreadingSuggestion> {
    const { data } = await client.put(`/proofreading/suggestion/${suggestionId}`, request)
    return data
  },

  async applySuggestions(sessionId: string): Promise<{ applied: number; total: number }> {
    const { data } = await client.post(`/proofreading/${sessionId}/apply`)
    return data
  },

  async getPendingSuggestionsCount(projectId: string): Promise<{ pending_count: number }> {
    const { data } = await client.get(`/proofreading/${projectId}/pending-count`)
    return data
  },

  // Prompts
  async getPromptTemplate(promptType: string): Promise<PromptTemplate> {
    const { data } = await client.get(`/prompts/${promptType}`)
    return data
  },

  async updatePromptTemplate(promptType: string, systemPrompt: string, userPrompt: string): Promise<PromptTemplate> {
    const { data } = await client.put(`/prompts/${promptType}`, {
      system_prompt: systemPrompt,
      user_prompt: userPrompt,
    })
    return data
  },

  async previewPrompt(promptType: string, variables: Record<string, unknown>, customSystemPrompt?: string, customUserPrompt?: string): Promise<PromptPreview> {
    const { data } = await client.post(`/prompts/${promptType}/preview`, {
      variables,
      custom_system_prompt: customSystemPrompt,
      custom_user_prompt: customUserPrompt,
    })
    return data
  },

  async listPromptTypes(): Promise<{ types: string[] }> {
    const { data } = await client.get('/prompts')
    return data
  },

  // Prompt Templates (database-backed)
  async getPromptTemplates(category?: string): Promise<PromptTemplateDB[]> {
    const { data } = await client.get('/prompts/templates', {
      params: category ? { category } : undefined,
    })
    return data
  },

  async getPromptTemplateById(templateId: string): Promise<PromptTemplateDB> {
    const { data } = await client.get(`/prompts/templates/${templateId}`)
    return data
  },

  async createPromptTemplate(request: CreatePromptTemplateRequest): Promise<PromptTemplateDB> {
    const { data } = await client.post('/prompts/templates', request)
    return data
  },

  async updatePromptTemplateById(templateId: string, request: UpdatePromptTemplateRequest): Promise<PromptTemplateDB> {
    const { data } = await client.put(`/prompts/templates/${templateId}`, request)
    return data
  },

  async deletePromptTemplate(templateId: string): Promise<void> {
    await client.delete(`/prompts/templates/${templateId}`)
  },

  async syncBuiltinTemplates(): Promise<{ synced: number; templates: PromptTemplateDB[] }> {
    const { data } = await client.post('/prompts/sync-builtin')
    return data
  },

  // Project Prompt Configurations
  async getProjectPromptConfigs(projectId: string): Promise<ProjectPromptConfig[]> {
    const { data } = await client.get(`/prompts/projects/${projectId}`)
    return data
  },

  async getProjectPromptConfig(projectId: string, category: string): Promise<ProjectPromptConfig> {
    const { data } = await client.get(`/prompts/projects/${projectId}/${category}`)
    return data
  },

  async updateProjectPromptConfig(projectId: string, category: string, request: ProjectPromptConfigRequest): Promise<ProjectPromptConfig> {
    const { data } = await client.put(`/prompts/projects/${projectId}/${category}`, request)
    return data
  },

  async deleteProjectPromptConfig(projectId: string, category: string): Promise<void> {
    await client.delete(`/prompts/projects/${projectId}/${category}`)
  },

  // Project Variables
  async getProjectVariables(projectId: string): Promise<ProjectVariable[]> {
    const { data } = await client.get(`/prompts/projects/${projectId}/variables`)
    return data
  },

  async createProjectVariable(projectId: string, request: CreateProjectVariableRequest): Promise<ProjectVariable> {
    const { data } = await client.post(`/prompts/projects/${projectId}/variables`, request)
    return data
  },

  async updateProjectVariable(projectId: string, variableName: string, request: UpdateProjectVariableRequest): Promise<ProjectVariable> {
    const { data } = await client.put(`/prompts/projects/${projectId}/variables/${variableName}`, request)
    return data
  },

  async deleteProjectVariable(projectId: string, variableName: string): Promise<void> {
    await client.delete(`/prompts/projects/${projectId}/variables/${variableName}`)
  },

  // Available Variables
  async getAvailableVariables(projectId: string, stage?: string): Promise<AvailableVariablesResponse> {
    const params = stage ? { stage } : {}
    const { data } = await client.get(`/prompts/projects/${projectId}/available-variables`, { params })
    return data
  },
}
