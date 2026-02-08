import React, { useEffect } from 'react'
import { useDocumentData } from '../../../hooks/useDocumentData'
import { formatDate } from '../../../utils/formatting'

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

    // Helper function to get badge class and tooltip based on status
    const getBadgeInfo = (status, label) => {
        const labelMap = {
            'BS': 'Balance Sheet',
            'IS': 'Income Statement',
            'OG': 'Organic Growth',
            'SO': 'Shares Outstanding'
        }
        const fullLabel = labelMap[label] || label

        if (status === 'success') {
            return {
                className: 'status-badge status-success',
                tooltip: `${fullLabel}: Extracted and validated`
            }
        } else if (status === 'warning') {
            return {
                className: 'status-badge status-warning',
                tooltip: `${fullLabel}: Validation failed or incomplete data`
            }
        } else if (status === 'error') {
            return {
                className: 'status-badge status-error',
                tooltip: `${fullLabel}: Not found`
            }
        }
        return null
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
                    completedDocuments.map(document => {
                        const bsBadge = getBadgeInfo(document.balance_sheet_status, 'BS')
                        const isBadge = getBadgeInfo(document.income_statement_status, 'IS')
                        const ogBadge = getBadgeInfo(document.organic_growth_status, 'OG')
                        const soBadge = getBadgeInfo(document.shares_outstanding_status, 'SO')

                        return (
                            <div
                                key={document.id}
                                className="document-item"
                                onClick={() => onDocumentSelect(document)}
                            >
                                <div className="document-name">
                                    <span className="document-type-display">
                                        {formatDocumentType(document.document_type)}
                                    </span>
                                    {document.time_period && (
                                        <span className="document-time-period"> • {document.time_period}</span>
                                    )}
                                    {document.period_end_date ? (
                                        <span className="document-time-period"> • {formatDate(document.period_end_date)}</span>
                                    ) : !document.time_period && (
                                        <span className="document-time-period"> • N/A</span>
                                    )}
                                </div>
                                <div className="document-meta">
                                    {document.duplicate_detected && (
                                        <span
                                            className="status-badge status-error"
                                            title="Duplicate: This document is a duplicate of an existing document"
                                            style={{ backgroundColor: 'var(--error, #E5484D)', color: 'white' }}
                                        >
                                            dup
                                        </span>
                                    )}
                                    {bsBadge && (
                                        <span className={bsBadge.className} title={bsBadge.tooltip}>
                                            BS
                                        </span>
                                    )}
                                    {isBadge && (
                                        <span className={isBadge.className} title={isBadge.tooltip}>
                                            IS
                                        </span>
                                    )}
                                    {ogBadge && (
                                        <span className={ogBadge.className} title={ogBadge.tooltip}>
                                            OG
                                        </span>
                                    )}
                                    {soBadge && (
                                        <span className={soBadge.className} title={soBadge.tooltip}>
                                            SO
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
                        )
                    })
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
