import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from './AuthContext'
import { useStatusStream } from '../hooks/useStatusStream'
import { API_BASE_URL } from '../config'

export const UploadContext = createContext()

export const useUpload = () => {
    const context = useContext(UploadContext)
    if (!context) {
        throw new Error('useUpload must be used within UploadProvider')
    }
    return context
}

export const UploadProvider = ({ children }) => {
    const { isAuthenticated, token } = useAuth()
    const [uploadingDocuments, setUploadingDocuments] = useState([])
    const [showUploadProgress, setShowUploadProgress] = useState(false)

    // Use SSE for real-time status updates instead of polling
    const { activeDocuments, isConnected, error: sseError } = useStatusStream()

    // Fallback: Load upload progress manually (used for initial load or when SSE fails)
    const loadUploadProgress = useCallback(async () => {
        if (!isAuthenticated || !token) return

        try {
            const response = await axios.get(`${API_BASE_URL}/documents/upload-progress`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            setUploadingDocuments(response.data)

            // Check if all documents have finished indexing
            const allFinished = response.data.length === 0 ||
                response.data.every(doc => {
                    const status = doc.indexing_status?.toLowerCase()
                    return status === 'indexed' || status === 'error'
                })

            // If all finished and showing progress, hide the progress view
            if (allFinished && showUploadProgress) {
                setShowUploadProgress(false)
            }
        } catch (error) {
            console.error('Error loading upload progress:', error)
        }
    }, [isAuthenticated, token, showUploadProgress])

    // Track previous SSE data to avoid unnecessary updates
    const previousActiveDocumentsRef = React.useRef(null)

    // Update uploadingDocuments from SSE stream
    useEffect(() => {
        if (isConnected && activeDocuments) {
            // Only update if data actually changed (deep equality check)
            const currentData = JSON.stringify(activeDocuments)
            const previousData = previousActiveDocumentsRef.current

            if (currentData !== previousData) {
                previousActiveDocumentsRef.current = currentData
                setUploadingDocuments(activeDocuments)
            }

            // Auto-hide progress modal when all uploads complete
            const allFinished = activeDocuments.length === 0 ||
                activeDocuments.every(doc => {
                    const status = doc.status?.toLowerCase() || doc.indexing_status?.toLowerCase()
                    return status === 'indexed' || status === 'processing_complete' || status === 'classified' || status === 'error'
                })

            if (allFinished && showUploadProgress) {
                setShowUploadProgress(false)
            }
        }
    }, [activeDocuments, isConnected, showUploadProgress])

    // Fallback to manual load if SSE fails
    useEffect(() => {
        if (sseError && isAuthenticated) {
            console.warn('[UploadContext] SSE error, falling back to manual load:', sseError)
            loadUploadProgress()
        }
    }, [sseError, isAuthenticated, loadUploadProgress])

    // Initial load on mount
    useEffect(() => {
        loadUploadProgress()
    }, []) // Only on mount

    const value = {
        uploadingDocuments,
        showUploadProgress,
        setShowUploadProgress,
        loadUploadProgress,
        isConnected, // Expose SSE connection status
        sseError // Expose SSE errors
    }

    return (
        <UploadContext.Provider value={value}>
            {children}
        </UploadContext.Provider>
    )
}
