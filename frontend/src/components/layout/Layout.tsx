import { ReactNode, useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Settings, Home, Loader2, Languages, FileCheck, Download, Check, FileText, ScanSearch, BookOpen } from 'lucide-react'
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

  // Get analysis running state from global store
  const isAnalyzing = useAppStore((state) => state.isAnalyzing)

  // Check if any step is actively running
  const translationStatus = status.translationProgress?.status
  const isTranslationRunning = status.translationProgress?.hasTask &&
    (translationStatus === 'processing' || translationStatus === 'pending')

  const proofreadingStatus = status.proofreadingProgress?.status
  const isProofreadingRunning = status.proofreadingProgress?.hasSession &&
    (proofreadingStatus === 'processing' || proofreadingStatus === 'pending')

  // Translation is only marked as finished when user explicitly clicks "Complete Translation" button
  const translationFinished = status.translationCompleted

  // Build steps array - fixed structure
  const steps = useMemo(() => {
    const baseSteps = [
      { id: 'analysis', icon: ScanSearch, label: t('workflow.analysis') },
      { id: 'translation', icon: Languages, label: t('workflow.translation') },
      { id: 'proofreading', icon: FileCheck, label: t('workflow.proofreading') },
      { id: 'export', icon: Download, label: t('workflow.export') },
    ]

    return baseSteps
  }, [t])

  // Status types:
  // - completed: Step is fully done (green checkmark)
  // - in_progress: Step is actively being processed (animated orange spinning)
  // - current: On this step but not processing
  // - upcoming: Not accessible yet
  const getStepStatus = (stepId: string): 'completed' | 'in_progress' | 'current' | 'upcoming' => {
    // Analysis: show in_progress when analyzing (highest priority), then completed when confirmed
    if (stepId === 'analysis') {
      // Show orange spinning when LLM is actively analyzing (check this first!)
      if (isAnalyzing) return 'in_progress'
      if (status.analysisCompleted) return 'completed'
      if (status.currentStep === 'analysis') return 'current'
      return 'upcoming'
    }

    // Translation: show in_progress while running (highest priority), then completed when finished
    if (stepId === 'translation') {
      // Show orange spinning when LLM is actively translating (check this first!)
      if (isTranslationRunning) return 'in_progress'
      if (translationFinished) return 'completed'
      if (status.currentStep === 'translation') return 'current'
      return 'upcoming'
    }

    // Proofreading: show in_progress while running (highest priority), then completed when finished
    if (stepId === 'proofreading') {
      // Show orange spinning when LLM is actively proofreading (check this first!)
      if (isProofreadingRunning) return 'in_progress'
      if (status.proofreadingCompleted) return 'completed'
      if (status.currentStep === 'proofreading') return 'current'
      return 'upcoming'
    }

    // Export: simple state for now (no LLM processing)
    if (stepId === 'export') {
      if (status.currentStep === 'export') return 'current'
      return 'upcoming'
    }

    return 'upcoming'
  }

  const canNavigate = (stepId: string): boolean => {
    const stepOrder = ['analysis', 'translation', 'proofreading', 'export']
    const currentIndex = stepOrder.indexOf(status.currentStep)
    const targetIndex = stepOrder.indexOf(stepId)
    if (targetIndex <= currentIndex) return true
    if (stepId === 'translation') return status.analysisCompleted
    if (stepId === 'proofreading') return status.translationCompleted
    if (stepId === 'export') return status.proofreadingCompleted
    return false
  }

  return (
    <div className="flex">
      {steps.map((step, index) => {
        const stepStatus = getStepStatus(step.id)
        const prevStepStatus = index > 0 ? getStepStatus(steps[index - 1].id) : null
        const canClick = canNavigate(step.id)
        const Icon = step.icon

        // Connector color based on previous step status
        const connectorColor = prevStepStatus === 'completed'
          ? 'bg-blue-500'
          : prevStepStatus === 'in_progress'
          ? 'bg-amber-400'
          : 'bg-gray-300 dark:bg-gray-600'

        return (
          <button
            key={step.id}
            onClick={() => canClick && onStepClick(step.id)}
            disabled={!canClick}
            className={`
              w-[76px] flex flex-col items-center gap-0.5 transition-all
              ${canClick ? 'cursor-pointer' : 'cursor-not-allowed'}
            `}
          >
            {/* Icon row with connectors */}
            <div className="relative flex items-center justify-center w-full h-7">
              {/* Left connector */}
              {index > 0 && (
                <div className={`absolute right-1/2 mr-3.5 w-[calc(50%-14px)] h-0.5 ${connectorColor}`} />
              )}
              {/* Step circle */}
              <span
                className={`
                  w-7 h-7 rounded-full flex items-center justify-center transition-all z-10
                  ${stepStatus === 'completed'
                    ? 'bg-blue-600 text-white'
                    : stepStatus === 'in_progress'
                    ? 'border-2 border-amber-500 text-amber-600 bg-amber-50 dark:bg-amber-900/30 animate-pulse'
                    : stepStatus === 'current'
                    ? 'border-2 border-blue-600 text-blue-600 bg-blue-50 dark:bg-blue-900/30'
                    : 'border border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500 bg-white dark:bg-gray-800'
                  }
                `}
              >
                {stepStatus === 'completed' ? (
                  <Check className="w-3.5 h-3.5" />
                ) : stepStatus === 'in_progress' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Icon className="w-3.5 h-3.5" />
                )}
              </span>
              {/* Right connector */}
              {index < steps.length - 1 && (
                <div className={`absolute left-1/2 ml-3.5 w-[calc(50%-14px)] h-0.5 ${
                  stepStatus === 'completed'
                    ? 'bg-blue-500'
                    : stepStatus === 'in_progress'
                    ? 'bg-amber-400'
                    : 'bg-gray-300 dark:bg-gray-600'
                }`} />
              )}
            </div>
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

  // Check if this is a workflow page that needs special layout
  const isAnalysisPage = location.pathname.includes('/analysis')
  const isTranslatePage = location.pathname.includes('/translate')
  const isProofreadPage = location.pathname.includes('/proofread')
  const isExportPage = location.pathname.includes('/export')
  // All workflow pages use wide layout (90% width)
  const isWideLayout = isAnalysisPage || isTranslatePage || isProofreadPage || isExportPage
  // Only translate/proofread/export need fixed height viewport
  const isFixedHeightPage = isTranslatePage || isProofreadPage || isExportPage

  return (
    <div className={`bg-gray-50 dark:bg-gray-900 transition-colors duration-200 ${globalFontClass} ${
      isFixedHeightPage ? 'h-screen flex flex-col overflow-hidden' : 'min-h-screen'
    }`}>
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 transition-colors duration-200 flex-shrink-0">
        <div className={`mx-auto ${isWideLayout ? 'w-[90%]' : 'max-w-7xl px-4 sm:px-6 lg:px-8'}`}>
          <div className="flex items-center h-14">
            {/* Left: Logo */}
            <div className="flex items-center flex-shrink-0">
              <Link to="/" className="flex items-center gap-2">
                <BookOpen className="w-7 h-7 text-blue-600 dark:text-blue-400" />
                <span className={`${fontClasses.title} font-semibold text-gray-900 dark:text-white`}>
                  ePub Translator
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

      {/* Main content - wide for workflow pages, constrained for others */}
      <main className={`${
        isWideLayout
          ? `w-[90%] mx-auto pt-4 pb-1 ${isFixedHeightPage ? 'flex-1 min-h-0 overflow-hidden' : ''}`
          : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-1'
      }`}>
        {children}
      </main>
    </div>
  )
}
