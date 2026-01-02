import React, { useState, useEffect, useRef } from 'react'
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
  const { isAuthenticated, token } = useAuth()

  useEffect(() => {
    loadCompanies()
    // Start polling for upload progress
    const progressInterval = setInterval(() => {
      loadUploadProgress()
    }, 2000) // Poll every 2 seconds
    
    return () => clearInterval(progressInterval)
  }, [])

  const loadUploadProgress = async () => {
    try {
      const endpoint = isAuthenticated ? 'upload-progress' : 'upload-progress-test'
      const response = await axios.get(`${API_BASE_URL}/documents/${endpoint}`, {
        headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      setUploadingDocuments(response.data)
      
      // If no active uploads and we're showing progress, automatically go back to companies list
      if (response.data.length === 0 && showUploadProgress) {
        setShowUploadProgress(false)
        // Clear any selected company/document to ensure we're on companies list
        if (selectedCompany || selectedDocument) {
          onBack()
        }
        loadCompanies() // Refresh companies list
      }
    } catch (error) {
      console.error('Error loading upload progress:', error)
    }
  }

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
      const response = await axios.get(`${API_BASE_URL}/documents/?company_id=${companyId}`)
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

  const handleUploadSuccess = (response) => {
    // After batch upload, go back to companies list
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
      {showUploadProgress && hasActiveUploads && (
        <div className="panel-content">
          <div className="panel-header">
            <button className="back-button" onClick={() => setShowUploadProgress(false)}>← Back</button>
            <h2>Upload Progress</h2>
          </div>
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
                       getMilestoneStatus(document.indexing_status, 'uploading') === 'active' ? '⟳' : '○'}
                    </span>
                    <span className="milestone-label">Uploading</span>
                  </div>
                  <div className={`milestone ${getMilestoneStatus(document.indexing_status, 'classification')}`}>
                    <span className="milestone-icon">
                      {getMilestoneStatus(document.indexing_status, 'classification') === 'completed' ? '✓' : 
                       getMilestoneStatus(document.indexing_status, 'classification') === 'active' ? '⟳' : '○'}
                    </span>
                    <span className="milestone-label">Classification</span>
                  </div>
                  <div className={`milestone ${getMilestoneStatus(document.indexing_status, 'indexing')}`}>
                    <span className="milestone-icon">
                      {getMilestoneStatus(document.indexing_status, 'indexing') === 'completed' ? '✓' : 
                       getMilestoneStatus(document.indexing_status, 'indexing') === 'active' ? '⟳' : '○'}
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
                      <p>This document appears to be a duplicate. Click "Replace & Index" to replace the existing document and proceed with indexing.</p>
                    </div>
                    <button 
                      className="button-warning"
                      onClick={() => handleReplaceAndIndex(document.id)}
                    >
                      Replace & Index
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!showUploadProgress && !selectedCompany && !selectedDocument && (
        <div className="panel-content">
          <div className="panel-header">
            <h2>Companies</h2>
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
                <span className="spinner">⟳</span>
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
                <span className="spinner">⟳</span>
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
              <button className="breadcrumb-link" onClick={() => { onBack(); if (selectedCompany) onBack(); }}>Companies</button>
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

