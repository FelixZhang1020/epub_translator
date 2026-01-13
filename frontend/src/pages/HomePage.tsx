import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, BookOpen, Clock, CheckCircle, AlertCircle, Trash2, Star } from 'lucide-react'
import { api } from '../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../stores/appStore'
import { formatDate } from '../utils/date'

export function HomePage() {
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const queryClient = useQueryClient()

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const favoriteMutation = useMutation({
    mutationFn: api.toggleFavorite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const handleToggleFavorite = (e: React.MouseEvent, projectId: string) => {
    e.preventDefault()
    e.stopPropagation()
    favoriteMutation.mutate(projectId)
  }

  const handleDelete = (e: React.MouseEvent, projectId: string, projectName: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (window.confirm(t('home.confirmDelete', { name: projectName }))) {
      deleteMutation.mutate(projectId)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'processing':
        return <Clock className="w-4 h-4 text-blue-500 animate-spin" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      default:
        return <Clock className="w-4 h-4 text-gray-400 dark:text-gray-500" />
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className={`${fontClasses.title} font-bold text-gray-900 dark:text-white`}>{t('home.title')}</h1>
          <p className={`${fontClasses.base} text-gray-600 dark:text-gray-400 mt-1`}>{t('home.subtitle')}</p>
        </div>
        <Link
          to="/upload"
          className={`flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors ${fontClasses.button}`}
        >
          <Plus className="w-5 h-5" />
          {t('home.newProject')}
        </Link>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto" />
          <p className={`${fontClasses.base} text-gray-500 dark:text-gray-400 mt-4`}>{t('common.loading')}</p>
        </div>
      ) : projects?.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <BookOpen className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto" />
          <h3 className={`${fontClasses.heading} font-medium text-gray-900 dark:text-white mt-4`}>{t('home.noProjects')}</h3>
          <p className={`${fontClasses.base} text-gray-500 dark:text-gray-400 mt-2`}>{t('home.noProjectsHint')}</p>
          <Link
            to="/upload"
            className={`inline-flex items-center gap-2 mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors ${fontClasses.button}`}
          >
            <Plus className="w-5 h-5" />
            {t('home.uploadEpub')}
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects?.map((project) => (
            <Link
              key={project.id}
              to={`/project/${project.id}`}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-sm transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className={`${fontClasses.base} font-medium text-gray-900 dark:text-white truncate`}>
                    {project.name}
                  </h3>
                  <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400 mt-1`}>
                    {project.author || t('home.unknownAuthor')}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => handleToggleFavorite(e, project.id)}
                    className={`p-1 rounded transition-colors ${
                      project.is_favorite
                        ? 'text-yellow-500 hover:text-yellow-600'
                        : 'text-gray-400 hover:text-yellow-500 hover:bg-yellow-50 dark:hover:bg-yellow-900/20'
                    }`}
                    title={t('home.favorite')}
                  >
                    <Star className={`w-4 h-4 ${project.is_favorite ? 'fill-current' : ''}`} />
                  </button>
                  {getStatusIcon(project.status)}
                  <button
                    onClick={(e) => handleDelete(e, project.id, project.name)}
                    className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                    title={t('common.delete')}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className={`flex items-center gap-4 mt-4 ${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
                <span>{project.total_chapters} {t('home.chapters')}</span>
                <span>{project.total_paragraphs} {t('home.paragraphs')}</span>
              </div>
              <p className={`${fontClasses.xs} text-gray-400 dark:text-gray-500 mt-2`}>
                {formatDate(project.created_at)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
