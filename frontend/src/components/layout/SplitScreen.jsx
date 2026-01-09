import React, { useState, useRef, useEffect } from 'react'
import './SplitScreen.css'

function SplitScreen({ left, right, splitRatio, onSplitChange }) {
  const containerRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const dividerRef = useRef(null)

  const minLeft = 0.2
  const maxLeft = 0.8

  const handleMouseDown = (e) => {
    setIsDragging(true)
    e.preventDefault()
  }

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !containerRef.current) return

      const container = containerRef.current
      const containerRect = container.getBoundingClientRect()
      const newRatio = (e.clientX - containerRect.left) / containerRect.width

      // Clamp between min and max
      const clampedRatio = Math.max(minLeft, Math.min(maxLeft, newRatio))
      onSplitChange(clampedRatio)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, onSplitChange])

  return (
    <div className="split-screen" ref={containerRef}>
      <div 
        className="split-panel split-panel-left"
        style={{ width: `${splitRatio * 100}%` }}
      >
        {left}
      </div>
      <div
        className="split-divider"
        ref={dividerRef}
        onMouseDown={handleMouseDown}
        style={{ cursor: isDragging ? 'col-resize' : 'col-resize' }}
      >
        <div className="divider-handle" />
      </div>
      <div 
        className="split-panel split-panel-right"
        style={{ width: `${(1 - splitRatio) * 100}%` }}
      >
        {right}
      </div>
    </div>
  )
}

export default SplitScreen


