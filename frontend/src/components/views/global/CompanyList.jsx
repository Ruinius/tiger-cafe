import React, { useEffect } from 'react'
import { useDashboardData } from '../../../hooks/useDashboardData'
import { useUploadManager } from '../../../hooks/useUploadManager'
import UploadModal from '../../modals/UploadModal'

function CompanyList({ onCompanySelect }) {
    const {
        filteredCompanies,
        loading,
        searchQuery,
        setSearchQuery,
        loadCompanies
    } = useDashboardData()

    const {
        isUploadModalOpen,
        openUploadModal,
        closeUploadModal,
        handleUploadSuccess,
        hasActiveUploads,
        uploadingDocuments,
        showUploadProgress,
        setShowUploadProgress
    } = useUploadManager(() => loadCompanies()) // Refresh companies on upload success

    // Load companies on mount
    useEffect(() => {
        loadCompanies()
    }, [loadCompanies])

    return (
        <>
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
                            <div className="company-name">{company.name}</div>
                            {company.ticker && (
                                <div className="company-ticker">{company.ticker}</div>
                            )}
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

            <UploadModal
                isOpen={isUploadModalOpen}
                onClose={closeUploadModal}
                onUploadSuccess={handleUploadSuccess}
            />
        </>
    )
}

export default CompanyList
