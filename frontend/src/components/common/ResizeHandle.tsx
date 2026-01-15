import { useCallback, useEffect, useState } from 'react'

interface ResizeHandleProps {
  onResize: (delta: number) => void
  onResizeEnd?: () => void
  direction?: 'horizontal' | 'vertical'
  className?: string
}

export function ResizeHandle({
  onResize,
  onResizeEnd,
  direction = 'horizontal',
  className = '',
}: ResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [startPos, setStartPos] = useState(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
    setStartPos(direction === 'horizontal' ? e.clientX : e.clientY)
  }, [direction])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault()
      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY
      const delta = currentPos - startPos
      setStartPos(currentPos)
      onResize(delta)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      onResizeEnd?.()
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    // Add cursor style to body during drag
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDragging, startPos, direction, onResize, onResizeEnd])

  const isHorizontal = direction === 'horizontal'

  return (
    <div
      onMouseDown={handleMouseDown}
      className={`
        ${isHorizontal ? 'w-3 cursor-col-resize' : 'h-3 cursor-row-resize'}
        ${isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-gray-200 dark:hover:bg-gray-700'}
        transition-colors flex-shrink-0 group relative
        flex items-center justify-center
        ${className}
      `}
      style={{ touchAction: 'none' }}
    >
      {/* Larger invisible hit area for easier grabbing */}
      <div
        className={`
          absolute z-10
          ${isHorizontal ? 'inset-y-0 -left-2 -right-2 cursor-col-resize' : 'inset-x-0 -top-2 -bottom-2 cursor-row-resize'}
        `}
        onMouseDown={handleMouseDown}
      />
      {/* Grip dots indicator - centered using flex parent */}
      <div
        className={`
          flex ${isHorizontal ? 'flex-col' : 'flex-row'} gap-0.5
        `}
      >
        <div className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500" />
        <div className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500" />
        <div className="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500" />
      </div>
    </div>
  )
}

