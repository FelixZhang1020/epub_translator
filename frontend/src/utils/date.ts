/**
 * Date formatting utilities.
 * All dates in the project should use YYYY-MM-DD format.
 */

/**
 * Format a date string or Date object to YYYY-MM-DD format.
 * @param date - Date string (ISO format) or Date object
 * @returns Formatted date string in YYYY-MM-DD format
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Format a date string or Date object to YYYY-MM-DD HH:mm format.
 * @param date - Date string (ISO format) or Date object
 * @returns Formatted datetime string in YYYY-MM-DD HH:mm format
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

