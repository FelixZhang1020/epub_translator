import { useEffect, useState, useMemo } from 'react'
import { Outlet, useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Settings, FileCheck, ScanSearch, Languages, Download } from 'lucide-react'
import { api } from '../../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../../stores/appStore'

// Map database step name to URL path
const getRoutePathFromStep = (step: string): string => {
  const stepToRoute: Record<string, string> = {
    'analysis': 'analysis',
    'translation': 'translate',
    'proofreading': 'proofread',
    'export': 'export'
  }
  return stepToRoute[step] || 'analysis'
}

export function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const setTranslationProgress = useAppStore((state) => state.setTranslationProgress)
  const setWorkflowStatus = useAppStore((state) => state.setWorkflowStatus)
  const setIsAnalyzing = useAppStore((state) => state.setIsAnalyzing)

  // Map URL path to database step name
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

  // Fetch chapters for progress calculation
  const { data: chapters } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => api.getChapters(projectId!),
    enabled: !!projectId,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  // Calculate progress based on chapters data
  const { translatedCount, confirmedCount, totalParagraphs } = useMemo(() => {
    if (!chapters) return { translatedCount: 0, confirmedCount: 0, totalParagraphs: 0 }
    let translated = 0
    let confirmed = 0
    let total = 0
    for (const chapter of chapters) {
      translated += chapter.translated_count
      confirmed += chapter.confirmed_count
      total += chapter.paragraph_count
    }
    return { translatedCount: translated, confirmedCount: confirmed, totalParagraphs: total }
  }, [chapters])

  // Get font size
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]

  // Update current step when URL changes
  useEffect(() => {
    setCurrentStep(getCurrentStepFromPath())
  }, [location.pathname])

  // Validate stage access and redirect if necessary
  useEffect(() => {
    if (!workflowStatus || !projectId) return

    const currentPath = getCurrentStepFromPath()

    // Define stage access rules
    const canAccessStage = (stage: string): boolean => {
      if (stage === 'analysis') return true
      if (stage === 'translation') return workflowStatus.analysis_completed ?? false
      if (stage === 'proofreading') return workflowStatus.translation_completed ?? false
      if (stage === 'export') return workflowStatus.proofreading_completed ?? false
      return false
    }

    // Redirect if trying to access a locked stage
    if (!canAccessStage(currentPath)) {
      // Find the furthest accessible stage
      const stages = ['analysis', 'translation', 'proofreading', 'export']
      let redirectStage = 'analysis'

      for (const stage of stages) {
        if (canAccessStage(stage)) {
          redirectStage = stage
        } else {
          break
        }
      }

      // Only redirect if we're not already on the correct stage
      if (currentPath !== redirectStage) {
        const routePath = getRoutePathFromStep(redirectStage)
        navigate(`/project/${projectId}/${routePath}`, { replace: true })
      }
    }
  }, [location.pathname, workflowStatus, projectId, navigate])

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

  // Check if analysis is in progress
  const analysisProgress = effectiveWorkflowStatus?.analysis_progress
  const isAnalyzing = !!(analysisProgress?.has_task && analysisProgress?.status === 'processing')

  // Sync workflow status to global store for header display
  useEffect(() => {
    if (projectId && effectiveWorkflowStatus) {
      const analysisProgress = effectiveWorkflowStatus.analysis_progress
      const translationProgress = effectiveWorkflowStatus.translation_progress
      const proofreadingProgress = effectiveWorkflowStatus.proofreading_progress

      // Sync analysis running state to global store
      setIsAnalyzing(isAnalyzing)

      setWorkflowStatus({
        projectId,
        currentStep: currentStep as 'analysis' | 'translation' | 'proofreading' | 'export',
        analysisCompleted: effectiveWorkflowStatus.analysis_completed ?? false,
        translationCompleted: effectiveWorkflowStatus.translation_completed ?? false,
        proofreadingCompleted: effectiveWorkflowStatus.proofreading_completed ?? false,
        analysisProgress: analysisProgress ? {
          exists: analysisProgress.exists ?? false,
          confirmed: analysisProgress.confirmed ?? false,
        } : undefined,
        translationProgress: translationProgress ? {
          hasTask: translationProgress.has_task ?? false,
          status: translationProgress.status,
          progress: translationProgress.progress ?? 0,
          completedParagraphs: translationProgress.completed_paragraphs ?? 0,
          totalParagraphs: translationProgress.total_paragraphs ?? 0,
        } : undefined,
        proofreadingProgress: proofreadingProgress ? {
          hasSession: proofreadingProgress.has_session ?? false,
          status: proofreadingProgress.status,
          roundNumber: proofreadingProgress.round_number,
          progress: proofreadingProgress.progress ?? 0,
          pendingSuggestions: proofreadingProgress.pending_suggestions ?? 0,
        } : undefined,
      })
    }
  }, [projectId, currentStep, effectiveWorkflowStatus, isAnalyzing, setWorkflowStatus, setIsAnalyzing])

  // Clear progress and workflow status when leaving the project
  useEffect(() => {
    return () => {
      setTranslationProgress(null)
      setWorkflowStatus(null)
    }
  }, [setTranslationProgress, setWorkflowStatus])

  // Check if on workflow pages that need full-width/full-height layout
  // These must be defined before early returns to maintain hooks order
  const isAnalysisPage = location.pathname.includes('/analysis')
  const isTranslatePage = location.pathname.includes('/translate')
  const isProofreadPage = location.pathname.includes('/proofread')
  const isExportPage = location.pathname.includes('/export')
  // All workflow pages use full width
  const isWideLayout = isAnalysisPage || isTranslatePage || isProofreadPage || isExportPage
  // Only translate/proofread/export need fixed height viewport
  const isFixedHeightPage = isTranslatePage || isProofreadPage || isExportPage

  // Get current stage info for display (must be before early returns)
  const currentStageInfo = useMemo(() => {
    if (isAnalysisPage) return { icon: ScanSearch, label: t('workflow.analysis') }
    if (isTranslatePage) return { icon: Languages, label: t('workflow.translation') }
    if (isProofreadPage) return { icon: FileCheck, label: t('workflow.proofreading') }
    if (isExportPage) return { icon: Download, label: t('workflow.export') }
    return { icon: ScanSearch, label: t('workflow.analysis') }
  }, [isAnalysisPage, isTranslatePage, isProofreadPage, isExportPage, t])

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

  return (
    <div className={isWideLayout ? `w-full ${isFixedHeightPage ? 'h-full flex flex-col' : ''}` : 'max-w-6xl mx-auto'}>
      {/* Header - compact single line */}
      <div className={isFixedHeightPage ? 'mb-2 flex-shrink-0' : 'mb-2'}>
        <div className="flex items-center gap-3">
          {/* Stage Badge */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-700/50">
            <currentStageInfo.icon className="w-4 h-4 text-gray-600 dark:text-gray-300" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
              {currentStageInfo.label}
            </span>
          </div>

          {/* Divider */}
          <div className="h-5 w-px bg-gray-300 dark:bg-gray-600" />

          {/* Book info */}
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              {project.name}
            </h1>
            {project.author && (
              <span className="text-gray-500 dark:text-gray-400">
                - {project.author}
              </span>
            )}
          </div>

          {/* Settings button */}
          <button
            onClick={() => navigate(`/project/${projectId}/parameters`)}
            className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            title={t('parameterReview.title')}
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Progress indicator - show on translate/proofread/export pages */}
          {isFixedHeightPage && totalParagraphs > 0 && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
              <div className="w-20">
                <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      (isTranslatePage ? translatedCount : confirmedCount) === totalParagraphs
                        ? 'bg-green-500'
                        : 'bg-blue-600'
                    }`}
                    style={{
                      width: `${Math.round(((isTranslatePage ? translatedCount : confirmedCount) / totalParagraphs) * 100)}%`
                    }}
                  />
                </div>
              </div>
              <span className={`font-medium text-gray-600 dark:text-gray-300 ${fontClasses.xs} whitespace-nowrap`}>
                {isTranslatePage ? translatedCount : confirmedCount} / {totalParagraphs}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Page Content */}
      <div className={`${isFixedHeightPage
          ? 'flex-1 min-h-0 overflow-hidden'
          : ''
        }`}>
        <Outlet context={{ project, workflowStatus: effectiveWorkflowStatus, refetchWorkflow }} />
      </div>
    </div>
  )
}
