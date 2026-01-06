import React from 'react'

export default function SharesOutstandingTable({ incomeStatement }) {
  if (!incomeStatement) return null
  
  const hasShares =
    incomeStatement.basic_shares_outstanding !== null ||
    incomeStatement.diluted_shares_outstanding !== null

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

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-name">Metric</th>
              <th className="text-right col-value">Amount</th>
              <th className="col-unit">Unit</th>
            </tr>
          </thead>
          <tbody>
            {incomeStatement.basic_shares_outstanding !== null && (
              <tr>
                <td className="col-name">Basic Shares Outstanding</td>
                <td className="text-right col-value">{incomeStatement.basic_shares_outstanding.toLocaleString()}</td>
                <td className="col-unit">{incomeStatement.basic_shares_outstanding_unit ? incomeStatement.basic_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {incomeStatement.diluted_shares_outstanding !== null && (
              <tr>
                <td className="col-name">Diluted Shares Outstanding</td>
                <td className="text-right col-value">{incomeStatement.diluted_shares_outstanding.toLocaleString()}</td>
                <td className="col-unit">{incomeStatement.diluted_shares_outstanding_unit ? incomeStatement.diluted_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div >
    </div >
  )
}
