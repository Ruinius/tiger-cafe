import React from 'react'

export default function AmortizationTable({ data, formatNumber }) {
  if (!data || !data.line_items || data.line_items.length === 0) return null

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th>Line Item</th>
              <th className="text-right">Value</th>
              <th>Unit</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {data.line_items.map((item, index) => (
              <tr key={`${item.line_name}-${index}`}>
                <td>{item.line_name}</td>
                <td className="text-right">{formatNumber(item.line_value, item.unit)}</td>
                <td>{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
                <td>{item.is_operating ? 'Operating' : 'Non-operating'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
