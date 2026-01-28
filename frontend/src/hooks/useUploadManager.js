import { useState, useCallback } from 'react'
import axios from 'axios'
import { useUploadDispatch, useUploadState } from '../contexts/UploadContext'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

/**
 * Hook for managing the upload modal and triggering upload actions.
 * Does NOT subscribe to rapid status updates, so it won't trigger re-renders on log messages.
 * Use this in layout components like Dashboard.
 */
export function useUploadModalLogic(onUploadComplete) {
  const { setShowUploadProgress, loadUploadProgress } = useUploadDispatch()
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

  return {
    isUploadModalOpen,
    openUploadModal,
    closeUploadModal,
    handleUploadSuccess,
    handleReplaceAndIndex,
    handleCancelDuplicate,
    checkDuplicates: (files) => checkDuplicates(files, token),
    isUploading
  }
}

/**
 * Full upload manager that includes current upload status.
 * WARNING: This will cause re-renders whenever upload logs/status change.
 * Only use in components that need to display active progress (e.g. MissionControl, CompanyList).
 */
export function useUploadManager(onUploadComplete) {
  // Get actions/modal state (stable-ish)
  const modalLogic = useUploadModalLogic(onUploadComplete)

  // Get volatile state
  const { uploadingDocuments, showUploadProgress } = useUploadState()
  const { setShowUploadProgress } = useUploadDispatch() // Need this too if not returned by modalLogic? 
  // Actually modalLogic doesn't return setShowUploadProgress.

  const hasActiveUploads = modalLogic.isUploading || uploadingDocuments.some(doc => {
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
      'error',
      'duplicate_detected'
    ]

    return !terminalStatuses.includes(status) && !terminalStatuses.includes(idxStatus)
  })

  return {
    ...modalLogic,
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
