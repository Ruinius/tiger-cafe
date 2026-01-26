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

  const hasActiveUploads = isUploading || uploadingDocuments.some(doc => {
    const status = (doc.status || '').toLowerCase()
    const idxStatus = (doc.indexing_status || '').toLowerCase()

    // Terminal statuses that mean "I'm not actively doing heavy work anymore"
    const terminalStatuses = [
      'processing_complete',
      'extraction_failed',
      'classified',
      'classification_failed',
      'indexing_failed',
      'upload_failed',
      'error'
    ]

    // For earnings announcements, 'indexed' is NOT terminal (extraction follows)
    // For others, 'indexed' might be. But we use processing_complete for earnings.
    return !terminalStatuses.includes(status) && !terminalStatuses.includes(idxStatus)
  })

  return {
    isUploadModalOpen,
    openUploadModal,
    closeUploadModal,
    handleUploadSuccess,
    handleReplaceAndIndex,
    handleCancelDuplicate,
    checkDuplicates: (files) => checkDuplicates(files, token),
    hasActiveUploads,
    uploadingDocuments,
    showUploadProgress,
    setShowUploadProgress,
  }
}

// Add duplicate check function
async function checkDuplicates(files, token) {
  const { computeQuickHash } = await import('../utils/fileHash');

  const filesMetadata = await Promise.all(Array.from(files).map(async (file) => ({
    filename: file.name,
    size: file.size,
    quick_hash: await computeQuickHash(file)
  })));

  const response = await axios.post(`${API_BASE_URL}/documents/check-duplicates-batch`, filesMetadata, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
  });

  return response.data;
}
