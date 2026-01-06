import { Check, BookOpen, Languages, FileCheck, Download } from 'lucide-react'
import { useTranslation } from '../../stores/appStore'

interface Step {
  id: string
  label: string
  icon: React.ReactNode
}

interface StepIndicatorProps {
  currentStep: string
  analysisCompleted: boolean
  translationCompleted: boolean
  proofreadingCompleted: boolean
  onStepClick?: (step: string) => void
}

export function StepIndicator({
  currentStep,
  analysisCompleted,
  translationCompleted,
  proofreadingCompleted,
  onStepClick,
}: StepIndicatorProps) {
  const { t } = useTranslation()

  const steps: Step[] = [
    { id: 'analysis', label: t('workflow.analysis'), icon: <BookOpen className="w-5 h-5" /> },
    { id: 'translation', label: t('workflow.translation'), icon: <Languages className="w-5 h-5" /> },
    { id: 'proofreading', label: t('workflow.proofreading'), icon: <FileCheck className="w-5 h-5" /> },
    { id: 'export', label: t('workflow.export'), icon: <Download className="w-5 h-5" /> },
  ]

  const getStepStatus = (stepId: string): 'completed' | 'current' | 'upcoming' => {
    // Only show completed (checkmark) if the step is confirmed AND we've moved past it
    const stepOrder = ['analysis', 'translation', 'proofreading', 'export']
    const currentIndex = stepOrder.indexOf(currentStep)
    const stepIndex = stepOrder.indexOf(stepId)

    // A step is completed only if:
    // 1. It has been confirmed (analysisCompleted, etc.)
    // 2. AND we are on a later step (not the current step)
    if (stepId === 'analysis' && analysisCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === 'translation' && translationCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === 'proofreading' && proofreadingCompleted && stepIndex < currentIndex) return 'completed'
    if (stepId === currentStep) return 'current'
    return 'upcoming'
  }

  const canNavigate = (stepId: string): boolean => {
    const stepOrder = ['analysis', 'translation', 'proofreading', 'export']
    const currentIndex = stepOrder.indexOf(currentStep)
    const targetIndex = stepOrder.indexOf(stepId)

    // Can always go back
    if (targetIndex <= currentIndex) return true

    // Can move forward only if prerequisites are met
    if (stepId === 'translation') return analysisCompleted
    if (stepId === 'proofreading') return translationCompleted
    if (stepId === 'export') return true // Can preview export anytime after proofreading started

    return false
  }

  return (
    <nav aria-label={t('common.progress')} className="mb-8">
      <ol className="flex items-center justify-center">
        {steps.map((step, index) => {
          const status = getStepStatus(step.id)
          const canClick = canNavigate(step.id)

          return (
            <li key={step.id} className="relative flex items-center">
              {/* Connector line */}
              {index > 0 && (
                <div
                  className={`absolute right-full w-16 h-0.5 -translate-y-1/2 top-1/2 ${
                    status === 'completed' || getStepStatus(steps[index - 1].id) === 'completed'
                      ? 'bg-blue-600 dark:bg-blue-500'
                      : 'bg-gray-200 dark:bg-gray-700'
                  }`}
                />
              )}

              {/* Step button */}
              <button
                onClick={() => canClick && onStepClick?.(step.id)}
                disabled={!canClick}
                className={`
                  relative flex flex-col items-center group
                  ${canClick ? 'cursor-pointer' : 'cursor-not-allowed'}
                `}
              >
                {/* Circle */}
                <span
                  className={`
                    flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all
                    ${
                      status === 'completed'
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : status === 'current'
                        ? 'border-blue-600 text-blue-600 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500'
                    }
                    ${canClick && status !== 'completed' ? 'group-hover:border-blue-500 group-hover:text-blue-500' : ''}
                  `}
                >
                  {status === 'completed' ? (
                    <Check className="w-6 h-6" />
                  ) : (
                    step.icon
                  )}
                </span>

                {/* Label */}
                <span
                  className={`
                    mt-2 text-sm font-medium whitespace-nowrap
                    ${
                      status === 'current'
                        ? 'text-blue-600 dark:text-blue-400'
                        : status === 'completed'
                        ? 'text-gray-900 dark:text-gray-100'
                        : 'text-gray-400 dark:text-gray-500'
                    }
                  `}
                >
                  {step.label}
                </span>
              </button>

              {/* Spacer for connector */}
              {index < steps.length - 1 && <div className="w-16" />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
