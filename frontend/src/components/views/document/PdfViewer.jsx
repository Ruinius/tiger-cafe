import React, { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { usePdfViewer } from '../../../hooks/usePdfViewer'
import { useDocumentData } from '../../../hooks/useDocumentData'
import { API_BASE_URL } from '../../../config'

function PdfViewer({ selectedDocument, onBack }) {
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

    return (
        <div className="pdf-viewer-container">
            {/* Metadata Section */}
            <div className="info-section">
                <h3>Status & Metadata</h3>
                <div className="metadata-grid">
                    <div className="metadata-item">
                        <strong>Status:</strong>
                        <span className={`status-badge status-${doc.indexing_status?.toLowerCase() || 'pending'}`}>
                            {doc.indexing_status || 'pending'}
                        </span>
                    </div>
                    <div className="metadata-item">
                        <strong>Type:</strong> {doc.document_type?.replace(/_/g, ' ') || 'N/A'}
                    </div>
                    <div className="metadata-item">
                        <strong>Time Period:</strong> {doc.time_period || 'N/A'}
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
                            <strong>Uploaded:</strong> {new Date(doc.uploaded_at).toLocaleString()}
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
                                disabled={isCheckingProcessingStatus || isProcessing || doc.indexing_status === 'indexing' || doc.analysis_status === 'processing' || buttonDebouncing['rerun-indexing']}
                                onClick={() => debounceAction('rerun-indexing', () => performAction('rerun-indexing', doc.id))}
                                style={{ width: '100%', textAlign: 'left' }}
                            >
                                Re-run Indexing
                            </button>
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
                                onClick={() => debounceAction('rerun-extraction', () => performAction('rerun-extraction', doc.id))}
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
                        disabled={isCheckingProcessingStatus || isProcessing || doc.indexing_status === 'indexing' || doc.analysis_status === 'processing' || buttonDebouncing['delete-document']}
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

                {/* Original PDF Viewer */}
                <div className="chunk-item">
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
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius-md)',
                            cursor: 'pointer',
                            textAlign: 'left',
                            marginBottom: '0.5rem'
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
                        <div className="chunk-content" style={{ padding: '0', border: 'none', background: 'transparent' }}>
                            <iframe src={pdfUrl} title="Document PDF" className="pdf-viewer" style={{ width: '100%', height: '500px', border: 'none' }} />
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
                                                        wordBreak: 'break-word'
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
    )
}

export default PdfViewer
