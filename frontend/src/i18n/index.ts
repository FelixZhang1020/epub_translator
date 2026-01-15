import zh from './locales/zh.json'
import en from './locales/en.json'

export type Language = 'zh' | 'en'

const translations = { zh, en }

type NestedKeyOf<ObjectType extends object> = {
  [Key in keyof ObjectType & (string | number)]: ObjectType[Key] extends object
    ? `${Key}` | `${Key}.${NestedKeyOf<ObjectType[Key]>}`
    : `${Key}`
}[keyof ObjectType & (string | number)]

export type TranslationKey = NestedKeyOf<typeof zh>

export function getTranslation(language: Language, key: string, params?: Record<string, string>): string {
  const keys = key.split('.')
  let value: unknown = translations[language]

  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = (value as Record<string, unknown>)[k]
    } else {
      return key // Return key if translation not found
    }
  }

  if (typeof value !== 'string') {
    return key
  }

  // Replace parameters like {{name}} with actual values
  if (params) {
    return value.replace(/\{\{(\w+)\}\}/g, (_, paramKey) => params[paramKey] ?? `{{${paramKey}}}`)
  }

  return value
}

export function createT(language: Language) {
  return (key: string, params?: Record<string, string>) => getTranslation(language, key, params)
}

export { zh, en }

