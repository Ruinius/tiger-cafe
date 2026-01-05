import React from 'react'

const STANDARD_REFERENCES = [
  { id: 1, label: 'Other Current Liabilities', category: 'Current Liabilities' },
  { id: 2, label: 'Other Non-Current Liabilities', category: 'Non-Current Liabilities' }
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

export default function OtherLiabilitiesTable({ data, formatNumber }) {
  if (!data || !data.line_items || data.line_items.length === 0) return null

  const filteredItems = dedupeLineItems(filterTotalLines(data.line_items))

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
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Line Item</th>
              <th className="text-right">Value</th>
              <th>Unit</th>
              <th>Category</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item, index) => {
              const reference = STANDARD_REFERENCES.find(
                (standard) => standard.category === item.category
              )
              return (
                <tr key={`${item.line_name}-${index}`}>
                  <td className="text-muted">{reference ? reference.id : '—'}</td>
                  <td>{item.line_name}</td>
                  <td className="text-right">{formatNumber(item.line_value, item.unit)}</td>
                  <td>{item.unit ? item.unit.replace('_', ' ') : 'N/A'}</td>
                  <td>{item.category || 'N/A'}</td>
                  <td>
                    {item.is_operating === null || item.is_operating === undefined ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                        {item.is_operating ? 'Operating' : 'Non-operating'}
                      </span>
                    )}
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
