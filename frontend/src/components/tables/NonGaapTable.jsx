import React from 'react'
import '../views/document/Document.css'

export default function NonGaapTable({ data, formatNumber, currency = 'N/A', unit = 'N/A', timePeriod = 'N/A' }) {
    if (!data || !data.line_items || data.line_items.length === 0) return null

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
                    {data.chunk_index !== undefined && data.chunk_index !== null && (
                        <span><strong>Chunk Index:</strong> {data.chunk_index}</span>
                    )}
                </div>
            </div>

            <div className="financial-table-container">
                <table className="financial-table">
                    <thead>
                        <tr>
                            <th className="col-name">Line Item</th>
                            {/* Removed Standardized Name column */}
                            <th className="text-right col-value">Amount</th>
                            <th className="text-right col-type">Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.line_items.map((item, index) => {
                            const isCalculated = item.is_calculated === true;
                            const nameLower = (item.line_name || '').toLowerCase()
                            const categoryLower = (item.line_category || '').toLowerCase()
                            const isKey = nameLower.includes('total') ||
                                nameLower.includes('subtotal') ||
                                (nameLower.includes('revenue') && !nameLower.includes('cost of') && !nameLower.includes('deferred revenue')) ||
                                nameLower.includes('gross profit') ||
                                nameLower.includes('operating income') ||
                                nameLower.includes('net income') ||
                                nameLower.includes('ebita') ||
                                nameLower.includes('ebitda') ||
                                nameLower.includes('invested capital') ||
                                nameLower.includes('net working capital') ||
                                categoryLower === 'total' ||
                                isCalculated

                            return (
                                <tr key={`${item.line_name}-${index}`} className={isKey ? 'key-total-row' : ''}>
                                    <td className="col-name">{item.line_name}</td>
                                    <td className="text-right col-value">{formatNumber(item.line_value, item.unit)}</td>
                                    <td className="text-right col-type">
                                        {item.is_operating === null || item.is_operating === undefined ? (
                                            <span className="text-muted">—</span>
                                        ) : (
                                            <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                                {item.is_operating ? 'Operating' : 'Non-Operating'}
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
