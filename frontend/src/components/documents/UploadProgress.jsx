import React from 'react'

function UploadProgress({
    uploadingDocuments,
    onClose,
    onReplaceAndIndex,
    onCancelDuplicate
}) {
    const getProgressPercentage = (status) => {
        const statusLower = status?.toLowerCase()
        if (statusLower === 'indexed') return 100
        if (statusLower === 'indexing') return 66
        if (statusLower === 'classified' || statusLower === 'classifying') return 33
        return 10
    }

    const getMilestoneStatus = (indexingStatus, milestone) => {
        const statusLower = indexingStatus?.toLowerCase()

        if (milestone === 'uploading') {
            return statusLower ? 'completed' : 'active'
        }

        if (milestone === 'classification') {
            if (statusLower === 'indexed' || statusLower === 'indexing') return 'completed'
            if (statusLower === 'classified' || statusLower === 'classifying') return 'active'
            return 'pending'
        }

        if (milestone === 'indexing') {
            if (statusLower === 'indexed') return 'completed'
            if (statusLower === 'indexing') return 'active'
            return 'pending'
        }

        return 'pending'
    }

    return (
        <div className="panel-content">
            <div className="panel-header">
                <div className="breadcrumb">
                    <button className="breadcrumb-link" onClick={onClose}>
                        Companies
                    </button>
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
                                                onClick={() => onReplaceAndIndex(document.id)}
                                            >
                                                Replace & Index
                                            </button>
                                            <button
                                                className="button-secondary"
                                                onClick={() => onCancelDuplicate(document.id)}
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
    )
}

export default UploadProgress
