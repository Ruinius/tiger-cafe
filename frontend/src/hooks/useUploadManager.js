import { useState, useCallback } from 'react'
import axios from 'axios'
import { useUpload } from '../contexts/UploadContext'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

export function useUploadManager(onUploadComplete) {
  const { uploadingDocuments, showUploadProgress, setShowUploadProgress, loadUploadProgress } = useUpload()
  const { isAuthenticated, token } = useAuth()
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const openUploadModal = useCallback(() => setIsUploadModalOpen(true), [])
  const closeUploadModal = useCallback(() => setIsUploadModalOpen(false), [])

  const handleUploadSuccess = useCallback(async (response) => {
    setIsUploading(true)
    await loadUploadProgress()
    setShowUploadProgress(false) // Background processing
    if (onUploadComplete) onUploadComplete()
    setIsUploading(false)
  }, [loadUploadProgress, setShowUploadProgress, onUploadComplete])

  const handleReplaceAndIndex = useCallback(async (documentId) => {
    try {
      const endpoint = isAuthenticated ? 'replace-and-index' : 'replace-and-index-test'
      await axios.post(`${API_BASE_URL}/documents/${documentId}/${endpoint}`, {}, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      loadUploadProgress()
    } catch (error) {
      console.error('Error replacing document:', error)
    }
  }, [isAuthenticated, token, loadUploadProgress])

  const handleCancelDuplicate = useCallback(async (documentId) => {
    if (!window.confirm('Are you sure you want to cancel this upload? The document will be removed.')) {
      return
    }
    try {
      const endpoint = isAuthenticated ? '' : '/test'
      await axios.delete(`${API_BASE_URL}/documents/${documentId}${endpoint}`, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      loadUploadProgress()
    } catch (error) {
      console.error('Error canceling document:', error)
      alert('Failed to cancel document. Please try again.')
    }
  }, [isAuthenticated, token, loadUploadProgress])

  const hasActiveUploads = uploadingDocuments.length > 0 || isUploading

  return {
    isUploadModalOpen,
    openUploadModal,
    closeUploadModal,
    handleUploadSuccess,
    handleReplaceAndIndex,
    handleCancelDuplicate,
    hasActiveUploads,
    uploadingDocuments,
    showUploadProgress,
    setShowUploadProgress
  }
}
