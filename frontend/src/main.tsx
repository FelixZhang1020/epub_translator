import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { getTranslation, Language } from './i18n'
import './index.css'

// Apply language immediately before React renders to prevent flash
function initLanguage() {
  const stored = localStorage.getItem('epub-translator-app')
  let language: Language = 'zh'

  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      if (parsed.state?.language) {
        language = parsed.state.language
      }
    } catch {
      // ignore
    }
  } else if (typeof navigator !== 'undefined') {
    language = navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
  }

  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  document.title = getTranslation(language, 'app.title')
}

// Apply theme immediately before React renders to prevent flash
function initTheme() {
  const stored = localStorage.getItem('epub-translator-app')
  let theme = 'light'

  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      if (parsed.state?.theme) {
        theme = parsed.state.theme
      }
    } catch {
      // Check system preference
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        theme = 'dark'
      }
    }
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    theme = 'dark'
  }

  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  }
}

initLanguage()
initTheme()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
