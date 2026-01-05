import React from 'react'

export default function NonOperatingClassificationTable({ data, formatNumber }) {
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
              <th>Category</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {data.line_items.map((item, index) => (
              <tr key={`${item.line_name}-${index}`}>
                <td>{item.line_name}</td>
                <td className="text-right">{item.line_value !== null ? formatNumber(item.line_value, item.unit) : 'N/A'}</td>
                <td>{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
                <td>{item.category || 'Unknown'}</td>
                <td>{item.source ? item.source.replace('_', ' ') : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
