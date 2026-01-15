import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Language, getTranslation } from '../i18n'

export type Theme = 'light' | 'dark'
export type FontSize = 'small' | 'medium' | 'large'

// Font size mappings for different UI elements
export const fontSizeClasses: Record<FontSize, {
  base: string
  xs: string
  sm: string
  label: string
  paragraph: string
  button: string
  title: string
  heading: string
}> = {
  small: {
    base: 'text-xs',
    xs: 'text-[10px]',
    sm: 'text-[11px]',
    label: 'text-[10px]',
    paragraph: 'text-xs',
    button: 'text-xs',
    title: 'text-base',
    heading: 'text-sm',
  },
  medium: {
    base: 'text-sm',
    xs: 'text-xs',
    sm: 'text-[13px]',
    label: 'text-xs',
    paragraph: 'text-sm',
    button: 'text-sm',
    title: 'text-lg',
    heading: 'text-base',
  },
  large: {
    base: 'text-base',
    xs: 'text-sm',
    sm: 'text-[15px]',
    label: 'text-sm',
    paragraph: 'text-base',
    button: 'text-base',
    title: 'text-xl',
    heading: 'text-lg',
  },
}

// Global base font size class for the entire app
export const globalFontSizeClass: Record<FontSize, string> = {
  small: 'text-xs',
  medium: 'text-sm',
  large: 'text-base',
}

// Translation progress info for header display
export interface TranslationProgressInfo {
  projectId: string
  projectName: string
  status: string
  progress: number
  completed_paragraphs: number
  total_paragraphs: number
}

// Translation progress for step indicator
export interface TranslationProgressForStep {
  hasTask: boolean
  status?: string
  progress: number
  completedParagraphs: number
  totalParagraphs: number
}

// Analysis progress for step indicator
export interface AnalysisProgressForStep {
  exists: boolean
  confirmed: boolean
}

// Proofreading progress for step indicator
export interface ProofreadingProgressForStep {
  hasSession: boolean
  status?: string
  roundNumber?: number
  progress?: number
  pendingSuggestions?: number
}

// Workflow step status for header display
export interface WorkflowStepStatus {
  projectId: string
  currentStep: 'analysis' | 'translation' | 'proofreading' | 'export'
  analysisCompleted: boolean
  translationCompleted: boolean
  proofreadingCompleted: boolean
  analysisProgress?: AnalysisProgressForStep
  translationProgress?: TranslationProgressForStep
  proofreadingProgress?: ProofreadingProgressForStep
}

// Panel width settings for resizable layout
export interface PanelWidths {
  chapterList: number  // Left panel width in pixels
  referencePanel: number  // Right panel width in pixels
}

// Default panel widths
export const DEFAULT_PANEL_WIDTHS: PanelWidths = {
  chapterList: 200,
  referencePanel: 288,  // w-72 = 18rem = 288px
}

interface AppState {
  // Language
  language: Language
  setLanguage: (language: Language) => void

  // Theme
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void

  // Font Size
  fontSize: FontSize
  setFontSize: (size: FontSize) => void

  // Translation Progress (for header display)
  translationProgress: TranslationProgressInfo | null
  setTranslationProgress: (progress: TranslationProgressInfo | null) => void

  // Workflow Step Status (for header display)
  workflowStatus: WorkflowStepStatus | null
  setWorkflowStatus: (status: WorkflowStepStatus | null) => void

  // Analysis Running State (for header display)
  isAnalyzing: boolean
  setIsAnalyzing: (isAnalyzing: boolean) => void

  // Panel Widths (for resizable layout)
  panelWidths: PanelWidths
  setPanelWidth: (panel: keyof PanelWidths, width: number) => void
  resetPanelWidths: () => void
}

// Apply theme to document
function applyTheme(theme: Theme) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

// Apply language to document
function applyLanguage(language: Language) {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  document.title = getTranslation(language, 'app.title')
}

// Get initial theme from system preference
function getInitialTheme(): Theme {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('epub-translator-app')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed.state?.theme) {
          return parsed.state.theme
        }
      } catch {
        // ignore
      }
    }
    // Check system preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
  }
  return 'light'
}

// Get initial language from stored preference or browser setting
function getInitialLanguage(): Language {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('epub-translator-app')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed.state?.language) {
          return parsed.state.language
        }
      } catch {
        // ignore
      }
    }
    if (typeof navigator !== 'undefined') {
      return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    }
  }
  return 'zh'
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      language: getInitialLanguage(),
      theme: getInitialTheme(),
      fontSize: 'medium',
      translationProgress: null,
      workflowStatus: null,
      isAnalyzing: false,
      panelWidths: DEFAULT_PANEL_WIDTHS,

      setLanguage: (language) => {
        applyLanguage(language)
        set({ language })
      },

      setTheme: (theme) => {
        applyTheme(theme)
        set({ theme })
      },

      toggleTheme: () => {
        const newTheme = get().theme === 'light' ? 'dark' : 'light'
        applyTheme(newTheme)
        set({ theme: newTheme })
      },

      setFontSize: (fontSize) => {
        set({ fontSize })
      },

      setTranslationProgress: (translationProgress) => {
        set({ translationProgress })
      },

      setWorkflowStatus: (workflowStatus) => {
        set({ workflowStatus })
      },

      setIsAnalyzing: (isAnalyzing) => {
        set({ isAnalyzing })
      },

      setPanelWidth: (panel, width) => {
        set((state) => ({
          panelWidths: {
            ...state.panelWidths,
            [panel]: width,
          },
        }))
      },

      resetPanelWidths: () => {
        set({ panelWidths: DEFAULT_PANEL_WIDTHS })
      },
    }),
    {
      name: 'epub-translator-app',
      partialize: (state) => ({
        // Only persist these fields, not translationProgress
        language: state.language,
        theme: state.theme,
        fontSize: state.fontSize,
        panelWidths: state.panelWidths,
      }),
      onRehydrateStorage: () => (state) => {
        // Apply stored theme and language on rehydration
        if (state) {
          applyTheme(state.theme)
          applyLanguage(state.language)
        }
      },
    }
  )
)

// Custom hook for translations
export function useTranslation() {
  const language = useAppStore((state) => state.language)
  return {
    t: (key: string, params?: Record<string, string>) => getTranslation(language, key, params),
    language,
  }
}

