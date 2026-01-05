import React from 'react'

const formatLabel = (value) => {
  if (!value) return 'Unknown'
  return value
    .replace(/_/g, ' ')
    .split(' ')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

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
            {data.line_items.map((item, index) => {
              const categoryLabel = formatLabel(item.category)
              const sourceLabel = formatLabel(item.source)
              return (
                <tr key={`${item.line_name}-${index}`}>
                  <td>{item.line_name}</td>
                  <td className="text-right">{item.line_value !== null ? formatNumber(item.line_value, item.unit) : 'N/A'}</td>
                  <td>{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
                  <td>
                    <span className="classification-pill category" title={categoryLabel}>
                      {categoryLabel}
                    </span>
                  </td>
                  <td>
                    <span className="classification-pill source" title={sourceLabel}>
                      {sourceLabel}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
