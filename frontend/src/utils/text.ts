/**
 * Text utilities for safe string handling.
 *
 * This module provides UTF-8 safe string truncation utilities to prevent
 * character boundary issues when strings are processed by native code.
 */

/**
 * Safely truncate text without breaking multi-byte characters.
 *
 * JavaScript strings are UTF-16, so basic slicing is usually safe,
 * but this function provides additional safety by:
 * 1. Avoiding truncation in the middle of surrogate pairs
 * 2. Trying to break at word boundaries when possible
 *
 * @param text - Text to truncate
 * @param maxChars - Maximum characters (excluding suffix)
 * @param suffix - Suffix to append if truncated (default "...")
 * @returns Truncated text with suffix if needed
 */
export function safeTruncate(
  text: string,
  maxChars: number,
  suffix: string = '...'
): string {
  if (!text || text.length <= maxChars) {
    return text
  }

  // Basic truncation
  let truncated = text.slice(0, maxChars)

  // Check if we're in the middle of a surrogate pair
  // Surrogate pairs: high surrogate (0xD800-0xDBFF) followed by low surrogate (0xDC00-0xDFFF)
  const lastChar = truncated.charCodeAt(maxChars - 1)
  if (lastChar >= 0xd800 && lastChar <= 0xdbff) {
    // We cut in the middle of a surrogate pair, remove the orphan high surrogate
    truncated = truncated.slice(0, -1)
  }

  // Try to break at a word boundary (space, punctuation) for cleaner output
  // Look back up to 20 characters for a good break point
  const breakChars = new Set([
    ' ',
    '\n',
    '\t',
    ',',
    '.',
    '!',
    '?',
    ';',
    ':',
    '-',
    '\u3002', // Chinese period
    '\uff0c', // Chinese comma
    '\u3001', // Chinese enumeration comma
  ])

  for (let i = Math.min(20, truncated.length - 1); i > 0; i--) {
    if (breakChars.has(truncated[truncated.length - i])) {
      truncated = truncated.slice(0, truncated.length - i + 1).trimEnd()
      break
    }
  }

  return truncated + suffix
}

/**
 * Safely truncate a JSON-serialized value.
 *
 * This is specifically designed to prevent issues when truncating
 * JSON strings that may contain escape sequences or Unicode.
 *
 * @param value - Value to serialize and truncate
 * @param maxChars - Maximum characters for the result
 * @param suffix - Suffix to append if truncated
 * @returns Truncated JSON string representation
 */
export function safeTruncateJson(
  value: unknown,
  maxChars: number = 100,
  suffix: string = '...'
): string {
  let jsonStr: string
  try {
    jsonStr = JSON.stringify(value)
  } catch {
    jsonStr = String(value)
  }

  if (jsonStr.length <= maxChars) {
    return jsonStr
  }

  // For JSON, we need to be more careful about truncation
  // Don't truncate in the middle of escape sequences or inside strings
  const truncated = jsonStr.slice(0, maxChars)

  // Count unescaped quotes to check if we're inside a string
  let inString = false
  let escapeNext = false
  let safeEnd = 0

  for (let i = 0; i < truncated.length; i++) {
    const char = truncated[i]
    if (escapeNext) {
      escapeNext = false
      continue
    }
    if (char === '\\') {
      escapeNext = true
      continue
    }
    if (char === '"') {
      inString = !inString
      if (!inString) {
        safeEnd = i + 1
      }
    } else if (!inString && (char === ',' || char === ']' || char === '}')) {
      safeEnd = i + 1
    }
  }

  // If we ended inside a string, truncate to last safe position
  if (inString && safeEnd > 0) {
    return jsonStr.slice(0, safeEnd) + suffix
  }

  return truncated + suffix
}

/**
 * Normalize text for safe display in logs and UI.
 *
 * This function:
 * 1. Removes control characters
 * 2. Normalizes whitespace
 * 3. Optionally truncates to maxLength
 *
 * @param text - Text to normalize
 * @param maxLength - Optional maximum length
 * @returns Normalized text
 */
export function normalizeForDisplay(
  text: string,
  maxLength?: number
): string {
  if (!text) {
    return ''
  }

  // Remove control characters except newlines and tabs
  let normalized = text.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '')

  // Normalize whitespace (preserve newlines)
  normalized = normalized.replace(/[ \t]+/g, ' ')
  normalized = normalized.replace(/\n{3,}/g, '\n\n')

  if (maxLength) {
    normalized = safeTruncate(normalized, maxLength)
  }

  return normalized.trim()
}

