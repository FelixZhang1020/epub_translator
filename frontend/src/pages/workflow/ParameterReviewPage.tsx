import { useState } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, ArrowLeft, ChevronDown, ChevronRight, CheckCircle, AlertCircle } from 'lucide-react'
import { api, Project, WorkflowStatus, StageParameterReview } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

interface OutletContext {
  project: Project
  workflowStatus: WorkflowStatus
  refetchWorkflow: () => void
}

export function ParameterReviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  useOutletContext<OutletContext>()

  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({})

  // Fetch parameter review data
  const { data: review, isLoading } = useQuery({
    queryKey: ['parameterReview', projectId],
    queryFn: () => api.getParameterReview(projectId!),
    enabled: !!projectId,
  })

  const toggleStage = (stage: string) => {
    setExpandedStages(prev => ({
      ...prev,
      [stage]: !prev[stage]
    }))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!review) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">{t('common.error')}</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-6">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate(`/project/${projectId}/analysis`)}
          className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('common.back')}
        </button>

        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t('parameterReview.title')}
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {t('parameterReview.subtitle')}
        </p>
        <div className="mt-2 text-sm text-gray-500">
          {t('parameterReview.effectiveCount', {
            effective: String(review.summary.total_input_effective),
            total: String(review.summary.total_input_count)
          })}
        </div>
      </div>

      {/* Stage Sections */}
      <div className="space-y-4">
        {review.stages.map((stageReview: StageParameterReview) => (
          <div key={stageReview.stage} className="border rounded-lg bg-white dark:bg-gray-800">
            {/* Stage Header */}
            <button
              onClick={() => toggleStage(stageReview.stage)}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedStages[stageReview.stage] ? (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                )}
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {t(`parameterReview.stages.${stageReview.stage}`)}
                </h2>
                <span className="px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                  {stageReview.template_name}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${stageReview.input_effective_count === stageReview.input_total_count
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-amber-600 dark:text-amber-400'
                  }`}>
                  {stageReview.input_effective_count}/{stageReview.input_total_count} {t('parameterReview.effective')}
                </span>
              </div>
            </button>

            {/* Stage Content */}
            {expandedStages[stageReview.stage] && (
              <div className="border-t p-4">
                <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                  {t('parameterReview.inputParameters')}
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          {t('parameterReview.status')}
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          {t('parameterReview.parameter')}
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          Namespace
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          {t('parameterReview.value')}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {stageReview.input_parameters.map((param) => (
                        <tr
                          key={param.name}
                          className={param.is_effective ? 'bg-white dark:bg-gray-800' : 'bg-amber-50 dark:bg-amber-900/10'}
                        >
                          <td className="px-4 py-3">
                            {param.is_effective ? (
                              <CheckCircle className="w-4 h-4 text-green-500" />
                            ) : (
                              <AlertCircle className="w-4 h-4 text-amber-500" />
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <code className="text-sm text-blue-600 dark:text-blue-400">
                              {param.name}
                            </code>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                              {t(`parameterReview.namespaces.${param.namespace}`) || param.namespace}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-sm text-gray-700 dark:text-gray-300 font-mono">
                              {param.is_effective ? param.value_preview : t('parameterReview.noValue')}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Output Fields for Analysis/Proofreading */}
                {stageReview.has_structured_output && stageReview.output_fields && (
                  <div className="mt-6">
                    <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                      {t('parameterReview.outputParameters')}
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-gray-50 dark:bg-gray-700">
                          <tr>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                              Field
                            </th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                              Description
                            </th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                              Type
                            </th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                              {t('parameterReview.populated')}
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                          {stageReview.output_fields.map((field) => (
                            <tr key={field.name}>
                              <td className="px-4 py-3">
                                <code className="text-sm text-purple-600 dark:text-purple-400">
                                  {field.name}
                                </code>
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                {field.description}
                              </td>
                              <td className="px-4 py-3">
                                <span className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                                  {field.value_type}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                {field.is_populated ? (
                                  <CheckCircle className="w-4 h-4 text-green-500" />
                                ) : (
                                  <span className="text-sm text-gray-400">-</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

