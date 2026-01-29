import React, { useEffect, useState, useMemo } from 'react'
import { useDashboardData } from '../../../hooks/useDashboardData'
import { useUploadManager } from '../../../hooks/useUploadManager'
import { formatDate } from '../../../utils/formatting'
import './Dashboard.css'

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

    const [sortBy, setSortBy] = useState('status') // 'name', 'last_doc', 'valuation', 'status'

    // Load companies on mount
    useEffect(() => {
        loadCompanies()
    }, [loadCompanies])



    const sortedCompanies = useMemo(() => {
        if (!filteredCompanies) return [];
        // Filter out "ghost" companies (those with 0 documents)
        const validCompanies = filteredCompanies.filter(c => c.document_count > 0);
        const sorted = [...validCompanies];

        sorted.sort((a, b) => {
            switch (sortBy) {
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'last_doc':
                    // Newest first (descending)
                    return (b.latest_document_date || '').localeCompare(a.latest_document_date || '');
                case 'valuation':
                    // Newest first (descending)
                    const dateA = a.last_valuation_date ? new Date(a.last_valuation_date).getTime() : 0;
                    const dateB = b.last_valuation_date ? new Date(b.last_valuation_date).getTime() : 0;
                    return dateB - dateA;
                case 'status':
                    // Status = percent_undervalued
                    // User probably wants most ACTIONABLE first (e.g. Most Undervalued -> Least Undervalued -> Overvalued)
                    // High positive % => Undervalued. Negative % => Overvalued.
                    // Sort Descending
                    const valA = a.percent_undervalued !== null && a.percent_undervalued !== undefined ? a.percent_undervalued : -Infinity;
                    const valB = b.percent_undervalued !== null && b.percent_undervalued !== undefined ? b.percent_undervalued : -Infinity;
                    return valB - valA;
                default:
                    return 0;
            }
        });
        return sorted;
    }, [filteredCompanies, sortBy]);

    return (
        <div className="panel-content">
            <div className="panel-header">
                <span className="breadcrumb-current">Companies</span>
            </div>

            <div style={{ marginBottom: '1rem' }}>
                {/* Search and Add Button Row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <input
                        type="text"
                        placeholder="Search companies..."
                        className="search-input"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{ flex: 1, minWidth: '200px' }}
                    />

                    <button
                        className="round-action-btn"
                        onClick={loadCompanies}
                        title="Refresh company list"
                    >
                        <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                        </svg>
                    </button>

                    <button
                        className={`round-action-btn primary ${hasActiveUploads ? 'has-uploads' : ''}`}
                        onClick={hasActiveUploads ? onShowUploadProgress : onOpenUploadModal}
                        title={hasActiveUploads ? `Uploading ${uploadingDocuments.length} document(s)` : 'Add Document'}
                    >
                        {hasActiveUploads ? (
                            <span className="button-spinner" aria-hidden="true" />
                        ) : (
                            <svg
                                width="20"
                                height="20"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                        )}
                    </button>
                </div>

                {/* Sort Buttons Row */}
                <div className="sort-buttons" style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                    <span className="sort-label">Sort:</span>
                    <button
                        className={`sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                        onClick={() => setSortBy('name')}
                        style={{ display: 'none' }}
                    >
                        Name
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'last_doc' ? 'active' : ''}`}
                        onClick={() => setSortBy('last_doc')}
                    >
                        Most Recent Document
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'valuation' ? 'active' : ''}`}
                        onClick={() => setSortBy('valuation')}
                    >
                        Most Recent Valuation
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'status' ? 'active' : ''}`}
                        onClick={() => setSortBy('status')}
                    >
                        Over/under-valuation
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="loading">Loading companies...</div>
            ) : (
                <div className="companies-list">
                    {sortedCompanies.map((company) => {
                        const isUndervalued = company.percent_undervalued >= 0;
                        const valuationColor = company.percent_undervalued === null
                            ? ''
                            : company.percent_undervalued > 0.30
                                ? 'val-green'
                                : company.percent_undervalued < -0.15
                                    ? 'val-red'
                                    : 'val-yellow';

                        return (
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

                                <div className="company-stats">
                                    <div className="stat-row">
                                        <span className="stat-label">Most Recent Document</span>
                                        <span className="stat-value">{formatDate(company.latest_document_date)}</span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Most Recent Valuation</span>
                                        <span className={`stat-value ${!company.last_valuation_date ? 'needs-val' : ''}`}>
                                            {company.last_valuation_date
                                                ? formatDate(company.last_valuation_date)
                                                : 'Needs Valuation'}
                                        </span>
                                    </div>
                                    {company.percent_undervalued !== null && company.percent_undervalued !== undefined && (
                                        <div className="stat-row">
                                            <span className="stat-label">Over/under-valuation</span>
                                            <span className={`valuation-badge ${valuationColor}`}>
                                                {Math.abs(company.percent_undervalued * 100).toFixed(1)}% {isUndervalued ? 'Under' : 'Over'}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                    {sortedCompanies.length === 0 && (
                        <div className="no-results">
                            <p>No companies found matching "{searchQuery}"</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default CompanyList
