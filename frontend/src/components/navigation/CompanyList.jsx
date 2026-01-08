import React from 'react'

function CompanyList({ companies, searchQuery, onCompanySelect, onShowUploadProgress }) {
    const filteredCompanies = companies.filter(company =>
        company.name.toLowerCase().includes(searchQuery.toLowerCase())
    )

    return (
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
    )
}

export default CompanyList
