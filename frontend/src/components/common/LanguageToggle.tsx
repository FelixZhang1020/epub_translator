import { useState } from 'react'
import { Languages } from 'lucide-react'
import { useAppStore, useTranslation } from '../../stores/appStore'
import { Language } from '../../i18n'

export function LanguageToggle() {
  const { t } = useTranslation()
  const language = useAppStore((state) => state.language)
  const setLanguage = useAppStore((state) => state.setLanguage)
  const [isAnimating, setIsAnimating] = useState(false)

  const handleClick = () => {
    setIsAnimating(true)
    const newLang: Language = language === 'zh' ? 'en' : 'zh'
    setLanguage(newLang)
    // Reset animation after it completes
    setTimeout(() => setIsAnimating(false), 300)
  }

  return (
    <button
      onClick={handleClick}
      className={`
        flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all duration-200
        hover:bg-gray-100 dark:hover:bg-gray-700
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        dark:focus:ring-offset-gray-800
        ${isAnimating ? 'scale-105' : 'scale-100'}
      `}
      aria-label={language === 'zh' ? t('language.switchToEn') : t('language.switchToZh')}
    >
      <Languages
        className={`
          w-4 h-4 text-gray-600 dark:text-gray-300
          transition-transform duration-300
          ${isAnimating ? 'rotate-12 scale-110' : ''}
        `}
      />
      <span
        className={`
          text-sm font-medium text-gray-700 dark:text-gray-200
          transition-all duration-300
          ${isAnimating ? 'opacity-0 translate-y-1' : 'opacity-100 translate-y-0'}
        `}
      >
        {language === 'zh' ? t('language.zh') : t('language.en')}
      </span>
    </button>
  )
}
