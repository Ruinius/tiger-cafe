import React, { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { usePdfViewer } from '../../../hooks/usePdfViewer'
import { useDocumentData } from '../../../hooks/useDocumentData'
import { API_BASE_URL } from '../../../config'
import { formatDate } from '../../../utils/formatting'
import './Document.css'

function DocumentView({ selectedDocument, selectedCompany, onBack, onShowUpdates }) {
    const { isAuthenticated, token } = useAuth()
    const [pdfUrl, setPdfUrl] = useState(null)
    const pdfUrlRef = useRef(null)

    // Use custom hook for chunk management
    const {
        documentChunks,
        chunksLoading,
        expandedChunks,
        isDocumentExpanded,
        toggleChunk,
        expandAllChunks,
        collapseAllChunks,
        toggleDocumentExpanded
    } = usePdfViewer(selectedDocument)

    // Use document data hook for actions
    const {
        isProcessing,
        isCheckingProcessingStatus,
        hasFinancialStatements,
        performAction,
        currentDocument // Use this for up-to-date status
    } = useDocumentData(null, selectedDocument)
    // We pass null for companyId as we focus on document here.
    // selectedDocument is passed to init status checks.

    // Use currentDocument for status checks to reflect polling updates
    const doc = currentDocument || selectedDocument

    // Debouncing state to prevent duplicate button clicks
    const [buttonDebouncing, setButtonDebouncing] = useState({})
    const debounceTimers = useRef({})

    const debounceAction = useCallback((actionKey, action, delay = 1000) => {
        if (buttonDebouncing[actionKey]) return
        setButtonDebouncing(prev => ({ ...prev, [actionKey]: true }))
        action()
        if (debounceTimers.current[actionKey]) clearTimeout(debounceTimers.current[actionKey])
        debounceTimers.current[actionKey] = setTimeout(() => {
            setButtonDebouncing(prev => {
                const newState = { ...prev }
                delete newState[actionKey]
                return newState
            })
            delete debounceTimers.current[actionKey]
        }, delay)
    }, [buttonDebouncing])

    // Load PDF Blob
    React.useEffect(() => {
        const loadPdfDocument = async (docId) => {
            try {
                if (pdfUrlRef.current) {
                    URL.revokeObjectURL(pdfUrlRef.current)
                    pdfUrlRef.current = null
                }
                const endpoint = isAuthenticated ? 'file' : 'file-test'
                const url = `${API_BASE_URL}/documents/${docId}/${endpoint}`
                const response = await axios.get(url, {
                    responseType: 'blob',
                    headers: isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                })
                const blob = new Blob([response.data], { type: 'application/pdf' })
                const objectUrl = URL.createObjectURL(blob)
                pdfUrlRef.current = objectUrl
                setPdfUrl(objectUrl)
            } catch (error) {
                console.error('Error loading PDF:', error)
                setPdfUrl(null)
            }
        }

        if (doc?.id) {
            loadPdfDocument(doc.id)
        } else {
            setPdfUrl(null)
        }
        return () => {
            if (pdfUrlRef.current) {
                URL.revokeObjectURL(pdfUrlRef.current)
                pdfUrlRef.current = null
            }
        }
    }, [doc?.id, isAuthenticated, token])

    if (!doc) return null

    const documentName = doc.document_type
        ? doc.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
        : 'Document'



    return (
        <div className="panel-content">
            <div className="panel-header">
                <div className="breadcrumb">
                    <button className="breadcrumb-link" onClick={() => {
                        // Need to go back to companies list (2 levels up)
                        // But onBack prop provided by Dashboard transitions to COMPANY view.
                        // To go to Companies, user must click "Companies" which might not be directly available here
                        // unless we pass a specific handler or check history.
                        // But wait, the Breadcrumb says: Companies > Company Name > Document
                        // If we click Companies, we need to reset view to GLOBAL.
                        // If we click Company Name, we reset view to COMPANY.
                        // PdfViewer receives onBack which switches to COMPANY view.
                        // We might need another prop onGoHome if we want full breadcrumb?
                        // For now, let's implement the immediate parent back.
                        // Actually, I can render the full breadcrumb if I have the callbacks.
                        // But Dashboard orchestration only provides simple state transitions.
                        // Let's stick to the plan: Breadcrumb: < [Company Name]
                        // Wait, the plan says:
                        // Document View: Left Panel: PdfViewer. Breadcrumb: < [Company Name].
                        // So it should just link back to the Company View.
                        onBack()
                    }}>Companies</button>
                    <span className="breadcrumb-separator">›</span>
                    <button className="breadcrumb-link" onClick={onBack}>
                        {selectedCompany?.name || 'Company'}
                    </button>
                    <span className="breadcrumb-separator">›</span>
                    <span className="breadcrumb-current">
                        {documentName}{doc.period_end_date ? ` • ${formatDate(doc.period_end_date)}` : (doc.time_period ? ` • ${doc.time_period}` : '')}
                    </span>
                </div>
            </div>

            <div className="pdf-viewer-container">
                {/* Metadata Section */}
                <div className="info-section">
                    <h3 style={{ marginTop: 0 }}>Status & Metadata</h3>
                    <div className="metadata-grid">
                        <div className="metadata-item">
                            <strong>Status:</strong>
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                <span className={`status-badge status-${doc.indexing_status?.toLowerCase() || 'pending'}`}>
                                    {doc.indexing_status || 'pending'}
                                </span>
                                {doc.balance_sheet_status && doc.balance_sheet_status !== 'not_extracted' && (
                                    <span
                                        className={`status-badge status-${doc.balance_sheet_status === 'valid' ? 'indexed' : 'classified'}`}
                                        title={`Balance Sheet: ${doc.balance_sheet_status}`}
                                    >
                                        BS
                                    </span>
                                )}
                                {doc.income_statement_status && doc.income_statement_status !== 'not_extracted' && (
                                    <span
                                        className={`status-badge status-${doc.income_statement_status === 'valid' ? 'indexed' : 'classified'}`}
                                        title={`Income Statement: ${doc.income_statement_status}`}
                                    >
                                        IS
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="metadata-item">
                            <strong>Type:</strong> {doc.document_type?.replace(/_/g, ' ') || 'N/A'}
                        </div>
                        <div className="metadata-item">
                            <strong>Time Period:</strong> {doc.time_period || 'N/A'}
                        </div>
                        <div className="metadata-item">
                            <strong>Period Ending:</strong> {formatDate(doc.period_end_date) || 'N/A'}
                        </div>
                        <div className="metadata-item">
                            <strong>Pages:</strong> {doc.page_count || 'N/A'}
                        </div>
                        <div className="metadata-item">
                            <strong>Characters:</strong> {doc.character_count?.toLocaleString() || 'N/A'}
                        </div>
                        {doc.uploader_name && (
                            <div className="metadata-item">
                                <strong>Uploaded by:</strong> {doc.uploader_name}
                            </div>
                        )}
                        {doc.uploaded_at && (
                            <div className="metadata-item">
                                <strong>Uploaded:</strong> {formatDate(doc.uploaded_at, true)}
                            </div>
                        )}
                    </div>
                    {doc.summary && (
                        <div className="summary-section">
                            <strong>Summary:</strong>
                            <p className="summary-text">{doc.summary}</p>
                        </div>
                    )}

                    {/* Re-run Processing Buttons */}
                    {(doc.indexing_status === 'indexed' || doc.indexing_status === 'indexing') && (
                        <div className="summary-section" style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                            <strong>Re-run Processing</strong>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
                                <button
                                    className="button-secondary"
                                    disabled={
                                        isCheckingProcessingStatus ||
                                        isProcessing ||
                                        doc.analysis_status === 'processing' ||
                                        !doc.document_type ||
                                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(doc.document_type) ||
                                        buttonDebouncing['rerun-extraction']
                                    }
                                    onClick={() => debounceAction('rerun-extraction', () => {
                                        performAction('rerun-extraction', doc.id)
                                            .then(() => { if (onShowUpdates) onShowUpdates() })
                                            .catch(e => console.error(e))
                                    })}
                                    style={{ width: '100%', textAlign: 'left' }}
                                >
                                    Re-run Extraction and Classification
                                </button>
                                <button
                                    className="button-secondary"
                                    disabled={
                                        isCheckingProcessingStatus ||
                                        isProcessing ||
                                        doc.analysis_status === 'processing' ||
                                        !hasFinancialStatements ||
                                        !doc.document_type ||
                                        !['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(doc.document_type) ||
                                        buttonDebouncing['rerun-historical']
                                    }
                                    style={{ width: '100%', textAlign: 'left' }}
                                    onClick={() => debounceAction('rerun-historical', () => performAction('rerun-historical', doc.id))}
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
                            disabled={!hasFinancialStatements || isCheckingProcessingStatus || isProcessing || doc.analysis_status === 'processing' || buttonDebouncing['delete-statements']}
                            style={{ width: '100%', textAlign: 'left', marginTop: '0.75rem' }}
                            onClick={() => debounceAction('delete-statements', () => {
                                if (window.confirm('Are you sure you want to delete all financial statements for this document?')) {
                                    performAction('delete-statements', doc.id)
                                }
                            })}
                        >
                            Delete Financial Statements
                        </button>
                        <button
                            className="button-warning"
                            disabled={buttonDebouncing['delete-document']}
                            style={{ width: '100%', textAlign: 'left', marginTop: '0.75rem', backgroundColor: 'var(--error, #E5484D)', color: 'white' }}
                            onClick={() => debounceAction('delete-document', () => {
                                if (window.confirm('Are you sure you want to permanently delete this document?')) {
                                    performAction('delete-document', doc.id).then(() => {
                                        if (onBack) onBack() // Navigate back
                                    })
                                }
                            })}
                        >
                            Delete Document
                        </button>
                    </div>
                </div>

                {/* Unified Document Viewer Section */}
                <div className="info-section raw-document-section">
                    <div style={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', width: '100%' }}>
                        <h3 style={{ margin: 0 }}>Document</h3>
                        {documentChunks && documentChunks.chunks && documentChunks.chunks.length > 0 && (
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                <button className="button-secondary" onClick={expandAllChunks} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>Expand All</button>
                                <button className="button-secondary" onClick={collapseAllChunks} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>Collapse All</button>
                            </div>
                        )}
                    </div>

                    <div style={{
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-md)',
                        overflow: 'hidden',
                        marginBottom: '0.75rem'
                    }}>
                        <button
                            className="chunk-header"
                            onClick={toggleDocumentExpanded}
                            style={{
                                width: '100%',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '0.75rem',
                                background: 'var(--bg-elevated)',
                                border: 'none',
                                borderBottom: isDocumentExpanded ? '1px solid var(--border)' : 'none',
                                cursor: 'pointer',
                                textAlign: 'left'
                            }}
                        >
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                Original PDF {doc.page_count ? `(Pages 1-${doc.page_count})` : ''}
                            </span>
                            {doc.character_count ? (
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    {doc.character_count.toLocaleString()} chars
                                </span>
                            ) : (<span></span>)}
                            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                                {isDocumentExpanded ? '▼' : '▶'}
                            </span>
                        </button>
                        {isDocumentExpanded && pdfUrl && (
                            <div className="pdf-frame-container" style={{
                                height: '600px',
                                width: '100%',
                                background: 'var(--bg-elevated)',
                                overflow: 'hidden'
                            }}>
                                <iframe src={pdfUrl} title="Document PDF" className="pdf-viewer" style={{ width: '100%', height: '100%', border: 'none' }} />
                            </div>
                        )}
                    </div>

                    {/* Chunks List */}
                    {(doc.indexing_status === 'indexed' || doc.indexing_status === 'INDEXED') && (
                        <>
                            {chunksLoading ? (
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading chunks...</p>
                            ) : documentChunks && documentChunks.chunks ? (
                                <div className="chunks-container">
                                    {documentChunks.chunks.map((chunk) => {
                                        const isExpanded = expandedChunks.has(chunk.chunk_index)
                                        return (
                                            <div key={chunk.chunk_index} className="chunk-item" style={{
                                                border: '1px solid var(--border)',
                                                borderRadius: 'var(--radius-md)',
                                                overflow: 'hidden',
                                                marginBottom: '0.75rem'
                                            }}>
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
                                                        border: 'none',
                                                        borderBottom: isExpanded ? '1px solid var(--border)' : 'none',
                                                        cursor: 'pointer',
                                                        textAlign: 'left'
                                                    }}
                                                >
                                                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                                        Chunk {chunk.chunk_index} ({chunk.start_char !== undefined ? `Chars ${chunk.start_char}-${chunk.end_char}` : `Pages ${chunk.start_page}-${chunk.end_page}`})
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
                                                            maxHeight: '400px',
                                                            overflowY: 'auto',
                                                            fontSize: '0.875rem',
                                                            lineHeight: '1.6',
                                                            color: 'var(--text-primary)',
                                                            whiteSpace: 'pre-wrap',
                                                            wordBreak: 'break-word',
                                                            width: '100%'
                                                        }}
                                                    >
                                                        {chunk.error ? (
                                                            <p style={{ color: 'var(--error)' }}>Error: {chunk.error}</p>
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
                                    No chunks available.
                                </p>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}

export default DocumentView
