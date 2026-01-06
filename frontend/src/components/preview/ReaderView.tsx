import { useState } from 'react'
import { ChapterContent, ChapterImage } from '../../services/api/client'
import { useTranslation } from '../../stores/appStore'

export type ContentMode = 'translation' | 'original' | 'bilingual'

interface ReaderViewProps {
  content: ChapterContent
  projectId: string
  contentMode: ContentMode
}

// Map html_tag to appropriate React element rendering
function renderParagraph(
  text: string,
  htmlTag: string,
  className: string,
  key: string
): React.ReactNode {
  const baseClasses = className

  switch (htmlTag) {
    case 'h1':
      return (
        <h1 key={key} className={`text-3xl font-bold mt-8 mb-4 ${baseClasses}`}>
          {text}
        </h1>
      )
    case 'h2':
      return (
        <h2 key={key} className={`text-2xl font-bold mt-6 mb-3 ${baseClasses}`}>
          {text}
        </h2>
      )
    case 'h3':
      return (
        <h3 key={key} className={`text-xl font-semibold mt-5 mb-2 ${baseClasses}`}>
          {text}
        </h3>
      )
    case 'h4':
      return (
        <h4 key={key} className={`text-lg font-semibold mt-4 mb-2 ${baseClasses}`}>
          {text}
        </h4>
      )
    case 'h5':
    case 'h6':
      return (
        <h5 key={key} className={`text-base font-semibold mt-3 mb-2 ${baseClasses}`}>
          {text}
        </h5>
      )
    case 'blockquote':
      return (
        <blockquote
          key={key}
          className={`border-l-4 border-gray-300 dark:border-gray-600 pl-4 my-4 italic ${baseClasses}`}
        >
          {text}
        </blockquote>
      )
    case 'li':
      return (
        <li key={key} className={`ml-6 list-disc ${baseClasses}`}>
          {text}
        </li>
      )
    default:
      // Default to paragraph
      return (
        <p key={key} className={`my-3 leading-relaxed ${baseClasses}`}>
          {text}
        </p>
      )
  }
}

function ImageDisplay({ image, projectId }: { image: ChapterImage; projectId: string }) {
  const { t } = useTranslation()
  const [hasError, setHasError] = useState(false)

  // Use the url field if available, otherwise construct from src
  const imageUrl = image.url || `/api/v1/preview/${projectId}/image/${image.src}`

  if (hasError) {
    return (
      <div className="my-6 flex justify-center">
        <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-8 text-gray-500 dark:text-gray-400 text-sm">
          {t('preview.imageLoadError')}
        </div>
      </div>
    )
  }

  return (
    <figure className="my-6 flex flex-col items-center">
      <img
        src={imageUrl}
        alt={image.alt || ''}
        onError={() => setHasError(true)}
        className="max-w-full h-auto rounded-lg shadow-md"
        style={{ maxHeight: '70vh' }}
      />
      {image.caption && (
        <figcaption className="mt-2 text-sm text-gray-500 dark:text-gray-400 italic text-center">
          {image.caption}
        </figcaption>
      )}
    </figure>
  )
}

export function ReaderView({ content, projectId, contentMode }: ReaderViewProps) {
  const { t } = useTranslation()

  const textColorClass = 'text-gray-800 dark:text-gray-200'
  const originalColorClass = 'text-gray-600 dark:text-gray-400'

  // Sort images by position for potential inline rendering
  const sortedImages = [...(content.images || [])].sort((a, b) => a.position - b.position)

  // For now, show images at the top if they exist (like chapter header images)
  // In a future version, we could interleave based on xpath or position
  const headerImages = sortedImages.filter((_, i) => i === 0)
  const otherImages = sortedImages.filter((_, i) => i > 0)

  return (
    <div className="reader-view">
      {/* Reader Content Area */}
      <article className="max-w-2xl mx-auto px-4 py-8 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        {/* Chapter Title */}
        {content.title && (
          <h1 className="text-3xl font-serif font-bold text-center mb-8 text-gray-900 dark:text-gray-100">
            {content.title}
          </h1>
        )}

        {/* Header Images (like cover or chapter illustrations) */}
        {headerImages.map((image, i) => (
          <ImageDisplay key={`header-img-${i}`} image={image} projectId={projectId} />
        ))}

        {/* Main Content */}
        <div className="font-serif text-lg leading-relaxed">
          {content.paragraphs.length === 0 ? (
            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
              {t('preview.noContent')}
            </p>
          ) : (
            content.paragraphs.map((para) => {
              const hasTranslation = !!para.translated_text

              if (contentMode === 'original') {
                return renderParagraph(
                  para.original_text,
                  para.html_tag,
                  textColorClass,
                  `para-${para.id}`
                )
              }

              if (contentMode === 'translation') {
                return renderParagraph(
                  hasTranslation ? para.translated_text! : para.original_text,
                  para.html_tag,
                  hasTranslation ? textColorClass : `${originalColorClass} italic`,
                  `para-${para.id}`
                )
              }

              // Bilingual mode
              return (
                <div key={`para-${para.id}`} className="mb-6">
                  {renderParagraph(
                    para.original_text,
                    para.html_tag,
                    originalColorClass,
                    `para-orig-${para.id}`
                  )}
                  {hasTranslation && (
                    <div className="mt-2 pl-4 border-l-2 border-blue-300 dark:border-blue-600">
                      {renderParagraph(
                        para.translated_text!,
                        para.html_tag,
                        'text-blue-800 dark:text-blue-300',
                        `para-trans-${para.id}`
                      )}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Other Images at the end */}
        {otherImages.length > 0 && (
          <div className="mt-8 pt-8 border-t border-gray-200 dark:border-gray-700">
            {otherImages.map((image, i) => (
              <ImageDisplay key={`other-img-${i}`} image={image} projectId={projectId} />
            ))}
          </div>
        )}
      </article>
    </div>
  )
}
