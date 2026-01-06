import { ReactNode } from 'react'
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

  const steps = [
    { id: 'analysis', icon: BookOpen, label: t('workflow.analysis') },
    { id: 'translation', icon: Languages, label: t('workflow.translation') },
    { id: 'proofreading', icon: FileCheck, label: t('workflow.proofreading') },
    { id: 'export', icon: Download, label: t('workflow.export') },
  ]

  const getStepStatus = (stepId: string): 'completed' | 'current' | 'upcoming' => {
    // Only show completed (checkmark) if the step is confirmed AND we've moved past it
    const stepOrder = ['analysis', 'translation', 'proofreading', 'export']
    const currentIndex = stepOrder.indexOf(status.currentStep)
    const stepIndex = stepOrder.indexOf(stepId)

    // A step is completed only if:
    // 1. It has been confirmed (analysisCompleted, etc.)
    // 2. AND we are on a later step (not the current step)
    if (stepId === 'analysis' && status.analysisCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === 'translation' && status.translationCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === 'proofreading' && status.proofreadingCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === status.currentStep) return 'current'
    return 'upcoming'
  }

  const canNavigate = (stepId: string): boolean => {
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
                stepStatus === 'completed' || getStepStatus(steps[index - 1].id) === 'completed'
                  ? 'bg-blue-500'
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
                    : stepStatus === 'current'
                    ? 'border-2 border-blue-600 text-blue-600 bg-blue-50 dark:bg-blue-900/30'
                    : 'border border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500'
                  }
                  ${canClick && stepStatus !== 'completed' ? 'group-hover:border-blue-500 group-hover:text-blue-500' : ''}
                `}
              >
                {stepStatus === 'completed' ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <Icon className="w-3.5 h-3.5" />
                )}
              </span>
              {/* Step label */}
              <span
                className={`
                  text-[10px] font-medium whitespace-nowrap
                  ${stepStatus === 'current'
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
          <div className="relative flex justify-between items-center h-14">
            {/* Left: Logo */}
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-2">
                <BookOpen className="w-7 h-7 text-blue-600 dark:text-blue-400" />
                <span className={`${fontClasses.title} font-semibold text-gray-900 dark:text-white`}>
                  EPUB Translator
                </span>
              </Link>
            </div>

            {/* Center: Workflow Step Indicator + Translation Progress */}
            {isInProject && (workflowStatus || translationProgress) && (
              <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-3">
                {/* Workflow Step Indicator */}
                {workflowStatus && (
                  <HeaderStepIndicator status={workflowStatus} onStepClick={handleStepClick} />
                )}

                {/* Translation Progress */}
                {translationProgress && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-blue-50 dark:bg-blue-900/40 rounded-full border border-blue-200 dark:border-blue-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600 dark:text-blue-400" />
                    <span className={`${fontClasses.xs} text-blue-700 dark:text-blue-300 font-medium`}>
                      {t('translate.translationInProgress')}
                    </span>
                    <div className="w-20 h-1.5 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-600 dark:bg-blue-400 rounded-full transition-all duration-300"
                        style={{ width: `${Math.round(translationProgress.progress * 100)}%` }}
                      />
                    </div>
                    <span className={`${fontClasses.xs} text-blue-600 dark:text-blue-400 min-w-[3rem] text-right`}>
                      {Math.round(translationProgress.progress * 100)}%
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Right: Navigation + Controls */}
            <div className="flex items-center gap-2">
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
