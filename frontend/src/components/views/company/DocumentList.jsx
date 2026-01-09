import React, { useEffect } from 'react'
import { useDocumentData } from '../../../hooks/useDocumentData'
import { useUploadManager } from '../../../hooks/useUploadManager'
import UploadModal from '../../modals/UploadModal'

function DocumentList({ selectedCompany, onDocumentSelect }) {
    const {
        documents,
        loading,
        loadCompanyDocuments
    } = useDocumentData(selectedCompany)

    const {
        isUploadModalOpen,
        openUploadModal,
        closeUploadModal,
        handleUploadSuccess,
        hasActiveUploads,
        uploadingDocuments,
        showUploadProgress, // Used by parent/Orchestrator ideally, but here we can toggle it?
                            // Wait, UploadProgressModal is global. useUploadManager exposes setShowUploadProgress.
        setShowUploadProgress
    } = useUploadManager(() => loadCompanyDocuments(selectedCompany?.id))

    // documents are loaded by the hook when selectedCompany changes

    const formatDocumentType = (type) => {
        if (!type) return 'Document'
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    }

    return (
        <>
            <div className="document-list">
                {loading ? (
                    <div className="loading">Loading documents...</div>
                ) : (
                    documents.map(document => (
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
                    ))
                )}

                {!loading && documents.length === 0 && (
                    <div className="empty-state">No documents for this company</div>
                )}

                <button
                    className={`add-document-button ${hasActiveUploads ? 'has-uploads' : ''}`}
                    onClick={hasActiveUploads ? () => setShowUploadProgress(true) : openUploadModal}
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

            <UploadModal
                isOpen={isUploadModalOpen}
                onClose={closeUploadModal}
                onUploadSuccess={handleUploadSuccess}
            />
        </>
    )
}

export default DocumentList
