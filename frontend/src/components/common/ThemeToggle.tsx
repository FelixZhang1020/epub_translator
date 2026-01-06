import { useState } from 'react'
import { Sun, Moon } from 'lucide-react'
import { useAppStore, useTranslation } from '../../stores/appStore'

export function ThemeToggle() {
  const { t } = useTranslation()
  const theme = useAppStore((state) => state.theme)
  const toggleTheme = useAppStore((state) => state.toggleTheme)
  const [isAnimating, setIsAnimating] = useState(false)

  const handleClick = () => {
    setIsAnimating(true)
    toggleTheme()
    // Reset animation after it completes
    setTimeout(() => setIsAnimating(false), 500)
  }

  return (
    <button
      onClick={handleClick}
      className={`
        relative p-2 rounded-lg transition-all duration-200
        hover:bg-gray-100 dark:hover:bg-gray-700
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        dark:focus:ring-offset-gray-800
        ${isAnimating ? 'scale-110' : 'scale-100'}
      `}
      aria-label={theme === 'light' ? t('theme.switchToDark') : t('theme.switchToLight')}
    >
      <div className={`transition-transform duration-500 ${isAnimating ? 'rotate-[360deg]' : ''}`}>
        {theme === 'light' ? (
          <Sun className="w-5 h-5 text-amber-500" />
        ) : (
          <Moon className="w-5 h-5 text-blue-400" />
        )}
      </div>
    </button>
  )
}
