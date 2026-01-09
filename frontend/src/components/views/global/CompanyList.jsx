import React, { useEffect } from 'react'
import { useDashboardData } from '../../../hooks/useDashboardData'
import { useUploadManager } from '../../../hooks/useUploadManager'

function CompanyList({ onCompanySelect, onOpenUploadModal, onShowUploadProgress }) {
    const {
        filteredCompanies,
        loading,
        searchQuery,
        setSearchQuery,
        loadCompanies
    } = useDashboardData()

    const {
        hasActiveUploads,
        uploadingDocuments,
    } = useUploadManager()

    // Load companies on mount
    useEffect(() => {
        loadCompanies()
    }, [loadCompanies])

    return (
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
                <div className="companies-list">
                    {filteredCompanies.map((company) => (
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
                            <span className="doc-count-badge">
                                {company.document_count || 0}
                            </span>
                        </div>
                    ))}
                    {filteredCompanies.length === 0 && (
                        <div className="no-results">
                            <p>No companies found matching "{searchQuery}"</p>
                        </div>
                    )}
                </div>
            )}

            <button
                className={`add-document-button ${hasActiveUploads ? 'has-uploads' : ''}`}
                onClick={hasActiveUploads ? onShowUploadProgress : onOpenUploadModal}
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

export default CompanyList
