import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Upload, FileText, X, Loader2 } from 'lucide-react'
import { api } from '../services/api/client'
import { useTranslation, useAppStore, fontSizeClasses } from '../stores/appStore'

export function UploadPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const fontSize = useAppStore((state) => state.fontSize)
  const fontClasses = fontSizeClasses[fontSize]
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: api.uploadEpub,
    onSuccess: (data) => {
      // Navigate to the new 4-step workflow
      navigate(`/project/${data.project_id}/analysis`)
    },
  })

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile?.name.endsWith('.epub')) {
      setFile(droppedFile)
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile?.name.endsWith('.epub')) {
      setFile(selectedFile)
    }
  }, [])

  const handleUpload = () => {
    if (file) {
      uploadMutation.mutate(file)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className={`${fontClasses.title} font-bold text-gray-900 dark:text-white mb-2`}>{t('upload.title')}</h1>
      <p className={`${fontClasses.base} text-gray-600 dark:text-gray-400 mb-8`}>{t('upload.subtitle')}</p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          isDragging
            ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
            : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
        }`}
      >
        {file ? (
          <div className="flex items-center justify-center gap-4">
            <FileText className="w-12 h-12 text-blue-500 dark:text-blue-400" />
            <div className="text-left">
              <p className={`${fontClasses.base} font-medium text-gray-900 dark:text-white`}>{file.name}</p>
              <p className={`${fontClasses.sm} text-gray-500 dark:text-gray-400`}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              onClick={() => setFile(null)}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            >
              <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </button>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto" />
            <p className={`${fontClasses.base} text-gray-600 dark:text-gray-400 mt-4`}>
              {t('upload.dropHint')}
              <label className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 cursor-pointer ml-1">
                {t('upload.clickToSelect')}
                <input
                  type="file"
                  accept=".epub"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            </p>
            <p className={`${fontClasses.sm} text-gray-400 dark:text-gray-500 mt-2`}>{t('upload.formatHint')}</p>
          </>
        )}
      </div>

      {/* Error message */}
      {uploadMutation.isError && (
        <div className={`mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 ${fontClasses.base}`}>
          {t('upload.uploadFailed')}：{(uploadMutation.error as Error).message}
        </div>
      )}

      {/* Upload button */}
      <div className="mt-6 flex justify-end">
        <button
          onClick={handleUpload}
          disabled={!file || uploadMutation.isPending}
          className={`flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors ${fontClasses.button}`}
        >
          {uploadMutation.isPending ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {t('upload.uploading')}
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              {t('upload.startUpload')}
            </>
          )}
        </button>
      </div>
    </div>
  )
}
