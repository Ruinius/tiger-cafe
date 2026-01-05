import React from 'react'

export default function SharesOutstandingTable({ incomeStatement }) {
  if (!incomeStatement) return null
  const hasShares =
    incomeStatement.basic_shares_outstanding !== null ||
    incomeStatement.diluted_shares_outstanding !== null

  if (!hasShares) return null

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="text-right">Value</th>
              <th>Unit</th>
            </tr>
          </thead>
          <tbody>
            {incomeStatement.basic_shares_outstanding !== null && (
              <tr>
                <td>Basic Shares Outstanding</td>
                <td className="text-right">{incomeStatement.basic_shares_outstanding.toLocaleString()}</td>
                <td>{incomeStatement.basic_shares_outstanding_unit ? incomeStatement.basic_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {incomeStatement.diluted_shares_outstanding !== null && (
              <tr>
                <td>Diluted Shares Outstanding</td>
                <td className="text-right">{incomeStatement.diluted_shares_outstanding.toLocaleString()}</td>
                <td>{incomeStatement.diluted_shares_outstanding_unit ? incomeStatement.diluted_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
