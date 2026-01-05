import React, { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import './UploadModal.css'

const API_BASE_URL = 'http://localhost:8000/api'

function UploadModal({ isOpen, onClose, onUploadSuccess }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)
  const dropZoneRef = useRef(null)
  
  // Always call hooks at the top level - never conditionally
  const themeContext = useTheme()
  const authContext = useAuth()
  
  // Extract values with safe defaults
  const theme = themeContext?.theme || 'light'
  const isAuthenticated = authContext?.isAuthenticated || false

  // All hooks (including useCallback) MUST be called before any early returns
  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (dropZoneRef.current) {
      dropZoneRef.current.classList.add('drag-over')
    }
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (dropZoneRef.current) {
      dropZoneRef.current.classList.remove('drag-over')
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (dropZoneRef.current) {
      dropZoneRef.current.classList.remove('drag-over')
    }

    const droppedFiles = Array.from(e.dataTransfer.files).filter(file => 
      file.name.endsWith('.pdf')
    )
    
    if (droppedFiles.length === 0) {
      setError('Only PDF files are supported')
      return
    }
    
    if (droppedFiles.length + files.length > 10) {
      setError('Maximum 10 files allowed')
      return
    }
    
    setFiles(prev => [...prev, ...droppedFiles])
    setError(null)
  }, [files])

  // Regular functions (not hooks) can be defined after hooks
  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files).filter(file => 
      file.name.endsWith('.pdf')
    )
    if (selectedFiles.length === 0) {
      setError('Only PDF files are supported')
      return
    }
    if (selectedFiles.length + files.length > 10) {
      setError('Maximum 10 files allowed')
      return
    }
    setFiles(prev => [...prev, ...selectedFiles])
    setError(null)
  }

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select at least one file')
      return
    }

    setUploading(true)
    setError(null)

    // Close modal immediately - don't wait for response
    // Processing happens asynchronously in the background
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const endpoint = isAuthenticated ? 'upload-batch' : 'upload-batch-test'
    const uploadPromise = axios.post(
      `${API_BASE_URL}/documents/${endpoint}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )

    // Close modal and call success handler immediately
    handleClose()
    onUploadSuccess({ message: `Uploading ${files.length} file(s)...` })

    // Handle response/errors in background (won't block modal closing)
    uploadPromise
      .then((response) => {
        // Success - response handled by parent component
        if (onUploadSuccess) {
          onUploadSuccess(response.data)
        }
      })
      .catch((err) => {
        console.error('Upload error:', err)
        // Show error to user (could use a toast notification)
        alert(err.response?.data?.detail || 'Failed to upload documents. Please try again.')
      })
  }

  const handleClose = () => {
    setFiles([])
    setError(null)
    setUploading(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose} data-theme={theme}>
      <div 
        className="modal-content" 
        onClick={(e) => e.stopPropagation()}
        data-theme={theme}
      >
        <div className="modal-header">
          <h2>Upload Documents</h2>
          <button className="modal-close" onClick={handleClose} aria-label="Close modal">×</button>
        </div>

        <div className="modal-body">
          <div className="upload-limit-info">
            Upload up to 10 PDF documents
          </div>

          <div
            ref={dropZoneRef}
            className="drop-zone"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="drop-zone-content">
              <div className="drop-zone-icon">📄</div>
              <p className="drop-zone-text">
                Drag and drop PDF files here, or click to select
              </p>
              <p className="drop-zone-hint">
                {files.length > 0 ? `${files.length} file(s) selected` : 'Select up to 10 PDF files'}
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              onChange={handleFileSelect}
              className="file-input-hidden"
            />
          </div>

          {files.length > 0 && (
            <div className="file-list">
              <h3>Selected Files ({files.length}/10)</h3>
              <div className="file-items">
                {files.map((file, index) => (
                  <div key={index} className="file-item">
                    <span className="file-name">{file.name}</span>
                    <button
                      className="file-remove"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeFile(index)
                      }}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="error-message">{error}</div>
          )}

          <div className="modal-actions">
            <button
              className="button-secondary"
              onClick={handleClose}
              disabled={uploading}
            >
              Cancel
            </button>
            <button
              className="button-primary"
              onClick={handleUpload}
              disabled={files.length === 0 || uploading}
            >
              {uploading ? 'Uploading...' : `Upload ${files.length} File${files.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default UploadModal
















