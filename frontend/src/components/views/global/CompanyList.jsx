import React, { useEffect, useState, useMemo } from 'react'
import { useDashboardData } from '../../../hooks/useDashboardData'
import { useUploadManager } from '../../../hooks/useUploadManager'
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

    const [sortBy, setSortBy] = useState('name') // 'name', 'last_doc', 'valuation', 'status'

    // Load companies on mount
    useEffect(() => {
        loadCompanies()
    }, [loadCompanies])

    const formatDate = (val) => {
        if (!val) return 'N/A';
        // If it looks like YYYY-MM-DD (length 10), parse as local date
        if (typeof val === 'string' && val.length === 10 && val.includes('-')) {
            const [y, m, d] = val.split('-').map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
        // Else assume ISO / Date object
        const date = new Date(val);
        return isNaN(date.getTime()) ? 'N/A' : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    const sortedCompanies = useMemo(() => {
        if (!filteredCompanies) return [];
        const sorted = [...filteredCompanies];

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

            <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <input
                    type="text"
                    placeholder="Search companies..."
                    className="search-input"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ width: '100%' }}
                />

                <div className="sort-buttons">
                    <span className="sort-label">Sort by:</span>
                    <button
                        className={`sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                        onClick={() => setSortBy('name')}
                    >
                        Name
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'last_doc' ? 'active' : ''}`}
                        onClick={() => setSortBy('last_doc')}
                    >
                        Last Doc
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'valuation' ? 'active' : ''}`}
                        onClick={() => setSortBy('valuation')}
                    >
                        Valuation Date
                    </button>
                    <button
                        className={`sort-btn ${sortBy === 'status' ? 'active' : ''}`}
                        onClick={() => setSortBy('status')}
                    >
                        Status
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
                                        <span className="stat-label">Date Financials Cover</span>
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
