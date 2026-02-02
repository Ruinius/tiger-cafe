import React from 'react'
import '../views/document/Document.css'

export default function OrganicGrowthTable({ data, formatNumber, currency: propCurrency, unit: propUnit }) {
    if (!data) return null

    // Determine currency and unit from props or data
    const currency = propCurrency || data.currency || 'N/A'
    const unit = propUnit || data.current_period_revenue_unit || 'N/A'

    return (
        <div className="table-container">
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit && unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
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
                            <th className="text-right col-value">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.prior_period_revenue !== null && (
                            <tr>
                                <td className="col-name">Prior Period Revenue</td>
                                <td className="text-right col-value">{formatNumber(data.prior_period_revenue, data.prior_period_revenue_unit)}</td>
                            </tr>
                        )}
                        {data.current_period_revenue !== null && (
                            <tr>
                                <td className="col-name">Current Period Revenue</td>
                                <td className="text-right col-value">{formatNumber(data.current_period_revenue, data.current_period_revenue_unit)}</td>
                            </tr>
                        )}
                        {data.simple_revenue_growth !== null && (
                            <tr>
                                <td className="col-name">Simple Revenue Growth</td>
                                <td className="text-right col-value">{parseFloat(data.simple_revenue_growth).toFixed(2)}%</td>
                            </tr>
                        )}
                        {data.organic_revenue_growth !== null && (
                            <tr>
                                <td className="col-name">Organic Revenue Growth</td>
                                <td className="text-right col-value">{parseFloat(data.organic_revenue_growth).toFixed(2)}%</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
