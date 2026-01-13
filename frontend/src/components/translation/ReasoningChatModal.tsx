import { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import {
  X,
  Send,
  Loader2,
  Lightbulb,
  Check,
  MessageSquare,
  Trash2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { api, ConversationMessage } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'
import { useSettingsStore } from '../../stores/settingsStore'

interface ReasoningChatModalProps {
  isOpen: boolean
  onClose: () => void
  translationId: string
  paragraphId: string
  originalText: string
  translatedText: string
  onTranslationUpdated: () => void
}

export function ReasoningChatModal({
  isOpen,
  onClose,
  translationId,
  originalText,
  translatedText,
  onTranslationUpdated,
}: ReasoningChatModalProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [inputMessage, setInputMessage] = useState('')
  const [isContextExpanded, setIsContextExpanded] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { getActiveConfig, getActiveConfigId } = useSettingsStore()
  const activeConfig = getActiveConfig()
  const configId = getActiveConfigId()
  const hasLLMConfig = !!(activeConfig && activeConfig.hasApiKey)

  // Start or fetch conversation
  const { data: conversation, isLoading: isLoadingConversation, refetch: refetchConversation } = useQuery({
    queryKey: ['conversation', translationId],
    queryFn: async () => {
      try {
        // Try to get existing conversation first
        return await api.getConversation(translationId)
      } catch {
        // If no conversation exists, start one
        return await api.startConversation(translationId, {
          config_id: configId || undefined,
        })
      }
    },
    enabled: isOpen && !!translationId && hasLLMConfig,
  })

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: (message: string) =>
      api.sendMessage(translationId, {
        message,
        config_id: configId || undefined,
      }),
    onSuccess: () => {
      refetchConversation()
      setInputMessage('')
    },
  })

  // Apply suggestion mutation - uses optimization prompt to integrate suggestion
  const applySuggestionMutation = useMutation({
    mutationFn: (messageId: string) =>
      api.applyTranslationSuggestion(translationId, messageId, {
        config_id: configId || undefined,
      }),
    onSuccess: () => {
      refetchConversation()
      queryClient.invalidateQueries({ queryKey: ['chapter'] })
      onTranslationUpdated()
    },
  })

  // Clear conversation mutation
  const clearConversationMutation = useMutation({
    mutationFn: () => api.clearConversation(translationId),
    onSuccess: () => {
      refetchConversation()
    },
  })

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages])

  const handleSendMessage = () => {
    if (inputMessage.trim() && !sendMessageMutation.isPending) {
      sendMessageMutation.mutate(inputMessage.trim())
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-3xl h-[80vh] mx-4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-blue-500" />
            {t('translate.discussTranslation')}
          </h3>
          <div className="flex items-center gap-2">
            {conversation?.messages && conversation.messages.length > 0 && (
              <button
                onClick={() => clearConversationMutation.mutate()}
                disabled={clearConversationMutation.isPending}
                className="p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded"
                title={t('translate.clearConversation')}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Context Bar */}
        <div className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 text-sm">
          <div className={`p-3 ${isContextExpanded ? 'max-h-[40vh] overflow-y-auto' : ''}`}>
            <div className={`grid grid-cols-2 gap-4 ${isContextExpanded ? '' : ''}`}>
              <div>
                <div className="text-gray-500 dark:text-gray-400 text-xs uppercase mb-1 font-medium">
                  {t('translate.original')}
                </div>
                <div className={`text-gray-700 dark:text-gray-300 ${isContextExpanded ? 'whitespace-pre-wrap' : 'line-clamp-2'}`}>
                  {originalText}
                </div>
              </div>
              <div>
                <div className="text-gray-500 dark:text-gray-400 text-xs uppercase mb-1 font-medium">
                  {t('translate.currentTranslation')}
                </div>
                <div className={`text-blue-700 dark:text-blue-400 ${isContextExpanded ? 'whitespace-pre-wrap' : 'line-clamp-2'}`}>
                  {conversation?.current_translation || translatedText}
                </div>
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsContextExpanded(!isContextExpanded)}
            className="w-full py-1.5 flex items-center justify-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border-t border-gray-200 dark:border-gray-700"
          >
            {isContextExpanded ? (
              <>
                <ChevronUp className="w-3 h-3" />
                {t('translate.collapseContext')}
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                {t('translate.expandContext')}
              </>
            )}
          </button>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {isLoadingConversation ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : !conversation?.messages || conversation.messages.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <Lightbulb className="w-8 h-8 mx-auto mb-2 text-amber-500" />
              <p>{t('translate.askAboutTranslation')}</p>
              <p className="text-sm mt-2 text-gray-400 dark:text-gray-500">
                {t('translate.chatExamples')}
              </p>
            </div>
          ) : (
            conversation.messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onApplySuggestion={() => applySuggestionMutation.mutate(msg.id)}
                isApplying={applySuggestionMutation.isPending}
                isLocked={conversation.is_locked}
                t={t}
              />
            ))
          )}
          {sendMessageMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          {sendMessageMutation.isError && (
            <div className="text-red-500 text-sm mb-2">
              {t('translate.messageFailed')}
            </div>
          )}
          <div className="flex gap-2">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('translate.typeYourQuestion')}
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={2}
              disabled={sendMessageMutation.isPending}
            />
            <button
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || sendMessageMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              {sendMessageMutation.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  onApplySuggestion,
  isApplying,
  isLocked,
  t,
}: {
  message: ConversationMessage
  onApplySuggestion: () => void
  isApplying: boolean
  isLocked: boolean
  t: (key: string) => string
}) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg p-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Show Apply button if there's a suggestion */}
        {message.suggested_translation && !message.suggestion_applied && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              {t('translate.suggestedTranslation')}:
            </div>
            <div className="text-sm bg-white dark:bg-gray-800 p-2 rounded mb-2 text-gray-800 dark:text-gray-200">
              {message.suggested_translation}
            </div>
            {isLocked ? (
              <div className="text-xs text-amber-600 dark:text-amber-400">
                {t('translate.cannotApplyLocked')}
              </div>
            ) : (
              <button
                onClick={onApplySuggestion}
                disabled={isApplying}
                className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:bg-gray-400 transition-colors"
              >
                {isApplying ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {t('translate.applyTranslation')}
              </button>
            )}
          </div>
        )}

        {message.suggestion_applied && (
          <div className="mt-2 text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <Check className="w-3 h-3" />
            {t('translate.suggestionApplied')}
          </div>
        )}
      </div>
    </div>
  )
}
