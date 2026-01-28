import React, { useEffect } from 'react'
import { useDocumentData } from '../../../hooks/useDocumentData'

function DocumentList({ selectedCompany, onDocumentSelect, onBack, onOpenUploadModal, onShowUploadProgress }) {
    const {
        documents,
        loading,
        loadCompanyDocuments
    } = useDocumentData(selectedCompany)

    // TODO: Re-enable filtering once all documents have proper status values
    // Filter to only show completed documents (PROCESSED or ERROR)
    // Exclude documents that are still in progress
    const completedDocuments = documents.filter(doc => {
        // Check unified status first (new source of truth)
        if (doc.status) {
            const status = doc.status.toLowerCase()
            const allowedStates = [
                'processing_complete',
                'classified',
                'extraction_failed',
                'indexing_failed',
                'completed',
                'error',
                'pending',
                'processing',
                'classifying',
                'extracting',
                'indexing',
                'uploading'
            ]
            if (allowedStates.includes(status)) return true
        }

        // Fallback to legacy fields for older documents
        const indexingStatus = doc.indexing_status?.toLowerCase()
        const analysisStatus = doc.analysis_status?.toLowerCase()

        // Include everything for now to avoid disappearing documents during re-runs
        return true
    })

    const formatDocumentType = (type) => {
        if (!type) return 'Document'
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    }

    return (
        <div className="panel-content">
            <div className="panel-header">
                <div className="breadcrumb">
                    <button className="breadcrumb-link" onClick={onBack}>Companies</button>
                    <span className="breadcrumb-separator">›</span>
                    <span className="breadcrumb-current">{selectedCompany?.name}</span>
                </div>
            </div>
            <div className="document-list">
                {loading ? (
                    <div className="loading">Loading documents...</div>
                ) : (
                    completedDocuments.map(document => (
                        <div
                            key={document.id}
                            className="document-item"
                            onClick={() => onDocumentSelect(document)}
                        >
                            <div className="document-name">
                                <span className="document-type-display">
                                    {formatDocumentType(document.document_type)}
                                </span>
                                {document.period_end_date ? (
                                    <span className="document-time-period"> • {new Date(document.period_end_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                                ) : document.time_period && (
                                    <span className="document-time-period"> • {document.time_period}</span>
                                )}
                            </div>
                            <div className="document-meta">
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
                                        {new Date(document.uploaded_at).toLocaleDateString()}
                                    </span>
                                )}
                            </div>
                        </div>
                    ))
                )}

                {!loading && completedDocuments.length === 0 && documents.length > 0 && (
                    <div className="empty-state">Documents are still processing. Check the upload progress page for status.</div>
                )}

                {!loading && documents.length === 0 && (
                    <div className="empty-state">No documents for this company</div>
                )}


            </div>
        </div>
    )
}

export default DocumentList
