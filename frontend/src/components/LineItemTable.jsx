import React from 'react'
import { normalizeLineName } from '../utils/textUtils'

const formatLabel = (value) => {
  if (!value) return 'Unknown'
  return value
    .replace(/_/g, ' ')
    .split(' ')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

export default function LineItemTable({ data, formatNumber, balanceSheet, incomeStatement, typeOverride, categoryFormatter, showCategory = true }) {
  if (!data || !data.line_items || data.line_items.length === 0) return null

  // Determine currency and unit from data or source documents
  const currency = data.currency || balanceSheet?.currency || incomeStatement?.currency || 'N/A'
  const unit = data.unit || balanceSheet?.unit || incomeStatement?.unit || (data.line_items[0]?.unit ? data.line_items[0].unit.replace('_', ' ') : 'N/A')
  const timePeriod = data.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-header">
        <div className="balance-sheet-meta">
          <span><strong>Time Period:</strong> {timePeriod}</span>
          <span><strong>Currency:</strong> {currency}</span>
          {unit && unit !== 'N/A' && (
            <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
          )}
        </div>
      </div>

      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-name">Line Item</th>
              {showCategory && <th className="col-category">Category</th>}
              <th className="text-right col-value">Amount</th>
              <th className="text-right col-type">Type</th>
            </tr>
          </thead>
          <tbody>
            {data.line_items.map((item, index) => {
              const categoryValue = item.category || item.line_category
              const category = categoryFormatter ? categoryFormatter(categoryValue) : (categoryValue || 'N/A')

              let typeContent;
              if (typeOverride) {
                typeContent = typeOverride
              } else {
                typeContent = item.is_operating === null || item.is_operating === undefined ? (
                  <span className="text-muted">—</span>
                ) : (
                  <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                    {item.is_operating ? 'Operating' : 'Non-operating'}
                  </span>
                )
              }

              return (
                <tr key={`${item.line_name}-${index}`}>
                  <td className="col-name">{item.line_name}</td>
                  {showCategory && <td className="col-category">{category}</td>}
                  <td className="text-right col-value">{formatNumber(item.line_value, item.unit)}</td>
                  <td className="text-right col-type">{typeContent}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div >
    </div >
  )
}
