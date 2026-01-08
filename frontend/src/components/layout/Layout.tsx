import { ReactNode, useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { BookOpen, Settings, Home, Loader2, Languages, FileCheck, Download, Check, FileText } from 'lucide-react'
import { ThemeToggle } from '../common/ThemeToggle'
import { LanguageToggle } from '../common/LanguageToggle'
import { useTranslation, useAppStore, globalFontSizeClass, fontSizeClasses, WorkflowStepStatus } from '../../stores/appStore'

// Compact step indicator for header
function HeaderStepIndicator({
  status,
  onStepClick
}: {
  status: WorkflowStepStatus
  onStepClick: (step: string) => void
}) {
  const { t } = useTranslation()

  // Check if translation is actively running
  const isTranslating = status.translationProgress?.hasTask &&
    (status.translationProgress.status === 'processing' || status.translationProgress.status === 'pending')

  // Build steps array dynamically - insert "translating" node when translation is running
  const steps = useMemo(() => {
    const baseSteps = [
      { id: 'analysis', icon: BookOpen, label: t('workflow.analysis') },
      { id: 'translation', icon: Languages, label: t('workflow.translation') },
      { id: 'proofreading', icon: FileCheck, label: t('workflow.proofreading') },
      { id: 'export', icon: Download, label: t('workflow.export') },
    ]

    // Insert "translating" node between translation and proofreading when translation is running
    if (isTranslating) {
      baseSteps.splice(2, 0, {
        id: 'translating',
        icon: Loader2,
        label: t('workflow.translating'),
      })
    }

    return baseSteps
  }, [t, isTranslating])

  // Status types:
  // - completed: Step is fully done (green checkmark)
  // - in_progress: Step is actively being processed (animated)
  // - current: On this step but not processing
  // - upcoming: Not accessible yet
  const getStepStatus = (stepId: string): 'completed' | 'in_progress' | 'current' | 'upcoming' => {
    // Analysis: completed when confirmed, regardless of current page
    if (stepId === 'analysis') {
      if (status.analysisCompleted) return 'completed'
      if (status.currentStep === 'analysis') return 'current'
      return 'upcoming'
    }

    // Translation: completed when done or when actively translating (show as completed to make room for "translating" node)
    if (stepId === 'translation') {
      if (status.translationCompleted) return 'completed'
      // When translation is running, mark the translation step as completed
      // so the "translating" node shows as in_progress
      if (isTranslating) return 'completed'
      if (status.currentStep === 'translation') return 'current'
      return 'upcoming'
    }

    // Translating (dynamic node): always in_progress when it exists
    if (stepId === 'translating') {
      return 'in_progress'
    }

    // Proofreading and Export: keep simple for now
    if (stepId === 'proofreading') {
      if (status.proofreadingCompleted) return 'completed'
      if (status.currentStep === 'proofreading') return 'current'
      return 'upcoming'
    }

    if (stepId === 'export') {
      if (status.currentStep === 'export') return 'current'
      return 'upcoming'
    }

    return 'upcoming'
  }

  const canNavigate = (stepId: string): boolean => {
    // The "translating" dynamic node is not clickable
    if (stepId === 'translating') return false

    const stepOrder = ['analysis', 'translation', 'proofreading', 'export']
    const currentIndex = stepOrder.indexOf(status.currentStep)
    const targetIndex = stepOrder.indexOf(stepId)
    if (targetIndex <= currentIndex) return true
    if (stepId === 'translation') return status.analysisCompleted
    if (stepId === 'proofreading') return status.translationCompleted
    if (stepId === 'export') return true
    return false
  }

  return (
    <div className="flex items-center gap-1">
      {steps.map((step, index) => {
        const stepStatus = getStepStatus(step.id)
        const canClick = canNavigate(step.id)
        const Icon = step.icon

        return (
          <div key={step.id} className="flex items-center">
            {/* Connector line */}
            {index > 0 && (
              <div className={`w-6 h-0.5 ${
                getStepStatus(steps[index - 1].id) === 'completed'
                  ? 'bg-blue-500'
                  : getStepStatus(steps[index - 1].id) === 'in_progress'
                  ? 'bg-amber-400'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`} />
            )}

            {/* Step with label */}
            <button
              onClick={() => canClick && onStepClick(step.id)}
              disabled={!canClick}
              className={`
                flex flex-col items-center gap-0.5 transition-all
                ${canClick ? 'cursor-pointer' : 'cursor-not-allowed'}
              `}
            >
              {/* Step circle */}
              <span
                className={`
                  w-7 h-7 rounded-full flex items-center justify-center transition-all
                  ${stepStatus === 'completed'
                    ? 'bg-blue-600 text-white'
                    : stepStatus === 'in_progress'
                    ? 'border-2 border-amber-500 text-amber-600 bg-amber-50 dark:bg-amber-900/30 animate-pulse'
                    : stepStatus === 'current'
                    ? 'border-2 border-blue-600 text-blue-600 bg-blue-50 dark:bg-blue-900/30'
                    : 'border border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500'
                  }
                  ${canClick && stepStatus !== 'completed' && stepStatus !== 'in_progress' ? 'group-hover:border-blue-500 group-hover:text-blue-500' : ''}
                `}
              >
                {stepStatus === 'completed' ? (
                  <Check className="w-3.5 h-3.5" />
                ) : stepStatus === 'in_progress' && step.id === 'translating' ? (
                  // Show percentage for translating node
                  <span className="text-[9px] font-bold">
                    {Math.round((status.translationProgress?.progress || 0) * 100)}%
                  </span>
                ) : stepStatus === 'in_progress' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Icon className="w-3.5 h-3.5" />
                )}
              </span>
              {/* Step label */}
              <span
                className={`
                  text-[10px] font-medium whitespace-nowrap
                  ${stepStatus === 'in_progress'
                    ? 'text-amber-600 dark:text-amber-400'
                    : stepStatus === 'current'
                    ? 'text-blue-600 dark:text-blue-400'
                    : stepStatus === 'completed'
                    ? 'text-gray-700 dark:text-gray-300'
                    : 'text-gray-400 dark:text-gray-500'
                  }
                `}
              >
                {step.label}
              </span>
            </button>
          </div>
        )
      })}
    </div>
  )
}

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const translationProgress = useAppStore((state) => state.translationProgress)
  const workflowStatus = useAppStore((state) => state.workflowStatus)
  const globalFontClass = globalFontSizeClass[fontSize]
  const fontClasses = fontSizeClasses[fontSize]

  const navItems = [
    { path: '/', labelKey: 'nav.home', icon: Home },
    { path: '/prompts', labelKey: 'nav.prompts', icon: FileText },
    { path: '/settings', labelKey: 'nav.settings', icon: Settings },
  ]

  // Check if we're in a project page
  const isInProject = location.pathname.includes('/project/')

  // Handle step click navigation
  const handleStepClick = (step: string) => {
    if (!workflowStatus) return
    const stepToPath: Record<string, string> = {
      analysis: 'analysis',
      translation: 'translate',
      proofreading: 'proofread',
      export: 'export',
    }
    navigate(`/project/${workflowStatus.projectId}/${stepToPath[step]}`)
  }

  // Check if this is a translate page that needs fixed viewport layout
  const isTranslatePage = location.pathname.includes('/translate')

  return (
    <div className={`bg-gray-50 dark:bg-gray-900 transition-colors duration-200 ${globalFontClass} ${
      isTranslatePage ? 'h-screen flex flex-col overflow-hidden' : 'min-h-screen'
    }`}>
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 transition-colors duration-200 flex-shrink-0">
        <div className={`mx-auto ${isTranslatePage ? 'w-[90%]' : 'max-w-7xl px-4 sm:px-6 lg:px-8'}`}>
          <div className="flex items-center h-14">
            {/* Left: Logo */}
            <div className="flex items-center flex-shrink-0">
              <Link to="/" className="flex items-center gap-2">
                <BookOpen className="w-7 h-7 text-blue-600 dark:text-blue-400" />
                <span className={`${fontClasses.title} font-semibold text-gray-900 dark:text-white`}>
                  EPUB Translator
                </span>
              </Link>
            </div>

            {/* Center: Spacer with workflow indicator - flex-1 keeps nav position stable */}
            <div className="flex-1 flex justify-center items-center">
              {/* Workflow Step Indicator */}
              {isInProject && workflowStatus && (
                <HeaderStepIndicator status={workflowStatus} onStepClick={handleStepClick} />
              )}
            </div>

            {/* Right: Navigation + Controls */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Navigation */}
              <nav className="flex items-center gap-1 mr-4">
                {navItems.map(({ path, labelKey, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md ${fontClasses.button} font-medium transition-colors ${
                      location.pathname === path
                        ? 'bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {t(labelKey)}
                  </Link>
                ))}
              </nav>

              {/* Divider */}
              <div className="h-5 w-px bg-gray-200 dark:bg-gray-600" />

              {/* Theme and Language Controls */}
              <div className="flex items-center gap-1 ml-2">
                <LanguageToggle />
                <ThemeToggle />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main content - full width for translate pages, constrained for others */}
      <main className={`${
        isTranslatePage
          ? 'w-[90%] mx-auto py-1 flex-1 min-h-0 overflow-hidden'
          : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6'
      }`}>
        {children}
      </main>
    </div>
  )
}
