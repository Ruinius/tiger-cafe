import React from 'react'
import '../../../components/views/document/Document.css'

/**
 * A shared table component for displaying a list of financial line items.
 * 
 * @param {Object} props
 * @param {Object} props.data - The data object containing line_items array
 * @param {Function} props.formatNumber - Function to format numeric values
 * @param {string} [props.currency] - Currency code (e.g. 'USD')
 * @param {string} [props.unit] - Unit scaling (e.g. 'millions')
 * @param {string} [props.timePeriod] - Time period string (e.g. 'FY2023')
 * @param {React.ReactNode} [props.typeOverride] - Optional override for the "Type" column content
 * @param {Function} [props.categoryFormatter] - Optional function to format category names
 * @param {boolean} [props.showCategory=true] - Whether to show the category column
 */
export default function LineItemTable({
    data,
    formatNumber,
    currency = 'N/A',
    unit = 'N/A',
    timePeriod = 'N/A',
    typeOverride,
    categoryFormatter,
    showCategory = true
}) {
    if (!data || !data.line_items || data.line_items.length === 0) return null

    // If props are provided, use them. Fallback to data properties if available.
    // This allows the parent to explicitly override or allows self-contained data objects.
    const displayCurrency = currency !== 'N/A' ? currency : (data.currency || 'N/A')
    const displayUnit = unit !== 'N/A' ? unit : (data.unit || (data.line_items[0]?.unit ? data.line_items[0].unit.replace('_', ' ') : 'N/A'))
    const displayTimePeriod = timePeriod !== 'N/A' ? timePeriod : (data.time_period || 'N/A')

    return (
        <div className="table-container">
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Time Period:</strong> {displayTimePeriod}</span>
                    <span><strong>Currency:</strong> {displayCurrency}</span>
                    {displayUnit && displayUnit !== 'N/A' && (
                        <span><strong>Unit:</strong> {displayUnit.replace('_', ' ')}</span>
                    )}
                </div>
            </div>

            <div className="financial-table-container">
                <table className="financial-table">
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
                                        {item.is_operating ? 'Operating' : 'Non-Operating'}
                                    </span>
                                )
                            }

                            const nameLower = (item.line_name || '').toLowerCase()
                            const categoryLower = (categoryValue || '').toLowerCase()
                            const isKey = nameLower.includes('total') ||
                                nameLower.includes('subtotal') ||
                                (nameLower.includes('revenue') && !nameLower.includes('cost of')) ||
                                nameLower.includes('gross profit') ||
                                nameLower.includes('operating income') ||
                                nameLower.includes('net income') ||
                                nameLower.includes('ebita') ||
                                nameLower.includes('ebitda') ||
                                nameLower.includes('invested capital') ||
                                nameLower.includes('net working capital') ||
                                categoryLower === 'total'

                            return (
                                <tr key={`${item.line_name}-${index}`} className={isKey ? 'key-total-row' : ''}>
                                    <td className="col-name">{item.line_name}</td>
                                    {showCategory && <td className="col-category">{category}</td>}
                                    <td className="text-right col-value">{formatNumber(item.line_value, item.unit)}</td>
                                    <td className="text-right col-type">{typeContent}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
