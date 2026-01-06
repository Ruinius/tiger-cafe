import React from 'react'

const STANDARD_REFERENCES = [
  { id: 1, label: 'Other Current Assets', category: 'Current Assets' },
  { id: 2, label: 'Other Non-Current Assets', category: 'Non-Current Assets' }
]

const normalizeLineName = (name) =>
  (name || '')
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()

const dedupeLineItems = (items) => {
  const seen = new Map()
  items.forEach((item) => {
    const key = normalizeLineName(item.line_name)
    const score = ['unit', 'is_operating', 'category']
      .map((field) => (item[field] !== null && item[field] !== undefined ? 1 : 0))
      .reduce((sum, value) => sum + value, 0)

    if (!seen.has(key) || score > seen.get(key).score) {
      seen.set(key, { item, score })
    }
  })
  return Array.from(seen.values()).map((entry) => entry.item)
}

const filterTotalLines = (items) => {
  return items.filter((item) => {
    const categoryLabel = STANDARD_REFERENCES.find(
      (reference) => reference.category === item.category
    )?.label
    if (!categoryLabel) return true

    const normalizedName = normalizeLineName(item.line_name)
    const normalizedLabel = normalizeLineName(categoryLabel)
    const isTotalLine =
      normalizedName === normalizedLabel ||
      normalizedName.startsWith(`total ${normalizedLabel}`) ||
      normalizedName.includes(`total ${normalizedLabel}`)

    if (!isTotalLine) return true

    const hasBreakdownItems = items.some(
      (candidate) =>
        candidate !== item &&
        candidate.category === item.category &&
        normalizeLineName(candidate.line_name) !== normalizedName
    )

    return !hasBreakdownItems
  })
}

export default function OtherAssetsTable({ data, balanceSheet, formatNumber }) {
  if (!data || !data.line_items) return null

  const renderTable = (reference) => {
    // Find the standardized line item in the balance sheet
    const balanceSheetItem = balanceSheet?.line_items?.find(item =>
      normalizeLineName(item.line_name).includes(normalizeLineName(reference.label))
    )

    // Filter sub-items for this category
    const subItems = data.line_items.filter(item => item.category === reference.category)
    const hasSubItems = subItems.length > 0 && subItems.some(item => !item.line_name.includes("Residual"))

    return (
      <div key={reference.id} className="balance-sheet-table-container" style={{ marginBottom: '2rem' }}>
        <h4 style={{ marginBottom: '0.5rem' }}>{reference.label}</h4>
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-ref">Ref</th>
              <th className="col-name">Line Item</th>
              <th className="col-category">Category</th>
              <th className="text-right col-value">Amount</th>
              <th className="col-unit">Unit</th>
              <th className="text-right col-type">Type</th>
            </tr>
          </thead>
          <tbody>
            {/* Standardized Line Item (Total) */}
            {balanceSheetItem && (
              <tr className="total-row">
                <td className="col-ref text-muted">{reference.id}</td>
                <td className="col-name bold-text">{balanceSheetItem.line_name}</td>
                <td className="col-category">{reference.category}</td>
                <td className="col-value text-right bold-text">{formatNumber(balanceSheetItem.line_value, balanceSheet.unit)}</td>
                <td className="col-unit">{balanceSheet.unit ? balanceSheet.unit.replace('_', ' ') : 'N/A'}</td>
                <td className="text-right col-type">
                  <span className="text-muted">—</span>
                </td>
              </tr>
            )}

            {/* If no sub-items found (excluding residual), show "nothing found" */}
            {!hasSubItems && (
              <tr>
                <td className="col-ref text-muted">—</td>
                <td className="col-name text-muted italic-text" colSpan="5">Nothing found</td>
              </tr>
            )}

            {/* Sub-items and Residual */}
            {subItems.map((item, index) => (
              <tr key={`${item.line_name}-${index}`}>
                <td className="col-ref text-muted">—</td>
                <td className="col-name">{item.line_name}</td>
                <td className="col-category">{item.category || 'N/A'}</td>
                <td className="col-value text-right">{formatNumber(item.line_value, item.unit)}</td>
                <td className="col-unit">{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
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
    )
  }

  return (
    <div className="balance-sheet-container">
      <div className="standardized-references">
        <div className="standardized-references-title">Standardized References</div>
        <ol>
          {STANDARD_REFERENCES.map((reference) => (
            <li key={reference.id}>{reference.label}</li>
          ))}
        </ol>
      </div>
      {STANDARD_REFERENCES.map(renderTable)}
    </div>
  )
}
