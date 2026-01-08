import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import UploadModal from './UploadModal'
import './LeftPanel.css'

const API_BASE_URL = 'http://localhost:8000/api'

function LeftPanel({ selectedCompany, selectedDocument, onCompanySelect, onDocumentSelect, onBack }) {
  const [companies, setCompanies] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [showUploadProgress, setShowUploadProgress] = useState(false)
  const [uploadingDocuments, setUploadingDocuments] = useState([])
  const [isUploading, setIsUploading] = useState(false) // Track upload state to disable button immediately
  const [pdfUrl, setPdfUrl] = useState(null)
  const pdfUrlRef = useRef(null)
  const progressIntervalRef = useRef(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isCheckingProcessingStatus, setIsCheckingProcessingStatus] = useState(true) // Default to true to disable buttons until status is checked
  const [hasFinancialStatements, setHasFinancialStatements] = useState(false)
  const [documentChunks, setDocumentChunks] = useState(null)
  const [chunksLoading, setChunksLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState(new Set())
  const { isAuthenticated, token } = useAuth()
  const processingTriggeredRef = useRef(false)
  const processingActionRef = useRef(null)

  // Debouncing state to prevent duplicate button clicks
  const [buttonDebouncing, setButtonDebouncing] = useState({})

  // Document visibility state
  const [isDocumentExpanded, setIsDocumentExpanded] = useState(false)
  const debounceTimers = useRef({})

  // Debounce utility function
  const debounceAction = useCallback((actionKey, action, delay = 1000) => {
    // If already debouncing this action, ignore
    if (buttonDebouncing[actionKey]) {
      return
    }

    // Set debouncing state
    setButtonDebouncing(prev => ({ ...prev, [actionKey]: true }))

    // Execute the action
    action()

    // Clear any existing timer for this action
    if (debounceTimers.current[actionKey]) {
      clearTimeout(debounceTimers.current[actionKey])
    }

    // Set timer to clear debouncing state
    debounceTimers.current[actionKey] = setTimeout(() => {
      setButtonDebouncing(prev => {
        const newState = { ...prev }
        delete newState[actionKey]
        return newState
      })
      delete debounceTimers.current[actionKey]
    }, delay)
  }, [buttonDebouncing])

  // Cleanup debounce timers on unmount
  useEffect(() => {
    return () => {
      Object.values(debounceTimers.current).forEach(timer => clearTimeout(timer))
    }
  }, [])

  const loadUploadProgress = useCallback(async () => {
    try {
      const endpoint = isAuthenticated ? 'upload-progress' : 'upload-progress-test'
      const response = await axios.get(`${API_BASE_URL}/documents/${endpoint}`, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      setUploadingDocuments(response.data)

      // Check if all documents have finished indexing (no active uploads/processing)
      const allFinished = response.data.length === 0 ||
        response.data.every(doc => {
          const status = doc.indexing_status?.toLowerCase()
          return status === 'indexed' || status === 'error'
        })

      // If all documents finished and we're showing progress, automatically redirect
      if (allFinished && showUploadProgress) {
        // Stop polling since all uploads are done
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current)
          progressIntervalRef.current = null
        }

        setShowUploadProgress(false)
        // Clear any selected company/document to ensure we're on companies list
        if (selectedCompany || selectedDocument) {
          onBack()
          // If we had a selected document, we need to go back twice (document -> company -> companies)
          if (selectedDocument && selectedCompany) {
            setTimeout(() => onBack(), 100)
          }
        }
        loadCompanies() // Refresh companies list
      }
    } catch (error) {
      console.error('Error loading upload progress:', error)
    }
  }, [isAuthenticated, token, showUploadProgress, selectedCompany, selectedDocument, onBack])

  // Check if financial statements exist for the selected document
  const checkFinancialStatements = useCallback(async (documentId) => {
    if (!documentId) {
      setHasFinancialStatements(false)
      return
    }

    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}

      // Check both balance sheet and income statement
      const [balanceSheetResponse, incomeStatementResponse] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/documents/${documentId}/balance-sheet`, { headers }),
        axios.get(`${API_BASE_URL}/documents/${documentId}/income-statement`, { headers })
      ])

      // Check if balance sheet exists
      // Must be fulfilled (not rejected), have HTTP status 200, and data.status === 'exists'
      let hasBalanceSheet = false
      if (balanceSheetResponse.status === 'fulfilled') {
        const response = balanceSheetResponse.value
        // Check if it's a successful response (status 200) and has the expected data structure
        hasBalanceSheet = response.status === 200 &&
          response.data?.status === 'exists'
      }

      // Check if income statement exists
      // Must be fulfilled (not rejected), have HTTP status 200, and data.status === 'exists'
      let hasIncomeStatement = false
      if (incomeStatementResponse.status === 'fulfilled') {
        const response = incomeStatementResponse.value
        // Check if it's a successful response (status 200) and has the expected data structure
        hasIncomeStatement = response.status === 200 &&
          response.data?.status === 'exists'
      }

      setHasFinancialStatements(hasBalanceSheet || hasIncomeStatement)
    } catch (error) {
      console.error('Error checking financial statements:', error)
      setHasFinancialStatements(false)
    }
  }, [isAuthenticated, token])

  // Reset processing states when document changes or processing completes
  // Also fetch latest document status when document is selected to ensure we have current analysis_status
  useEffect(() => {
    let isMounted = true

    if (!selectedDocument) {
      if (isMounted) {
        setIsProcessing(false)
        setIsCheckingProcessingStatus(false) // No document, so no need to check
        setHasFinancialStatements(false)
      }
      return
    }

    // Set checking state to true to disable buttons while we fetch status
    if (isMounted) {
      setIsCheckingProcessingStatus(true)
      setHasFinancialStatements(false) // Reset until we check
    }

    // Fetch latest document status to ensure we have current analysis_status
    const fetchLatestStatus = async () => {
      try {
        const endpoint = isAuthenticated ? 'status' : 'status-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
          { headers }
        )
        // Always update selectedDocument with latest status (including indexing_status)
        // This ensures polling keeps the document status current
        // CRITICAL FIX: Only call onDocumentSelect if isMounted is still true.
        // If user clicked back, isMounted will be false, preventing re-selection.
        if (isMounted && response.data && onDocumentSelect) {
          onDocumentSelect(response.data)
        }

        if (isMounted) {
          // After fetching status, we can enable buttons (they'll still be disabled if processing)
          setIsCheckingProcessingStatus(false)

          // Check if financial statements exist (only for eligible document types)
          const eligibleTypes = ['earnings_announcement', 'quarterly_filing', 'annual_filing']
          if (selectedDocument.document_type && eligibleTypes.includes(selectedDocument.document_type)) {
            await checkFinancialStatements(selectedDocument.id)
          }
        }
      } catch (error) {
        if (isMounted) {
          console.error('Error fetching latest document status:', error)
          // Even on error, stop checking so buttons can be enabled (they'll check analysis_status)
          setIsCheckingProcessingStatus(false)
          setHasFinancialStatements(false)
        }
      }
    }

    // Fetch immediately when document is selected
    fetchLatestStatus()

    // Reset button states based on current status
    // Note: This will be re-evaluated after fetchLatestStatus updates selectedDocument
    if (selectedDocument.analysis_status !== 'processing') {
      // Reset button states when processing completes
      setIsProcessing(false)
    }

    return () => {
      isMounted = false
    }
  }, [selectedDocument?.id, isAuthenticated, token, checkFinancialStatements])

  // Track last known status to avoid unnecessary updates during polling
  const lastStatusRef = useRef({ indexingStatus: null, analysisStatus: null })

  // Poll for selected document indexing status when it's being indexed
  useEffect(() => {
    if (!selectedDocument) return

    const isIndexing = selectedDocument.indexing_status === 'indexing' || selectedDocument.indexing_status === 'INDEXING'
    if (!isIndexing) {
      // Reset tracking when not indexing
      lastStatusRef.current = { indexingStatus: null, analysisStatus: null }
      return
    }

    // Initialize tracking with current status
    lastStatusRef.current = {
      indexingStatus: selectedDocument.indexing_status,
      analysisStatus: selectedDocument.analysis_status
    }

    let isMounted = true

    // Poll every 3 seconds while indexing (reduced frequency to avoid jarring updates)
    const pollInterval = setInterval(async () => {
      try {
        const endpoint = isAuthenticated ? 'status' : 'status-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
          { headers }
        )

        if (!isMounted) return

        if (response.data && onDocumentSelect) {
          const newIndexingStatus = response.data.indexing_status
          const newAnalysisStatus = response.data.analysis_status

          // Only update if status actually changed to avoid unnecessary re-renders
          if (newIndexingStatus !== lastStatusRef.current.indexingStatus ||
            newAnalysisStatus !== lastStatusRef.current.analysisStatus) {
            lastStatusRef.current.indexingStatus = newIndexingStatus
            lastStatusRef.current.analysisStatus = newAnalysisStatus
            onDocumentSelect(response.data)
          }

          // If indexing completed, stop polling
          if (newIndexingStatus !== 'indexing' && newIndexingStatus !== 'INDEXING') {
            clearInterval(pollInterval)
            lastStatusRef.current = { indexingStatus: null, analysisStatus: null }
          }
        }
      } catch (error) {
        if (isMounted) {
          console.error(`Error polling status for document ${selectedDocument.id}:`, error)
        }
      }
    }, 3000)

    return () => {
      isMounted = false
      clearInterval(pollInterval)
    }
  }, [selectedDocument?.id, selectedDocument?.indexing_status, isAuthenticated, token, onDocumentSelect])

  // Track if we're waiting for indexing to complete
  const waitingForIndexingRef = useRef(false)

  // Set waiting flag when we trigger re-indexing
  useEffect(() => {
    if (isProcessing && selectedDocument?.indexing_status === 'indexing') {
      waitingForIndexingRef.current = true
    }
  }, [isProcessing, selectedDocument?.indexing_status])

  // Watch for when indexing completes to reset isProcessing state
  useEffect(() => {
    // If we've started processing and the status is now reflected on the server,
    // we can clear the manual override flag
    if (selectedDocument?.analysis_status === 'processing' ||
      selectedDocument?.indexing_status === 'indexing' ||
      selectedDocument?.indexing_status === 'INDEXING') {
      processingTriggeredRef.current = false
    }

    if (selectedDocument && isProcessing && waitingForIndexingRef.current) {
      // Reset isProcessing when indexing completes
      if (selectedDocument.indexing_status === 'indexed' || selectedDocument.indexing_status === 'INDEXED') {
        setIsProcessing(false)
        waitingForIndexingRef.current = false
      }
    } else if (selectedDocument && isProcessing &&
      selectedDocument.indexing_status !== 'indexing' &&
      selectedDocument.indexing_status !== 'INDEXING' &&
      selectedDocument.analysis_status !== 'processing') {
      // If we just triggered processing, give it a moment to reach the server
      // and reflect in analysis_status before we allow auto-reset
      if (processingTriggeredRef.current) {
        return
      }

      // Also reset if neither indexing nor analysis is in progress
      setIsProcessing(false)
      waitingForIndexingRef.current = false
    }
  }, [selectedDocument?.indexing_status, selectedDocument?.analysis_status, isProcessing, selectedDocument])

  // Listen for event when financial statements processing completes
  useEffect(() => {
    const handleProcessingComplete = () => {
      setIsProcessing(false)
    }

    window.addEventListener('financialStatementsProcessingComplete', handleProcessingComplete)

    return () => {
      window.removeEventListener('financialStatementsProcessingComplete', handleProcessingComplete)
    }
  }, [])

  // Failsafe: Re-enable buttons after 60 seconds if processing gets stuck
  useEffect(() => {
    let timeoutId

    if (isProcessing) {
      if (processingActionRef.current === 'delete-document') {
        timeoutId = setTimeout(() => {
          console.warn('Processing timeout reached (60s). Re-enabling buttons.')
          setIsProcessing(false)
          processingTriggeredRef.current = false
          waitingForIndexingRef.current = false
        }, 60000)
      }
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
    }
  }, [isProcessing])

  // Poll for analysis_status changes when document is processing
  // This ensures buttons re-enable when processing completes (even with errors)
  useEffect(() => {
    if (!selectedDocument || selectedDocument.analysis_status !== 'processing') {
      return
    }

    let isMounted = true

    // Poll every 3 seconds while processing
    const pollInterval = setInterval(async () => {
      try {
        const endpoint = isAuthenticated ? 'status' : 'status-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
          { headers }
        )

        if (!isMounted) return

        if (response.data && onDocumentSelect) {
          const newAnalysisStatus = response.data.analysis_status

          // If processing completed (status changed from 'processing')
          if (newAnalysisStatus !== 'processing') {
            // Update document
            onDocumentSelect(response.data)

            // Reset processing state
            setIsProcessing(false)
            processingTriggeredRef.current = false

            // Re-check financial statements to update button states
            const eligibleTypes = ['earnings_announcement', 'quarterly_filing', 'annual_filing']
            if (selectedDocument.document_type && eligibleTypes.includes(selectedDocument.document_type)) {
              await checkFinancialStatements(selectedDocument.id)
            }

            // Stop polling
            clearInterval(pollInterval)
          }
        }
      } catch (error) {
        if (isMounted) {
          console.error(`Error polling analysis status for document ${selectedDocument.id}:`, error)
        }
      }
    }, 3000)

    return () => {
      isMounted = false
      clearInterval(pollInterval)
    }
  }, [selectedDocument?.id, selectedDocument?.analysis_status, isAuthenticated, token, onDocumentSelect, checkFinancialStatements])

  useEffect(() => {
    loadCompanies()
    // Initial load of upload progress
    loadUploadProgress()
  }, [loadUploadProgress])

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
      // Poll every 3 seconds (reduced frequency from 2 seconds)
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

  useEffect(() => {
    if (selectedCompany) {
      loadCompanyDocuments(selectedCompany.id)
    } else {
      setDocuments([])
    }
  }, [selectedCompany])

  // Poll for indexing status updates when documents are being indexed
  useEffect(() => {
    if (!selectedCompany || documents.length === 0) return

    const indexingDocuments = documents.filter(
      doc => doc.indexing_status === 'indexing' || doc.indexing_status === 'INDEXING'
    )

    if (indexingDocuments.length === 0) return

    // Poll every 2 seconds for indexing status
    const pollInterval = setInterval(async () => {
      for (const doc of indexingDocuments) {
        try {
          const endpoint = isAuthenticated ? 'status' : 'status-test'
          const response = await axios.get(`${API_BASE_URL}/documents/${doc.id}/${endpoint}`)
          // Update the document in the list if status changed
          setDocuments(prevDocs =>
            prevDocs.map(d =>
              d.id === doc.id ? response.data : d
            )
          )
        } catch (error) {
          console.error(`Error polling status for document ${doc.id}:`, error)
        }
      }
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [documents, selectedCompany])

  // Load PDF when document is selected
  useEffect(() => {
    if (selectedDocument) {
      loadPdfDocument(selectedDocument.id)
    } else {
      // Revoke URL when document is deselected
      if (pdfUrlRef.current) {
        URL.revokeObjectURL(pdfUrlRef.current)
        pdfUrlRef.current = null
      }
      setPdfUrl(null)
    }

    // Cleanup: revoke object URL when component unmounts or document changes
    return () => {
      if (pdfUrlRef.current) {
        URL.revokeObjectURL(pdfUrlRef.current)
        pdfUrlRef.current = null
      }
    }
  }, [selectedDocument?.id]) // Only depend on document ID to avoid infinite loops

  // Track loading state to prevent duplicate calls
  const chunksLoadingRef = useRef(false)
  const chunksAbortControllerRef = useRef(null)

  // Load document chunks when document is selected and indexed (non-blocking)
  const loadDocumentChunks = useCallback(async (documentId) => {
    if (!documentId) {
      setDocumentChunks(null)
      return
    }

    // Only load chunks for indexed documents
    if (selectedDocument?.indexing_status !== 'indexed' && selectedDocument?.indexing_status !== 'INDEXED') {
      setDocumentChunks(null)
      return
    }

    // Prevent duplicate calls
    if (chunksLoadingRef.current) {
      return
    }

    // Cancel any previous request
    if (chunksAbortControllerRef.current) {
      chunksAbortControllerRef.current.abort()
    }

    chunksLoadingRef.current = true
    setChunksLoading(true)

    // Create new abort controller for this request
    const abortController = new AbortController()
    chunksAbortControllerRef.current = abortController

    // Use setTimeout to ensure this runs asynchronously and doesn't block
    // specifically wait for the UI and PDF viewer to settle before loading raw chunks
    setTimeout(async () => {
      try {
        const endpoint = isAuthenticated ? 'chunks' : 'chunks-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${documentId}/${endpoint}`,
          {
            headers,
            signal: abortController.signal,
            timeout: 30000 // 30 second timeout
          }
        )

        // Only update state if request wasn't aborted
        if (!abortController.signal.aborted) {
          setDocumentChunks(response.data)
        }
      } catch (error) {
        // Ignore abort errors
        if (error.name === 'AbortError' || error.name === 'CanceledError') {
          return
        }
        console.error('Error loading document chunks:', error)
        if (!abortController.signal.aborted) {
          setDocumentChunks(null)
        }
      } finally {
        if (!abortController.signal.aborted) {
          chunksLoadingRef.current = false
          setChunksLoading(false)
        }
      }
    }, 1000) // Run after 1s delay to avoid blocking initial render
  }, [isAuthenticated, token, selectedDocument?.indexing_status])

  useEffect(() => {
    if (selectedDocument) {
      // Reset state
      setExpandedChunks(new Set())
      // Load chunks asynchronously
      loadDocumentChunks(selectedDocument.id)
    } else {
      // Cancel any pending request
      if (chunksAbortControllerRef.current) {
        chunksAbortControllerRef.current.abort()
      }
      chunksLoadingRef.current = false
      setDocumentChunks(null)
      setExpandedChunks(new Set())
    }

    // Cleanup: cancel request on unmount or document change
    return () => {
      if (chunksAbortControllerRef.current) {
        chunksAbortControllerRef.current.abort()
      }
      chunksLoadingRef.current = false
    }
  }, [selectedDocument?.id, loadDocumentChunks])

  const toggleChunk = (chunkIndex) => {
    setExpandedChunks(prev => {
      const newSet = new Set(prev)
      if (newSet.has(chunkIndex)) {
        newSet.delete(chunkIndex)
      } else {
        newSet.add(chunkIndex)
      }
      return newSet
    })
  }

  const expandAllChunks = () => {
    setIsDocumentExpanded(true)
    if (documentChunks && documentChunks.chunks) {
      setExpandedChunks(new Set(documentChunks.chunks.map(chunk => chunk.chunk_index)))
    }
  }

  const collapseAllChunks = () => {
    setIsDocumentExpanded(false)
    setExpandedChunks(new Set())
  }

  const loadPdfDocument = async (documentId) => {
    try {
      // Revoke previous URL if exists
      if (pdfUrlRef.current) {
        URL.revokeObjectURL(pdfUrlRef.current)
        pdfUrlRef.current = null
      }

      // Use test endpoint if not authenticated (for development)
      const endpoint = isAuthenticated ? 'file' : 'file-test'
      const url = `${API_BASE_URL}/documents/${documentId}/${endpoint}`

      // Fetch PDF as blob to include authentication headers
      const response = await axios.get(url, {
        responseType: 'blob',
        headers: isAuthenticated && token ? {
          'Authorization': `Bearer ${token}`
        } : {}
      })

      // Create object URL from blob
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const objectUrl = URL.createObjectURL(blob)
      pdfUrlRef.current = objectUrl
      setPdfUrl(objectUrl)
    } catch (error) {
      console.error('Error loading PDF:', error)
      setPdfUrl(null)
      pdfUrlRef.current = null
    }
  }

  const loadCompanies = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/companies/`)
      setCompanies(response.data)
    } catch (error) {
      console.error('Error loading companies:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCompanyDocuments = async (companyId) => {
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(`${API_BASE_URL}/documents/?company_id=${companyId}`, { headers })
      setDocuments(response.data)
    } catch (error) {
      console.error('Error loading documents:', error)
    }
  }

  const filteredCompanies = companies.filter(company =>
    company.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (company.ticker && company.ticker.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const handleAddDocument = () => {
    setIsUploadModalOpen(true)
  }

  const handleUploadSuccess = async (response) => {
    // Set uploading state immediately to disable button
    setIsUploading(true)
    // After batch upload, immediately check upload progress to update the button
    await loadUploadProgress()
    // The upload progress will be tracked in the background
    // User can click "Check Uploads" button to see progress if needed
    setShowUploadProgress(false)
    loadCompanies() // Refresh companies list
    // Reset uploading state after progress is loaded (button will be disabled if hasActiveUploads is true)
    setIsUploading(false)
  }

  const handleReplaceAndIndex = async (documentId) => {
    try {
      const endpoint = isAuthenticated ? 'replace-and-index' : 'replace-and-index-test'
      await axios.post(`${API_BASE_URL}/documents/${documentId}/${endpoint}`, {}, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      // Refresh upload progress
      loadUploadProgress()
    } catch (error) {
      console.error('Error replacing document:', error)
    }
  }

  const handleCancelDuplicate = async (documentId) => {
    if (!window.confirm('Are you sure you want to cancel this upload? The document will be removed.')) {
      return
    }

    try {
      const endpoint = isAuthenticated ? '' : '/test'
      await axios.delete(`${API_BASE_URL}/documents/${documentId}${endpoint}`, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      // Refresh upload progress
      loadUploadProgress()
    } catch (error) {
      console.error('Error canceling document:', error)
      alert('Failed to cancel document. Please try again.')
    }
  }

  const getProgressPercentage = (status) => {
    switch (status?.toLowerCase()) {
      case 'uploading':
        return 33
      case 'classifying':
        return 66
      case 'classified':
        return 66  // Same as classifying since it's the final state for non-earnings announcements
      case 'indexing':
        return 90
      case 'indexed':
        return 100
      default:
        return 0
    }
  }

  const getMilestoneStatus = (status, milestone) => {
    const statusLower = status?.toLowerCase()
    if (milestone === 'uploading') {
      if (statusLower === 'uploading') return 'active'
      if (['classifying', 'classified', 'indexing', 'indexed'].includes(statusLower)) return 'completed'
      return 'pending'
    }
    if (milestone === 'classification') {
      if (statusLower === 'classifying') return 'active'
      if (['classified', 'indexing', 'indexed'].includes(statusLower)) return 'completed'
      if (statusLower === 'uploading') return 'pending'
      return 'pending'
    }
    if (milestone === 'indexing') {
      if (statusLower === 'indexing') return 'active'
      if (statusLower === 'indexed') return 'completed'
      // For 'classified' status, indexing milestone should be pending (not completed)
      if (statusLower === 'classified') return 'pending'
      return 'pending'
    }
    return 'pending'
  }

  const hasActiveUploads = uploadingDocuments.length > 0 || isUploading

  return (
    <div className="left-panel">
      {showUploadProgress && (
        <div className="panel-content">
          <div className="panel-header">
            <div className="breadcrumb">
              <button className="breadcrumb-link" onClick={() => {
                setShowUploadProgress(false)
                // Clear any selected company/document to ensure we're on companies list
                if (selectedCompany || selectedDocument) {
                  onBack()
                  if (selectedDocument && selectedCompany) {
                    setTimeout(() => onBack(), 100)
                  }
                }
              }}>Companies</button>
              <span className="breadcrumb-separator">›</span>
              <span className="breadcrumb-current">Upload Progress</span>
            </div>
          </div>
          {uploadingDocuments.length === 0 ? (
            <div className="empty-state">
              <p>All uploads have completed. Redirecting...</p>
            </div>
          ) : (
            <div className="upload-progress-list">
              {uploadingDocuments.map(document => (
                <div key={document.id} className="upload-progress-item">
                  <div className="upload-progress-header">
                    <div className="upload-progress-filename">{document.filename}</div>
                    {document.duplicate_detected && (
                      <div className="duplicate-warning-badge">⚠️ Duplicate</div>
                    )}
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar"
                      style={{ width: `${getProgressPercentage(document.indexing_status)}%` }}
                    />
                  </div>
                  <div className="milestones">
                    <div className={`milestone ${getMilestoneStatus(document.indexing_status, 'uploading')}`}>
                      <span className="milestone-icon">
                        {getMilestoneStatus(document.indexing_status, 'uploading') === 'completed' ? '✓' :
                          getMilestoneStatus(document.indexing_status, 'uploading') === 'active' ? <span className="status-spinner" aria-hidden="true" /> : '○'}
                      </span>
                      <span className="milestone-label">Uploading</span>
                    </div>
                    <div className={`milestone ${getMilestoneStatus(document.indexing_status, 'classification')}`}>
                      <span className="milestone-icon">
                        {getMilestoneStatus(document.indexing_status, 'classification') === 'completed' ? '✓' :
                          getMilestoneStatus(document.indexing_status, 'classification') === 'active' ? <span className="status-spinner" aria-hidden="true" /> : '○'}
                      </span>
                      <span className="milestone-label">Classification</span>
                    </div>
                    <div className={`milestone ${getMilestoneStatus(document.indexing_status, 'indexing')}`}>
                      <span className="milestone-icon">
                        {getMilestoneStatus(document.indexing_status, 'indexing') === 'completed' ? '✓' :
                          getMilestoneStatus(document.indexing_status, 'indexing') === 'active' ? <span className="status-spinner" aria-hidden="true" /> : '○'}
                      </span>
                      <span className="milestone-label">Indexing</span>
                    </div>
                  </div>
                  {document.duplicate_detected &&
                    (document.indexing_status?.toLowerCase() === 'classifying' ||
                      document.indexing_status === 'CLASSIFYING') && (
                      <div className="duplicate-action">
                        <div className="duplicate-warning-text">
                          <strong>⚠️ Duplicate Document Detected</strong>
                          <p>This document appears to be a duplicate. Click "Replace & Index" to replace the existing document and proceed with indexing, or "Cancel" to remove this upload.</p>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                          <button
                            className="button-warning"
                            onClick={() => handleReplaceAndIndex(document.id)}
                          >
                            Replace & Index
                          </button>
                          <button
                            className="button-secondary"
                            onClick={() => handleCancelDuplicate(document.id)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!showUploadProgress && !selectedCompany && !selectedDocument && (
        <div className="panel-content">
          <div className="panel-header">
            <span className="breadcrumb-current">Companies</span>
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <input
              type="text"
              placeholder="Search companies..."
              className="search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          {loading ? (
            <div className="loading">Loading companies...</div>
          ) : (
            <div className="company-list">
              {filteredCompanies.map(company => (
                <div
                  key={company.id}
                  className="company-item"
                  onClick={() => onCompanySelect(company)}
                >
                  <div className="company-info">
                    <div className="company-name">{company.name}</div>
                    {company.ticker && (
                      <div className="company-ticker">{company.ticker}</div>
                    )}
                  </div>
                  {company.document_count !== undefined && company.document_count > 0 && (
                    <span className="document-count-badge">{company.document_count}</span>
                  )}
                </div>
              ))}
              {filteredCompanies.length === 0 && (
                <div className="empty-state">No companies found</div>
              )}
            </div>
          )}
          <button
            className={`add-document-button ${hasActiveUploads ? 'has-uploads' : ''}`}
            onClick={hasActiveUploads ? () => setShowUploadProgress(true) : handleAddDocument}
          >
            {hasActiveUploads ? (
              <>
                <span className="button-spinner" aria-hidden="true" />
                Check Uploads ({uploadingDocuments.length})
              </>
            ) : (
              '+ Add Document'
            )}
          </button>
        </div>
      )}

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      {selectedCompany && !selectedDocument && (
        <div className="panel-content">
          <div className="panel-header">
            <div className="breadcrumb">
              <button className="breadcrumb-link" onClick={onBack}>Companies</button>
              <span className="breadcrumb-separator">›</span>
              <span className="breadcrumb-current">{selectedCompany.name}</span>
            </div>
          </div>
          <div className="document-list">
            {documents.map(document => (
              <div
                key={document.id}
                className="document-item"
                onClick={() => onDocumentSelect(document)}
              >
                <div className="document-name">
                  {document.document_type ? (
                    <span className="document-type-display">
                      {document.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  ) : (
                    <span className="document-type-display">Document</span>
                  )}
                  {document.time_period && (
                    <span className="document-time-period"> • {document.time_period}</span>
                  )}
                </div>
                <div className="document-meta">
                  <span className={`status-badge status-${document.indexing_status?.toLowerCase()}`}>
                    {document.indexing_status || 'pending'}
                  </span>
                  {document.balance_sheet_status && document.balance_sheet_status !== 'not_extracted' && (
                    <span
                      className={`status-badge status-${document.balance_sheet_status === 'valid' ? 'indexed' : 'classified'}`}
                      title={`Balance Sheet: ${document.balance_sheet_status}`}
                    >
                      BS
                    </span>
                  )}
                  {document.income_statement_status && document.income_statement_status !== 'not_extracted' && (
                    <span
                      className={`status-badge status-${document.income_statement_status === 'valid' ? 'indexed' : 'classified'}`}
                      title={`Income Statement: ${document.income_statement_status}`}
                    >
                      IS
                    </span>
                  )}
                  {document.uploader_name && (
                    <span className="document-uploader">
                      Uploaded by {document.uploader_name}
                    </span>
                  )}
                  {document.uploaded_at && (
                    <span className="document-date">
                      {new Date(document.uploaded_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {documents.length === 0 && (
              <div className="empty-state">No documents for this company</div>
            )}
          </div>
          <button
            className={`add-document-button ${hasActiveUploads ? 'has-uploads' : ''}`}
            onClick={hasActiveUploads ? () => setShowUploadProgress(true) : handleAddDocument}
          >
            {hasActiveUploads ? (
              <>
                <span className="button-spinner" aria-hidden="true" />
                Check Uploads ({uploadingDocuments.length})
              </>
            ) : (
              '+ Add Document'
            )}
          </button>
        </div>
      )}

      {selectedDocument && (
        <div className="panel-content">
          <div className="panel-header">
            <div className="breadcrumb">
              <button className="breadcrumb-link" onClick={() => {
                // Go back to companies list: need to clear both document and company
                // Call onBack twice to go back two levels (document -> company -> companies)
                onBack() // First call clears document
                // Use setTimeout to ensure React state update completes before second call
                setTimeout(() => {
                  onBack() // Second call clears company
                }, 0)
              }}>Companies</button>
              <span className="breadcrumb-separator">›</span>
              <button className="breadcrumb-link" onClick={onBack}>{selectedCompany?.name || 'Company'}</button>
              <span className="breadcrumb-separator">›</span>
              <span className="breadcrumb-current">{selectedDocument.document_type ? selectedDocument.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Document'}{selectedDocument.time_period ? ` • ${selectedDocument.time_period}` : ''}</span>
            </div>
          </div>
          <div className="document-detail">
            <div className="info-section">
              <h3>Status & Metadata</h3>
              <div className="metadata-grid">
                <div className="metadata-item">
                  <strong>Status:</strong>
                  <span className={`status-badge status-${selectedDocument.indexing_status?.toLowerCase() || 'pending'}`}>
                    {selectedDocument.indexing_status || 'pending'}
                  </span>
                </div>
                <div className="metadata-item">
                  <strong>Type:</strong> {selectedDocument.document_type?.replace(/_/g, ' ') || 'N/A'}
                </div>
                <div className="metadata-item">
                  <strong>Time Period:</strong> {selectedDocument.time_period || 'N/A'}
                </div>
                <div className="metadata-item">
                  <strong>Pages:</strong> {selectedDocument.page_count || 'N/A'}
                </div>
                <div className="metadata-item">
                  <strong>Characters:</strong> {selectedDocument.character_count?.toLocaleString() || 'N/A'}
                </div>
                {selectedDocument.uploader_name && (
                  <div className="metadata-item">
                    <strong>Uploaded by:</strong> {selectedDocument.uploader_name}
                  </div>
                )}
                {selectedDocument.uploaded_at && (
                  <div className="metadata-item">
                    <strong>Uploaded:</strong> {new Date(selectedDocument.uploaded_at).toLocaleString()}
                  </div>
                )}
              </div>
              {selectedDocument.summary && (
                <div className="summary-section">
                  <strong>Summary:</strong>
                  <p className="summary-text">{selectedDocument.summary}</p>
                </div>
              )}

              {/* Re-run Processing Buttons */}
              {(selectedDocument.indexing_status === 'indexed' || selectedDocument.indexing_status === 'indexing') && (
                <div className="summary-section" style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <strong>Re-run Processing</strong>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
                    <button
                      className="button-secondary"
                      disabled={isCheckingProcessingStatus || isProcessing || selectedDocument.indexing_status === 'indexing' || selectedDocument.analysis_status === 'processing' || buttonDebouncing['rerun-indexing']}
                      onClick={() => debounceAction('rerun-indexing', async () => {
                        setIsProcessing(true)
                        processingTriggeredRef.current = true
                        processingActionRef.current = 'rerun-indexing'
                        try {
                          const endpoint = isAuthenticated ? 'rerun-indexing' : 'rerun-indexing-test'
                          const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                          await axios.post(
                            `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                            {},
                            { headers }
                          )
                          // Refresh document status to update indexing_status
                          // Polling will continue to update the status automatically
                          if (onDocumentSelect && selectedDocument) {
                            const statusEndpoint = isAuthenticated ? 'status' : 'status-test'
                            const statusResponse = await axios.get(
                              `${API_BASE_URL}/documents/${selectedDocument.id}/${statusEndpoint}`,
                              { headers }
                            )
                            if (statusResponse.data) {
                              // Update the document with latest status (including indexing_status)
                              onDocumentSelect(statusResponse.data)
                            }
                          }
                          // Refresh documents list if we have a company
                          if (selectedCompany) {
                            loadCompanyDocuments(selectedCompany.id)
                          }
                          // Don't set isProcessing(false) here - let the polling effect handle it
                          // when indexing_status changes from 'indexing' to 'indexed'
                        } catch (err) {
                          alert(err.response?.data?.detail || 'Failed to re-run indexing')
                          setIsProcessing(false)
                        }
                      }, 2000)}
                      style={{ width: '100%', textAlign: 'left' }}
                    >
                      Re-run Indexing
                    </button>
                    {/* Always show Extraction button, but disable if not eligible document type */}
                    <button
                      className="button-secondary"
                      disabled={
                        isCheckingProcessingStatus ||
                        isProcessing ||
                        selectedDocument.analysis_status === 'processing' ||
                        !selectedDocument.document_type ||
                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type) ||
                        buttonDebouncing['rerun-extraction']
                      }
                      onClick={() => debounceAction('rerun-extraction', async () => {
                        setIsProcessing(true)
                        processingTriggeredRef.current = true
                        processingActionRef.current = 'rerun-extraction'
                        // Immediately set all milestones to PENDING in RightPanel
                        window.dispatchEvent(new CustomEvent('resetProgressToPending', {
                          detail: { documentId: selectedDocument.id }
                        }))
                        // Clear financial statements data in RightPanel
                        window.dispatchEvent(new CustomEvent('clearFinancialStatements'))
                        try {
                          const endpoint = isAuthenticated ? 'rerun-financial-statements' : 'rerun-financial-statements/test'
                          const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                          await axios.post(
                            `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                            {},
                            { headers }
                          )
                          // Don't reload immediately - RightPanel will reload after delay in resetProgressToPending handler
                          // This ensures server has time to reset all milestones
                        } catch (err) {
                          alert(err.response?.data?.detail || 'Failed to re-run extraction and classification')
                          setIsProcessing(false)
                        }
                      }, 2000)}
                      style={{ width: '100%', textAlign: 'left' }}
                    >
                      Re-run Extraction and Classification
                    </button>
                    {/* Always show Historical Calculations button, but disable if no financial statements */}
                    <button
                      className="button-secondary"
                      disabled={
                        isCheckingProcessingStatus ||
                        isProcessing ||
                        selectedDocument.analysis_status === 'processing' ||
                        !hasFinancialStatements ||
                        !selectedDocument.document_type ||
                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type) ||
                        buttonDebouncing['rerun-historical']
                      }
                      style={{ width: '100%', textAlign: 'left' }}
                      onClick={() => debounceAction('rerun-historical', async () => {
                        if (!hasFinancialStatements) return
                        setIsProcessing(true)
                        processingTriggeredRef.current = true
                        processingActionRef.current = 'rerun-historical'
                        try {
                          const endpoint = isAuthenticated ? 'historical-calculations/recalculate' : 'historical-calculations/recalculate/test'
                          const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                          await axios.post(
                            `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                            {},
                            { headers }
                          )
                          // Trigger reload of historical calculations in RightPanel
                          window.dispatchEvent(new CustomEvent('reloadHistoricalCalculations'))
                        } catch (err) {
                          alert(err.response?.data?.detail || 'Failed to recalculate historical calculations')
                        } finally {
                          setIsProcessing(false)
                          processingTriggeredRef.current = false
                        }
                      }, 2000)}
                    >
                      Re-run Historical Calculations
                    </button>
                  </div>
                </div>
              )}

              {/* Danger Zone */}
              <div className="summary-section" style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                <strong>Danger Zone</strong>
                <button
                  className="button-warning"
                  disabled={!hasFinancialStatements || isCheckingProcessingStatus || isProcessing || selectedDocument.analysis_status === 'processing' || buttonDebouncing['delete-statements']}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    marginTop: '0.75rem'
                  }}
                  onClick={() => debounceAction('delete-statements', async () => {
                    if (!hasFinancialStatements) return
                    if (!window.confirm('Are you sure you want to delete all financial statements for this document? This action cannot be undone.')) {
                      return
                    }
                    setIsProcessing(true)
                    processingActionRef.current = 'delete-statements'
                    try {
                      const endpoint = isAuthenticated ? 'financial-statements' : 'financial-statements/test'
                      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                      await axios.delete(
                        `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                        { headers }
                      )
                      // Clear financial statements data in RightPanel
                      window.dispatchEvent(new CustomEvent('clearFinancialStatements'))
                      // Update state to reflect that financial statements no longer exist
                      setHasFinancialStatements(false)
                      // Refresh document status and trigger RightPanel refresh
                      if (onDocumentSelect && selectedDocument) {
                        // Fetch latest status
                        const statusEndpoint = isAuthenticated ? 'status' : 'status-test'
                        const statusResponse = await axios.get(
                          `${API_BASE_URL}/documents/${selectedDocument.id}/${statusEndpoint}`,
                          { headers }
                        )
                        if (statusResponse.data) {
                          onDocumentSelect(statusResponse.data)
                        }
                      }
                    } catch (err) {
                      alert(err.response?.data?.detail || 'Failed to delete financial statements')
                    } finally {
                      setIsProcessing(false)
                    }
                  }, 2000)}
                >
                  Delete Financial Statements
                </button>
                <button
                  className="button-warning"
                  disabled={isCheckingProcessingStatus || isProcessing || selectedDocument.indexing_status === 'indexing' || selectedDocument.analysis_status === 'processing' || buttonDebouncing['delete-document']}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    marginTop: '0.75rem',
                    backgroundColor: 'var(--error, #E5484D)',
                    color: 'white'
                  }}
                  onClick={() => debounceAction('delete-document', async () => {
                    if (window.confirm(`Are you sure you want to permanently delete "${selectedDocument.filename}"? This will delete the document, all financial statements, and all associated data. This action cannot be undone.`)) {
                      setIsProcessing(true)
                      processingActionRef.current = 'delete-document'
                      try {
                        const endpoint = isAuthenticated ? 'permanent' : 'permanent/test'
                        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                        await axios.delete(
                          `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                          { headers }
                        )
                        // Navigate back to company document list (one level up)
                        if (onBack) {
                          onBack()
                        }
                        // Refresh the company documents list if we have a company
                        if (selectedCompany) {
                          // Small delay to ensure navigation happens first
                          setTimeout(() => {
                            loadCompanyDocuments(selectedCompany.id)
                          }, 100)
                        }
                      } catch (err) {
                        alert(err.response?.data?.detail || 'Failed to delete document')
                        setIsProcessing(false)
                      }
                    }
                  }, 2000)}
                >
                  Delete Document
                </button>
              </div>
            </div>
            {/* Unified Document Viewer Section */}
            {(pdfUrl || selectedDocument?.indexing_status === 'indexed' || selectedDocument?.indexing_status === 'INDEXED') && (
              <div className="info-section raw-document-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ marginBottom: 0 }}>Document</h3>
                  {documentChunks && documentChunks.chunks && documentChunks.chunks.length > 0 && (
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        className="button-secondary"
                        onClick={expandAllChunks}
                        style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                      >
                        Expand All
                      </button>
                      <button
                        className="button-secondary"
                        onClick={collapseAllChunks}
                        style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                      >
                        Collapse All
                      </button>
                    </div>
                  )}
                </div>

                {/* Original PDF Viewer */}
                {pdfUrl ? (
                  <div className="chunk-item">
                    <button
                      className="chunk-header"
                      onClick={() => setIsDocumentExpanded(!isDocumentExpanded)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.75rem',
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        marginBottom: '0.5rem'
                      }}
                    >
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        Original PDF {selectedDocument.page_count ? `(Pages 1-${selectedDocument.page_count})` : ''}
                      </span>
                      {selectedDocument.character_count ? (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {selectedDocument.character_count.toLocaleString()} chars
                        </span>
                      ) : (
                        <span></span>
                      )}
                      <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                        {isDocumentExpanded ? '▼' : '▶'}
                      </span>
                    </button>
                    {isDocumentExpanded && (
                      <div className="chunk-content" style={{ padding: '0', border: 'none', background: 'transparent' }}>
                        <div className="pdf-viewer-container" style={{ height: '500px', marginTop: '0.5rem' }}>
                          <iframe
                            src={pdfUrl}
                            title={selectedDocument.filename}
                            className="pdf-viewer"
                            style={{ height: '100%', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                    Loading document PDF...
                  </p>
                )}

                {/* Chunks List */}
                {(selectedDocument?.indexing_status === 'indexed' || selectedDocument?.indexing_status === 'INDEXED') && (
                  <>
                    {chunksLoading ? (
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading chunks...</p>
                    ) : documentChunks && documentChunks.chunks ? (
                      <div className="chunks-container">
                        {documentChunks.chunks.map((chunk) => {
                          const isExpanded = expandedChunks.has(chunk.chunk_index)
                          return (
                            <div key={chunk.chunk_index} className="chunk-item">
                              <button
                                className="chunk-header"
                                onClick={() => toggleChunk(chunk.chunk_index)}
                                style={{
                                  width: '100%',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  padding: '0.75rem',
                                  background: 'var(--bg-elevated)',
                                  border: '1px solid var(--border)',
                                  borderRadius: 'var(--radius-md)',
                                  cursor: 'pointer',
                                  textAlign: 'left',
                                  marginBottom: '0.5rem'
                                }}
                              >
                                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                  Chunk {chunk.chunk_index} (Pages {chunk.start_page}-{chunk.end_page})
                                </span>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                  {chunk.character_count.toLocaleString()} chars
                                </span>
                                <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                                  {isExpanded ? '▼' : '▶'}
                                </span>
                              </button>
                              {isExpanded && (
                                <div
                                  className="chunk-content"
                                  style={{
                                    padding: '1rem',
                                    background: 'var(--bg-surface)',
                                    border: '1px solid var(--border)',
                                    borderRadius: 'var(--radius-md)',
                                    marginBottom: '0.5rem',
                                    maxHeight: '400px',
                                    overflowY: 'auto',
                                    fontSize: '0.875rem',
                                    lineHeight: '1.6',
                                    color: 'var(--text-primary)',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                    contentVisibility: 'auto',
                                    containIntrinsicSize: 'auto 400px'
                                  }}
                                >
                                  {chunk.error ? (
                                    <p style={{ color: 'var(--error)' }}>Error loading chunk: {chunk.error}</p>
                                  ) : chunk.text ? (
                                    chunk.text
                                  ) : (
                                    <p style={{ color: 'var(--text-secondary)' }}>No text available</p>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        No chunks available. Document may not be fully indexed.
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default LeftPanel
