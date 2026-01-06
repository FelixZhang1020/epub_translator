import { useEffect, useState } from 'react'
import { Outlet, useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore } from '../../stores/appStore'

export function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const setTranslationProgress = useAppStore((state) => state.setTranslationProgress)
  const setWorkflowStatus = useAppStore((state) => state.setWorkflowStatus)

  // Get current step from URL path
  const getCurrentStepFromPath = (): string => {
    const path = location.pathname
    if (path.includes('/analysis')) return 'analysis'
    if (path.includes('/translate')) return 'translation'
    if (path.includes('/proofread')) return 'proofreading'
    if (path.includes('/export')) return 'export'
    return 'analysis'
  }

  const [currentStep, setCurrentStep] = useState(getCurrentStepFromPath())

  // Fetch project info
  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: !!projectId,
  })

  // Fetch workflow status
  const { data: workflowStatus, isLoading: statusLoading, refetch: refetchWorkflow } = useQuery({
    queryKey: ['workflowStatus', projectId],
    queryFn: () => api.getWorkflowStatus(projectId!),
    enabled: !!projectId,
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  // Check if translation is in progress
  const translationProgress = workflowStatus?.translation_progress
  const isTranslating = translationProgress?.status === 'processing' || translationProgress?.status === 'pending'

  // Refetch more frequently when translation is in progress
  const { data: activeWorkflowStatus } = useQuery({
    queryKey: ['workflowStatus-active', projectId],
    queryFn: () => api.getWorkflowStatus(projectId!),
    enabled: !!projectId && isTranslating,
    refetchInterval: isTranslating ? 2000 : false, // Refresh every 2 seconds while translating
  })

  // Use active status when available and translating
  const effectiveWorkflowStatus = isTranslating && activeWorkflowStatus ? activeWorkflowStatus : workflowStatus
  const effectiveTranslationProgress = effectiveWorkflowStatus?.translation_progress
  const effectiveIsTranslating = effectiveTranslationProgress?.status === 'processing' || effectiveTranslationProgress?.status === 'pending'

  // Update current step when URL changes
  useEffect(() => {
    setCurrentStep(getCurrentStepFromPath())
  }, [location.pathname])

  // Sync translation progress to global store for header display
  useEffect(() => {
    if (effectiveIsTranslating && effectiveTranslationProgress && project && projectId) {
      setTranslationProgress({
        projectId,
        projectName: project.name,
        status: effectiveTranslationProgress.status || 'processing',
        progress: effectiveTranslationProgress.progress,
        completed_paragraphs: effectiveTranslationProgress.completed_paragraphs,
        total_paragraphs: effectiveTranslationProgress.total_paragraphs,
      })
    } else {
      setTranslationProgress(null)
    }
  }, [effectiveIsTranslating, effectiveTranslationProgress, project, projectId, setTranslationProgress])

  // Sync workflow status to global store for header display
  useEffect(() => {
    if (projectId && effectiveWorkflowStatus) {
      setWorkflowStatus({
        projectId,
        currentStep: currentStep as 'analysis' | 'translation' | 'proofreading' | 'export',
        analysisCompleted: effectiveWorkflowStatus.analysis_completed ?? false,
        translationCompleted: effectiveWorkflowStatus.translation_completed ?? false,
        proofreadingCompleted: effectiveWorkflowStatus.proofreading_completed ?? false,
      })
    }
  }, [projectId, currentStep, effectiveWorkflowStatus, setWorkflowStatus])

  // Clear progress and workflow status when leaving the project
  useEffect(() => {
    return () => {
      setTranslationProgress(null)
      setWorkflowStatus(null)
    }
  }, [setTranslationProgress, setWorkflowStatus])

  if (projectLoading || statusLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {t('common.error')}
        </h2>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Project not found
        </p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-blue-600 hover:text-blue-700"
        >
          {t('nav.home')}
        </button>
      </div>
    )
  }

  // Check if on translate page for wider layout
  const isTranslatePage = location.pathname.includes('/translate')

  return (
    <div className={isTranslatePage ? 'w-full h-full flex flex-col' : 'max-w-6xl mx-auto'}>
      {/* Header - compact for translate page */}
      <div className={isTranslatePage ? 'mb-1 flex-shrink-0' : 'mb-6'}>
        {!isTranslatePage && (
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('nav.home')}
          </button>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isTranslatePage && (
              <button
                onClick={() => navigate('/')}
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            <div>
              <h1 className={`font-bold text-gray-900 dark:text-gray-100 ${isTranslatePage ? 'text-lg' : 'text-2xl'}`}>
                {project.name}
              </h1>
              {project.author && !isTranslatePage && (
                <p className="text-gray-600 dark:text-gray-400 mt-1">
                  {t('common.by')} {project.author}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Page Content */}
      <div className={`${
        isTranslatePage
          ? 'flex-1 min-h-0 overflow-hidden'
          : 'mt-8'
      }`}>
        <Outlet context={{ project, workflowStatus: effectiveWorkflowStatus, refetchWorkflow }} />
      </div>
    </div>
  )
}
