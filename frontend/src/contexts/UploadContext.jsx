import React, { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react'
import axios from 'axios'
import { useAuth } from './AuthContext'
import { useStatusStream } from '../hooks/useStatusStream'
import { API_BASE_URL } from '../config'

export const UploadStateContext = createContext()
export const UploadDispatchContext = createContext()

export const useUploadState = () => {
    const context = useContext(UploadStateContext)
    if (!context) {
        throw new Error('useUploadState must be used within UploadProvider')
    }
    return context
}

export const useUploadDispatch = () => {
    const context = useContext(UploadDispatchContext)
    if (!context) {
        throw new Error('useUploadDispatch must be used within UploadProvider')
    }
    return context
}

// Legacy hook returning both
export const useUpload = () => {
    const state = useUploadState()
    const dispatch = useUploadDispatch()
    return { ...state, ...dispatch }
}

export const UploadProvider = ({ children }) => {
    const { isAuthenticated, token } = useAuth()
    const [uploadingDocuments, setUploadingDocuments] = useState([])
    const [showUploadProgress, setShowUploadProgress] = useState(false)
    const [processingLogs, setProcessingLogs] = useState(new Map())
    const [isStreaming, setIsStreaming] = useState(false)

    // Drip Buffer Refs
    const messageQueueRef = useRef([])
    const lastSeenDataRef = useRef(new Map()) // documentId -> { milestones: {}, logCount: 0 }
    const animationTimerRef = useRef(null)

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

    // Drip Logic: Process one event from the queue at a time
    useEffect(() => {
        const processNextEvent = () => {
            const queueLength = messageQueueRef.current.length
            if (queueLength > 0) {
                // Determine burst size: process more events if the queue is backing up
                const burstSize = queueLength > 20 ? 4 : (queueLength > 10 ? 2 : 1)

                for (let i = 0; i < burstSize; i++) {
                    if (messageQueueRef.current.length === 0) break

                    const event = messageQueueRef.current.shift()
                    setIsStreaming(true)

                    if (event.type === 'DOCUMENT_METADATA_UPDATE') {
                        setUploadingDocuments(prev => {
                            const index = prev.findIndex(d => d.id === event.documentId)
                            if (index === -1) return [...prev, event.data]
                            const newDocs = [...prev]
                            newDocs[index] = { ...newDocs[index], ...event.data }
                            return newDocs
                        })
                    } else if (event.type === 'MILESTONE_UPDATE') {
                        setUploadingDocuments(prev => {
                            const index = prev.findIndex(d => d.id === event.documentId)
                            if (index === -1) return prev
                            const newDocs = [...prev]
                            const doc = { ...newDocs[index] }
                            const progress = { ...(doc.financial_statement_progress || { milestones: {} }) }
                            const milestones = { ...progress.milestones }
                            milestones[event.milestoneKey] = {
                                ...milestones[event.milestoneKey],
                                status: event.status,
                                message: event.message
                            }
                            progress.milestones = milestones
                            doc.financial_statement_progress = progress

                            // Also update global doc status if it's an indexing status change
                            if (event.milestoneKey === 'index') {
                                doc.indexing_status = event.status === 'completed' ? 'indexed' : 'indexing'
                            }

                            newDocs[index] = doc
                            return newDocs
                        })
                    } else if (event.type === 'REMOVE_DOCUMENT') {
                        setUploadingDocuments(prev => prev.filter(d => d.id !== event.documentId))
                    } else if (event.type === 'LOG') {
                        // Accumulate logs in processingLogs Map
                        setProcessingLogs(prev => {
                            const newMap = new Map(prev)
                            const currentLogs = newMap.get(event.documentId) || []
                            const isDuplicate = currentLogs.some(l =>
                                l.message === event.log.message && l.timestamp === event.log.timestamp
                            )
                            if (!isDuplicate) {
                                newMap.set(event.documentId, [...currentLogs, event.log])
                            }
                            return newMap
                        })
                    }
                }
            } else {
                setIsStreaming(false)
            }
        }

        animationTimerRef.current = setInterval(processNextEvent, 600) // Slightly faster base drip (600ms)

        return () => {
            if (animationTimerRef.current) clearInterval(animationTimerRef.current)
        }
    }, [])

    // Update uploadingDocuments from SSE stream (Now populates the drip queue)
    useEffect(() => {
        if (isConnected && activeDocuments) {
            const currentDataStr = JSON.stringify(activeDocuments)
            if (currentDataStr === previousActiveDocumentsRef.current) return
            previousActiveDocumentsRef.current = currentDataStr

            activeDocuments.forEach(doc => {
                const docId = doc.id
                const lastSeen = lastSeenDataRef.current.get(docId) || { milestones: {}, status: null, metadata: {} }

                // 1. Metadata Changes
                const currentMetadata = {
                    filename: doc.filename,
                    ticker: doc.ticker,
                    duplicate_detected: doc.duplicate_detected,
                    indexing_status: doc.indexing_status,
                    analysis_status: doc.analysis_status
                }
                if (JSON.stringify(currentMetadata) !== JSON.stringify(lastSeen.metadata)) {
                    messageQueueRef.current.push({
                        type: 'DOCUMENT_METADATA_UPDATE',
                        documentId: docId,
                        data: doc
                    })
                }

                // 2. Granular Milestone Changes
                const progress = doc.financial_statement_progress
                if (progress && progress.milestones) {
                    Object.entries(progress.milestones).forEach(([key, milestone]) => {
                        const lastMilestone = lastSeen.milestones[key] || { status: 'pending' }
                        const newLogs = milestone.logs || []
                        const seenLogCount = lastMilestone.seenLogCount || 0

                        // A. Transition to In Progress (if it wasn't already)
                        if (milestone.status === 'in_progress' && lastMilestone.status !== 'in_progress') {
                            messageQueueRef.current.push({
                                type: 'MILESTONE_UPDATE',
                                documentId: docId,
                                milestoneKey: key,
                                status: 'in_progress',
                                message: milestone.message
                            })
                        }

                        // B. New Logs (Always queue these)
                        if (newLogs.length > seenLogCount) {
                            const frisch = newLogs.slice(seenLogCount)
                            frisch.forEach(log => {
                                const logObj = typeof log === 'string'
                                    ? { message: log, source: 'system', timestamp: new Date().toISOString() }
                                    : { ...log, source: log.source || 'system', timestamp: log.timestamp || new Date().toISOString() }

                                messageQueueRef.current.push({
                                    type: 'LOG',
                                    documentId: docId,
                                    milestoneKey: key,
                                    log: logObj
                                })
                            })
                        }

                        // C. Transition to Terminal (Completed/Error/etc)
                        const isTerminal = ['completed', 'error', 'warning', 'skipped'].includes(milestone.status)
                        const wasTerminal = ['completed', 'error', 'warning', 'skipped'].includes(lastMilestone.status)

                        if (isTerminal && (!wasTerminal || milestone.status !== lastMilestone.status)) {
                            messageQueueRef.current.push({
                                type: 'MILESTONE_UPDATE',
                                documentId: docId,
                                milestoneKey: key,
                                status: milestone.status,
                                message: milestone.message
                            })
                        }
                    })
                }

                // Update last seen tracker
                lastSeenDataRef.current.set(docId, {
                    metadata: currentMetadata,
                    milestones: Object.fromEntries(
                        Object.entries(doc.financial_statement_progress?.milestones || {}).map(([k, v]) => [
                            k,
                            { status: v.status, seenLogCount: (v.logs || []).length }
                        ])
                    )
                })
            })

            // 3. Detect removals (if a doc was in lastSeen but not in activeDocuments)
            const activeIds = new Set(activeDocuments.map(d => d.id))
            for (const [id, _] of lastSeenDataRef.current.entries()) {
                if (!activeIds.has(id)) {
                    messageQueueRef.current.push({
                        type: 'REMOVE_DOCUMENT',
                        documentId: id
                    })
                    lastSeenDataRef.current.delete(id)
                }
            }

            // Auto-hide logic (Check current state of activeDocuments, not the dripped state)
            const allFinished = activeDocuments.length === 0 ||
                activeDocuments.every(doc => {
                    const status = (doc.status || '').toLowerCase()
                    const idxStatus = (doc.indexing_status || '').toLowerCase()
                    const terminal = [
                        'processing_complete',
                        'extraction_failed',
                        'classified',
                        'classification_failed',
                        'indexing_failed',
                        'upload_failed',
                        'error',
                        'indexed', // Added 'indexed' as a fallback for non-earnings docs
                        'duplicate_detected'
                    ]
                    return terminal.includes(status) || terminal.includes(idxStatus)
                })

            if (allFinished && showUploadProgress) {
                // We keep it open a bit longer if we are still dripping
                if (messageQueueRef.current.length === 0) {
                    setShowUploadProgress(false)
                }
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

    const stateValue = {
        uploadingDocuments,
        processingLogs,
        isStreaming,
        showUploadProgress,
        isConnected, // Expose SSE connection status
        sseError // Expose SSE errors
    }

    const dispatchValue = useMemo(() => ({
        setShowUploadProgress,
        loadUploadProgress,
    }), [loadUploadProgress])

    return (
        <UploadDispatchContext.Provider value={dispatchValue}>
            <UploadStateContext.Provider value={stateValue}>
                {children}
            </UploadStateContext.Provider>
        </UploadDispatchContext.Provider>
    )
}
