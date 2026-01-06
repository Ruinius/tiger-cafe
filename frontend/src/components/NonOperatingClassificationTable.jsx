import React from 'react'

const formatLabel = (value) => {
  if (!value) return 'Unknown'
  return value
    .replace(/_/g, ' ')
    .split(' ')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

export default function NonOperatingClassificationTable({ data, formatNumber, balanceSheet, incomeStatement }) {
  if (!data || !data.line_items || data.line_items.length === 0) return null

  // Helper function to find the original line item category
  const getOriginalCategory = (item) => {
    const source = item.source ? item.source.toLowerCase() : ''
    const lineName = item.line_name

    // Try to find in balance sheet if source indicates balance sheet
    if (balanceSheet && balanceSheet.line_items && (source.includes('balance') || source.includes('balance_sheet'))) {
      const bsItem = balanceSheet.line_items.find(bs => bs.line_name === lineName)
      if (bsItem && bsItem.line_category) {
        return bsItem.line_category
      }
    }

    // Try to find in income statement if source indicates income statement
    if (incomeStatement && incomeStatement.line_items && (source.includes('income') || source.includes('income_statement'))) {
      const isItem = incomeStatement.line_items.find(is => is.line_name === lineName)
      if (isItem && isItem.line_category) {
        return isItem.line_category
      }
    }

    // Fallback: try both if source is unknown
    if (balanceSheet && balanceSheet.line_items) {
      const bsItem = balanceSheet.line_items.find(bs => bs.line_name === lineName)
      if (bsItem && bsItem.line_category) {
        return bsItem.line_category
      }
    }

    if (incomeStatement && incomeStatement.line_items) {
      const isItem = incomeStatement.line_items.find(is => is.line_name === lineName)
      if (isItem && isItem.line_category) {
        return isItem.line_category
      }
    }

    return null
  }

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-name">Line Item</th>
              <th className="col-category">Category</th>
              <th className="text-right col-value">Amount</th>
              <th className="col-unit">Unit</th>
              <th className="text-right col-type">Type</th>
            </tr>
          </thead>
          <tbody>
            {data.line_items.map((item, index) => {
              const originalCategory = getOriginalCategory(item)
              return (
                <tr key={`${item.line_name}-${index}`}>
                  <td className="col-name">{item.line_name}</td>
                  <td className="col-category">{originalCategory || 'N/A'}</td>
                  <td className="text-right col-value">{item.line_value !== null ? formatNumber(item.line_value, item.unit) : 'N/A'}</td>
                  <td className="col-unit">{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
                  <td className="text-right col-type">
                    <span className="type-badge non-operating">Non-Operating</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div >
    </div >
  )
}
