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
  const [pdfUrl, setPdfUrl] = useState(null)
  const pdfUrlRef = useRef(null)
  const progressIntervalRef = useRef(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isCheckingProcessingStatus, setIsCheckingProcessingStatus] = useState(true) // Default to true to disable buttons until status is checked
  const [hasFinancialStatements, setHasFinancialStatements] = useState(false)
  const { isAuthenticated, token } = useAuth()

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
    if (!selectedDocument) {
      setIsProcessing(false)
      setIsCheckingProcessingStatus(false) // No document, so no need to check
      setHasFinancialStatements(false)
      return
    }
    
    // Set checking state to true to disable buttons while we fetch status
    setIsCheckingProcessingStatus(true)
    setHasFinancialStatements(false) // Reset until we check
    
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
        if (response.data && onDocumentSelect) {
          onDocumentSelect(response.data)
        }
        // After fetching status, we can enable buttons (they'll still be disabled if processing)
        setIsCheckingProcessingStatus(false)
        
        // Check if financial statements exist (only for eligible document types)
        const eligibleTypes = ['earnings_announcement', 'quarterly_filing', 'annual_filing']
        if (selectedDocument.document_type && eligibleTypes.includes(selectedDocument.document_type)) {
          await checkFinancialStatements(selectedDocument.id)
        }
      } catch (error) {
        console.error('Error fetching latest document status:', error)
        // Even on error, stop checking so buttons can be enabled (they'll check analysis_status)
        setIsCheckingProcessingStatus(false)
        setHasFinancialStatements(false)
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

    // Poll every 3 seconds while indexing (reduced frequency to avoid jarring updates)
    const pollInterval = setInterval(async () => {
      try {
        const endpoint = isAuthenticated ? 'status' : 'status-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
          { headers }
        )
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
        console.error(`Error polling status for document ${selectedDocument.id}:`, error)
      }
    }, 3000) // Increased from 2000ms to 3000ms

    return () => clearInterval(pollInterval)
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
    const hasActiveUploads = uploadingDocuments.length > 0
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
    // After batch upload, immediately check upload progress to update the button
    await loadUploadProgress()
    // The upload progress will be tracked in the background
    // User can click "Check Uploads" button to see progress if needed
    setShowUploadProgress(false)
    loadCompanies() // Refresh companies list
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
      if (['classifying', 'indexing', 'indexed'].includes(statusLower)) return 'completed'
      return 'pending'
    }
    if (milestone === 'classification') {
      if (statusLower === 'classifying') return 'active'
      if (['indexing', 'indexed'].includes(statusLower)) return 'completed'
      if (statusLower === 'uploading') return 'pending'
      return 'pending'
    }
    if (milestone === 'indexing') {
      if (statusLower === 'indexing') return 'active'
      if (statusLower === 'indexed') return 'completed'
      return 'pending'
    }
    return 'pending'
  }

  const hasActiveUploads = uploadingDocuments.length > 0

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
                      disabled={isCheckingProcessingStatus || selectedDocument.indexing_status === 'indexing'}
                      onClick={async () => {
                        setIsProcessing(true)
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
                      }}
                      style={{ width: '100%', textAlign: 'left', opacity: (isCheckingProcessingStatus || selectedDocument.indexing_status === 'indexing') ? 0.6 : 1, cursor: (isCheckingProcessingStatus || selectedDocument.indexing_status === 'indexing') ? 'not-allowed' : 'pointer' }}
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
                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)
                      }
                      onClick={async () => {
                        setIsProcessing(true)
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
                      }}
                      style={{ 
                        width: '100%', 
                        textAlign: 'left', 
                        opacity: (isCheckingProcessingStatus || isProcessing || selectedDocument.analysis_status === 'processing' || !selectedDocument.document_type || !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)) ? 0.6 : 1, 
                        cursor: (isCheckingProcessingStatus || isProcessing || selectedDocument.analysis_status === 'processing' || !selectedDocument.document_type || !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)) ? 'not-allowed' : 'pointer' 
                      }}
                    >
                      Re-run Extraction and Classification
                    </button>
                    {/* Always show Historical Calculations button, but disable if no financial statements */}
                    <button 
                      className="button-secondary"
                      disabled={
                        isCheckingProcessingStatus || 
                        isProcessing || 
                        !hasFinancialStatements ||
                        !selectedDocument.document_type ||
                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)
                      }
                      style={{ 
                        width: '100%', 
                        textAlign: 'left',
                        opacity: (isCheckingProcessingStatus || isProcessing || !hasFinancialStatements || !selectedDocument.document_type || !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)) ? 0.6 : 1,
                        cursor: (isCheckingProcessingStatus || isProcessing || !hasFinancialStatements || !selectedDocument.document_type || !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)) ? 'not-allowed' : 'pointer'
                      }}
                      onClick={async () => {
                        if (!hasFinancialStatements) return
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
                        }
                      }}
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
                  className="button-secondary"
                  disabled={!hasFinancialStatements}
                  style={{ 
                    width: '100%', 
                    textAlign: 'left', 
                    marginTop: '0.75rem', 
                    backgroundColor: hasFinancialStatements ? 'var(--error-color, #dc3545)' : 'var(--bg-secondary)', 
                    color: hasFinancialStatements ? 'white' : 'var(--text-secondary)', 
                    border: 'none',
                    opacity: hasFinancialStatements ? 1 : 0.6,
                    cursor: hasFinancialStatements ? 'pointer' : 'not-allowed'
                  }}
                  onClick={async () => {
                    if (!hasFinancialStatements) return
                    if (!window.confirm('Are you sure you want to delete all financial statements for this document? This action cannot be undone.')) {
                      return
                    }
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
                    }
                  }}
                >
                  Delete Financial Statements
                </button>
                <button 
                  className="button-secondary"
                  style={{ 
                    width: '100%', 
                    textAlign: 'left', 
                    marginTop: '0.75rem', 
                    backgroundColor: 'var(--error-color, #dc3545)', 
                    color: 'white', 
                    border: 'none'
                  }}
                  onClick={async () => {
                    if (!window.confirm(`Are you sure you want to permanently delete "${selectedDocument.filename}"? This will delete the document, all financial statements, and all associated data. This action cannot be undone.`)) {
                      return
                    }
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
                    }
                  }}
                >
                  Delete Document
                </button>
              </div>
            </div>
            {pdfUrl && (
              <div className="info-section document-viewer-section">
                <h3>Document</h3>
                <div className="pdf-viewer-container">
                  <iframe
                    src={pdfUrl}
                    title={selectedDocument.filename}
                    className="pdf-viewer"
                  />
                </div>
              </div>
            )}
            {!pdfUrl && (
              <div className="info-section">
                <p>Loading document...</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default LeftPanel
