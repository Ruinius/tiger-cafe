import React from 'react'

function DocumentList({
    documents,
    onDocumentSelect,
    onAddDocument,
    hasActiveUploads,
    uploadingDocuments,
    onShowUploadProgress
}) {
    const formatDocumentType = (type) => {
        if (!type) return 'Document'
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    }

    return (
        <div className="document-list">
            {documents.map(document => (
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
            ))}
            {documents.length === 0 && (
                <div className="empty-state">No documents for this company</div>
            )}
            <button
                className={`add-document-button ${hasActiveUploads ? 'has-uploads' : ''}`}
                onClick={hasActiveUploads ? onShowUploadProgress : onAddDocument}
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
    )
}

export default DocumentList
