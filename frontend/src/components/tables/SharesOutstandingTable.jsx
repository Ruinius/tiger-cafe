import React from 'react'
import '../views/document/Document.css'

export default function SharesOutstandingTable({ incomeStatement }) {
    if (!incomeStatement) return null

    const basic = incomeStatement.basic_shares_outstanding
    const diluted = incomeStatement.diluted_shares_outstanding

    const hasShares = (basic !== null && basic !== undefined) || (diluted !== null && diluted !== undefined)

    if (!hasShares) {
        return (
            <div className="info-section">
                <p className="info-text" style={{ color: 'var(--error)', fontWeight: 500 }}>
                    Shares outstanding data is missing.
                </p>
                <p className="info-text" style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                    This critical information could not be extracted from the document. Please verify the document contains shares outstanding data.
                </p>
            </div>
        )
    }

    // Determine unit from shares data
    const unit = incomeStatement.basic_shares_outstanding_unit || incomeStatement.diluted_shares_outstanding_unit || 'shares'

    return (
        <div className="table-container">
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
                </div>
            </div>

            <div className="financial-table-container">
                <table className="financial-table">
                    <thead>
                        <tr>
                            <th className="col-name">Line Item</th>
                            <th className="text-right col-value">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(basic !== null && basic !== undefined) && (
                            <tr>
                                <td className="col-name">Basic Shares Outstanding</td>
                                <td className="text-right col-value">{basic.toLocaleString()}</td>
                            </tr>
                        )}
                        {(diluted !== null && diluted !== undefined) && (
                            <tr>
                                <td className="col-name">Diluted Shares Outstanding</td>
                                <td className="text-right col-value">{diluted.toLocaleString()}</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
