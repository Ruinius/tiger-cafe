import React from 'react'

export default function AmortizationTable({ data, formatNumber }) {
  if (!data || !data.line_items || data.line_items.length === 0) return null

  // Determine currency and unit from data
  const currency = data.currency || 'N/A'
  const unit = data.unit || (data.line_items[0]?.unit ? data.line_items[0].unit.replace('_', ' ') : 'N/A')

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-header">
        <div className="balance-sheet-meta">
          <span><strong>Currency:</strong> {currency}</span>
          {unit && unit !== 'N/A' && (
            <span><strong>Unit:</strong> {unit}</span>
          )}
        </div>
      </div>

      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-name">Line Item</th>
              <th className="col-category">Category</th>
              <th className="text-right col-value">Amount</th>
              <th className="text-right col-type">Type</th>
            </tr>
          </thead>
          <tbody>
            {data.line_items.map((item, index) => (
              <tr key={`${item.line_name}-${index}`}>
                <td className="col-name">{item.line_name}</td>
                <td className="col-category">{item.category || 'N/A'}</td>
                <td className="text-right col-value">{formatNumber(item.line_value, item.unit)}</td>
                <td className="text-right col-type">
                  {item.is_operating === null || item.is_operating === undefined ? (
                    <span className="text-muted">—</span>
                  ) : (
                    <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                      {item.is_operating ? 'Operating' : 'Non-operating'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
