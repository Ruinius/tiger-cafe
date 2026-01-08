import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import axios from 'axios'
import { useAuth } from './AuthContext'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
    const progressIntervalRef = useRef(null)

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

    // Poll for upload progress only when there are active uploads or when showing progress
    useEffect(() => {
        // Clear any existing interval
        if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current)
            progressIntervalRef.current = null
        }

        // Only start polling if there are active uploads or we're showing the progress view
        const hasActiveUploads = uploadingDocuments.some(doc => {
            const status = doc.indexing_status?.toLowerCase()
            return status !== 'indexed' && status !== 'error'
        })
        const shouldPoll = hasActiveUploads || showUploadProgress

        if (shouldPoll) {
            // Poll every 3 seconds
            progressIntervalRef.current = setInterval(() => {
                loadUploadProgress()
            }, 3000)
        }

        return () => {
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current)
                progressIntervalRef.current = null
            }
        }
    }, [uploadingDocuments.length, showUploadProgress, loadUploadProgress])

    // Initial load
    useEffect(() => {
        loadUploadProgress()
    }, []) // Only on mount

    const value = {
        uploadingDocuments,
        showUploadProgress,
        setShowUploadProgress,
        loadUploadProgress
    }

    return (
        <UploadContext.Provider value={value}>
            {children}
        </UploadContext.Provider>
    )
}
