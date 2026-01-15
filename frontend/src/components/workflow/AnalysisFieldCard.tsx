import { useState, useCallback, useMemo } from 'react'
import {
  ChevronDown,
  ChevronUp,
  User,
  Pen,
  MessageCircle,
  Users,
  BookOpen,
  Tag,
  List,
  FileText,
  Hash,
} from 'lucide-react'
import { useTranslation } from '../../stores/appStore'
import { safeTruncate, safeTruncateJson } from '../../utils/text'

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

// Detect if value is a terminology/glossary table
function isTerminologyTable(value: unknown): value is Array<Record<string, string>> {
  if (!Array.isArray(value) || value.length === 0) return false
  const first = value[0]
  if (typeof first !== 'object' || first === null) return false
  const keys = Object.keys(first)
  // Check if it looks like terminology entries (has 2-3 string fields)
  return keys.length >= 2 && keys.length <= 4 &&
    keys.every(k => typeof first[k] === 'string')
}

// Detect if value is a simple string array
function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

interface AnalysisFieldCardProps {
  fieldKey: string
  value: unknown
  onChange: (key: string, value: string) => void
  i18nKey?: string
}

export function AnalysisFieldCard({
  fieldKey,
  value,
  onChange,
  i18nKey
}: AnalysisFieldCardProps) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState('')

  const Icon = getFieldIcon(fieldKey)
  const displayName = i18nKey ? t(i18nKey) : formatFieldName(fieldKey)

  // Determine the type of value and how to render it
  const valueType = useMemo(() => {
    if (value === null || value === undefined) return 'empty'
    if (typeof value === 'string') return 'string'
    if (isTerminologyTable(value)) return 'terminology'
    if (isStringArray(value)) return 'stringArray'
    if (Array.isArray(value)) return 'array'
    if (typeof value === 'object') return 'object'
    return 'primitive'
  }, [value])

  // Get preview text for collapsed state
  const previewText = useMemo(() => {
    if (valueType === 'empty') return t('analysis.noData') || 'No data'
    if (valueType === 'string') {
      const str = value as string
      return str.length > 100 ? safeTruncate(str, 100) : str
    }
    if (valueType === 'stringArray') {
      const arr = value as string[]
      return `${arr.length} ${t('common.items') || 'items'}`
    }
    if (valueType === 'terminology') {
      const arr = value as Array<Record<string, string>>
      return `${arr.length} ${t('analysis.terms') || 'terms'}`
    }
    if (valueType === 'array' || valueType === 'object') {
      return safeTruncateJson(value, 80)
    }
    return String(value)
  }, [value, valueType, t])

  // Handle entering edit mode
  const handleStartEdit = useCallback(() => {
    if (valueType === 'string') {
      setEditValue(value as string)
    } else {
      setEditValue(JSON.stringify(value, null, 2))
    }
    setIsEditing(true)
  }, [value, valueType])

  // Handle saving edit
  const handleSaveEdit = useCallback(() => {
    onChange(fieldKey, editValue)
    setIsEditing(false)
  }, [fieldKey, editValue, onChange])

  // Handle cancel edit
  const handleCancelEdit = useCallback(() => {
    setIsEditing(false)
    setEditValue('')
  }, [])

  // Render terminology table
  const renderTerminologyTable = (data: Array<Record<string, string>>) => {
    if (data.length === 0) return null
    const columns = Object.keys(data[0])

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                >
                  {formatFieldName(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                {columns.map((col) => (
                  <td
                    key={col}
                    className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100"
                  >
                    {row[col]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // Render string array as list
  const renderStringArray = (data: string[]) => {
    return (
      <ul className="space-y-1.5">
        {data.map((item, idx) => (
          <li
            key={idx}
            className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300"
          >
            <span className="text-gray-400 dark:text-gray-500 mt-0.5">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    )
  }

  // Render long text content
  const renderTextContent = (text: string) => {
    // Split by paragraphs for better readability
    const paragraphs = text.split(/\n\n+/).filter(p => p.trim())

    return (
      <div className="space-y-3">
        {paragraphs.map((para, idx) => (
          <p key={idx} className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {para}
          </p>
        ))}
      </div>
    )
  }

  // Render nested object with better formatting
  const renderNestedValue = (val: unknown, depth: number = 0): React.ReactNode => {
    if (val === null || val === undefined) {
      return <span className="text-gray-400 italic">-</span>
    }

    if (typeof val === 'string') {
      // Multi-line strings
      if (val.includes('\n')) {
        return (
          <div className="space-y-1">
            {val.split('\n').map((line, i) => (
              <p key={i} className="text-sm text-gray-700 dark:text-gray-300">{line}</p>
            ))}
          </div>
        )
      }
      return <span className="text-gray-700 dark:text-gray-300">{val}</span>
    }

    if (typeof val === 'number' || typeof val === 'boolean') {
      return <span className="text-blue-600 dark:text-blue-400">{String(val)}</span>
    }

    if (Array.isArray(val)) {
      // Simple string array - render as bulleted list
      if (val.every(item => typeof item === 'string')) {
        return (
          <ul className="space-y-1.5 mt-1">
            {val.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <span className="text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0">•</span>
                <span className="text-gray-700 dark:text-gray-300">{item}</span>
              </li>
            ))}
          </ul>
        )
      }
      // Array of objects - render each as a card
      if (val.every(item => typeof item === 'object' && item !== null)) {
        return (
          <div className="space-y-2 mt-1">
            {val.map((item, idx) => (
              <div key={idx} className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
                {renderNestedValue(item, depth + 1)}
              </div>
            ))}
          </div>
        )
      }
      // Mixed array - fallback to JSON
      return (
        <pre className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded p-2 overflow-x-auto">
          {JSON.stringify(val, null, 2)}
        </pre>
      )
    }

    if (typeof val === 'object') {
      const entries = Object.entries(val as Record<string, unknown>)
      return (
        <div className={`space-y-3 ${depth > 0 ? '' : 'divide-y divide-gray-100 dark:divide-gray-700'}`}>
          {entries.map(([key, subVal]) => (
            <div key={key} className={depth > 0 ? '' : 'pt-3 first:pt-0'}>
              <div className="flex items-start gap-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide min-w-[120px] flex-shrink-0 pt-0.5">
                  {formatFieldName(key)}
                </span>
                <div className="flex-1 min-w-0">
                  {renderNestedValue(subVal, depth + 1)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )
    }

    return <span className="text-gray-700 dark:text-gray-300">{String(val)}</span>
  }

  // Render the main content
  const renderContent = () => {
    if (isEditing) {
      return (
        <div className="space-y-3">
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            rows={valueType === 'string' ? 4 : 8}
            className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
              valueType !== 'string' ? 'font-mono text-sm' : ''
            }`}
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={handleCancelEdit}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              {t('common.save')}
            </button>
          </div>
        </div>
      )
    }

    switch (valueType) {
      case 'empty':
        return (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">
            {t('analysis.noData') || 'No data'}
          </p>
        )
      case 'string':
        return renderTextContent(value as string)
      case 'terminology':
        return renderTerminologyTable(value as Array<Record<string, string>>)
      case 'stringArray':
        return renderStringArray(value as string[])
      case 'array':
      case 'object':
        return renderNestedValue(value)
      default:
        return (
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {String(value)}
          </p>
        )
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700/50 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <Icon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {displayName}
          </span>
          {!isExpanded && (
            <span className="text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs">
              {previewText}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isExpanded && !isEditing && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleStartEdit()
              }}
              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
            >
              {t('common.edit')}
            </button>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="px-4 py-4 border-t border-gray-100 dark:border-gray-700">
          {renderContent()}
        </div>
      )}
    </div>
  )
}

