import { useMemo } from 'react'
import {
  User,
  Pen,
  MessageCircle,
  Users,
  BookOpen,
  Tag,
  List,
  FileText,
  Hash,
  Sparkles,
} from 'lucide-react'
import { useTranslation } from '../../stores/appStore'
import { safeTruncate } from '../../utils/text'

// Icon mapping for known field types
const FIELD_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  author_bio: User,
  author: User,
  writing_style: Pen,
  style: Pen,
  tone: MessageCircle,
  target_audience: Users,
  audience: Users,
  genre: BookOpen,
  genre_conventions: BookOpen,
  key_terminology: Tag,
  terminology: Tag,
  terms: Tag,
  glossary: Tag,
  themes: List,
  summary: FileText,
  overview: FileText,
}

// Known field i18n keys mapping
const FIELD_I18N_KEYS: Record<string, string> = {
  author_bio: 'analysis.authorBio',
  writing_style: 'analysis.writingStyle',
  tone: 'analysis.tone',
  target_audience: 'analysis.targetAudience',
  genre_conventions: 'analysis.genreConventions',
  key_terminology: 'analysis.keyTerminology',
  terminology: 'analysis.keyTerminology',
  themes: 'analysis.themes',
  summary: 'analysis.summary',
}

// Get icon for a field key
function getFieldIcon(key: string): React.ComponentType<{ className?: string }> {
  const lowerKey = key.toLowerCase()
  for (const [pattern, icon] of Object.entries(FIELD_ICONS)) {
    if (lowerKey.includes(pattern)) {
      return icon
    }
  }
  return Hash
}

// Format field name for display
function formatFieldName(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// Try to parse partial JSON and extract complete fields
function parsePartialJSON(text: string): {
  completeFields: Record<string, unknown>
  isInField: string | null
  partialValue: string
} {
  const result: Record<string, unknown> = {}
  let isInField: string | null = null
  let partialValue = ''

  // Clean up the text - remove markdown code blocks if present
  let cleanText = text.trim()
  if (cleanText.startsWith('```json')) {
    cleanText = cleanText.slice(7)
  } else if (cleanText.startsWith('```')) {
    cleanText = cleanText.slice(3)
  }
  if (cleanText.endsWith('```')) {
    cleanText = cleanText.slice(0, -3)
  }
  cleanText = cleanText.trim()

  // Try to parse the whole thing first
  try {
    const parsed = JSON.parse(cleanText)
    if (typeof parsed === 'object' && parsed !== null) {
      return { completeFields: parsed, isInField: null, partialValue: '' }
    }
  } catch {
    // Continue with partial parsing
  }

  // Find the last complete field and any partial content
  // We'll look for "key": value patterns
  const fieldPattern = /"([^"]+)":\s*(?:"[^"]*"|(\d+(?:\.\d+)?)|true|false|null|\[[^\]]*\]|\{[^}]*\})/g
  let lastIndex = 0
  let match

  // First pass: find all complete key-value pairs
  const tempText = cleanText
  while ((match = fieldPattern.exec(tempText)) !== null) {
    lastIndex = match.index + match[0].length
  }

  // Try to parse everything up to the last complete field
  if (lastIndex > 0) {
    // Find the start of the JSON object
    const objStart = cleanText.indexOf('{')
    if (objStart >= 0) {
      // Extract the complete portion
      let completeJson = cleanText.substring(objStart, lastIndex)

      // Clean up trailing commas and try to close the object
      completeJson = completeJson.replace(/,\s*$/, '')
      if (!completeJson.endsWith('}')) {
        completeJson += '}'
      }

      try {
        const parsed = JSON.parse(completeJson)
        if (typeof parsed === 'object' && parsed !== null) {
          Object.assign(result, parsed)
        }
      } catch {
        // Try a more aggressive approach - extract individual fields
        const singleFieldPattern = /"([^"]+)":\s*("(?:[^"\\]|\\.)*"|\d+(?:\.\d+)?|true|false|null|\[[\s\S]*?\])/g
        let fieldMatch
        while ((fieldMatch = singleFieldPattern.exec(cleanText)) !== null) {
          const [, key, value] = fieldMatch
          try {
            result[key] = JSON.parse(value)
          } catch {
            // Skip malformed values
          }
        }
      }
    }
  }

  // Check if we're currently in the middle of a field
  // Look for an unclosed string after the last complete field
  const remaining = cleanText.substring(lastIndex)
  const partialFieldMatch = remaining.match(/"([^"]+)":\s*"([^"]*)$/s)
  if (partialFieldMatch) {
    isInField = partialFieldMatch[1]
    partialValue = partialFieldMatch[2]
  } else {
    // Check for array being populated
    const partialArrayMatch = remaining.match(/"([^"]+)":\s*\[([^\]]*?)$/s)
    if (partialArrayMatch) {
      isInField = partialArrayMatch[1]
      partialValue = partialArrayMatch[2]
    }
  }

  return { completeFields: result, isInField, partialValue }
}

interface AnalysisStreamingPreviewProps {
  partialContent: string
  progress: number
  message: string
}

export function AnalysisStreamingPreview({
  partialContent,
  progress,
  message,
}: AnalysisStreamingPreviewProps) {
  const { t } = useTranslation()

  // Parse the partial content to extract fields
  const { completeFields, isInField, partialValue } = useMemo(
    () => parsePartialJSON(partialContent),
    [partialContent]
  )

  // Get sorted field entries (completed ones)
  const fieldEntries = useMemo(() => {
    return Object.entries(completeFields).filter(([key]) => !key.startsWith('_'))
  }, [completeFields])

  // Render a compact preview of a value
  const renderValuePreview = (value: unknown): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'string') {
      return value.length > 150 ? safeTruncate(value, 150) : value
    }
    if (Array.isArray(value)) {
      if (value.length === 0) return '[]'
      if (value.every(item => typeof item === 'string')) {
        return value.slice(0, 3).join(', ') + (value.length > 3 ? '...' : '')
      }
      return `[${value.length} items]`
    }
    if (typeof value === 'object') {
      const keys = Object.keys(value)
      return `{${keys.slice(0, 3).join(', ')}${keys.length > 3 ? '...' : ''}}`
    }
    return String(value)
  }

  return (
    <div className="space-y-4">
      {/* Progress indicator */}
      <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
        <Sparkles className="w-4 h-4 text-blue-500 animate-pulse" />
        <span>{message}</span>
        <span className="ml-auto font-mono text-xs">{progress}%</span>
      </div>

      {/* Extracted fields */}
      {fieldEntries.length > 0 && (
        <div className="space-y-2">
          {fieldEntries.map(([key, value]) => {
            const Icon = getFieldIcon(key)
            const i18nKey = FIELD_I18N_KEYS[key]
            const displayName = i18nKey ? t(i18nKey) : formatFieldName(key)
            const preview = renderValuePreview(value)

            return (
              <div
                key={key}
                className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 border border-gray-200 dark:border-gray-600"
              >
                <div className="flex items-start gap-2">
                  <Icon className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {displayName}
                      </span>
                      <span className="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-1.5 py-0.5 rounded">
                        {t('common.complete') || 'Complete'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                      {preview}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Currently streaming field */}
      {isInField && (
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-200 dark:border-blue-700">
          <div className="flex items-start gap-2">
            {(() => {
              const Icon = getFieldIcon(isInField)
              return <Icon className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0 animate-pulse" />
            })()}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {FIELD_I18N_KEYS[isInField] ? t(FIELD_I18N_KEYS[isInField]) : formatFieldName(isInField)}
                </span>
                <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 rounded flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
                  {t('analysis.streaming') || 'Streaming...'}
                </span>
              </div>
              {partialValue && (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {safeTruncate(partialValue, 200)}
                  <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse align-middle" />
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty state - show skeleton when nothing parsed yet */}
      {fieldEntries.length === 0 && !isInField && partialContent.length > 0 && (
        <div className="space-y-2">
          {/* Show 2 skeleton fields */}
          {[1, 2].map((i) => (
            <div
              key={i}
              className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 border border-gray-200 dark:border-gray-600 animate-pulse"
            >
              <div className="flex items-start gap-2">
                <div className="w-4 h-4 bg-gray-300 dark:bg-gray-600 rounded mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-24 mb-2" />
                  <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Character count indicator */}
      <div className="text-xs text-gray-400 dark:text-gray-500 text-right">
        {partialContent.length.toLocaleString()} {t('analysis.characters') || 'characters'}
      </div>
    </div>
  )
}

