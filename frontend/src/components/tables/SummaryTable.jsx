import React from 'react'
import '../views/document/Document.css'

export default function SummaryTable({ historicalCalculations, organicGrowth, incomeStatement, formatNumber }) {
    if (!historicalCalculations) return null

    /**
     * @doc Summary Table Line Items (DO NOT REFACTOR)
     * This table MUST display the same line items as the Historical Data table in Company Analysis View.
     * Required line items in exact order:
     * 1. Revenue
     * 2. Simple Revenue Growth
     * 3. Organic Growth
     * 4. EBITA
     * 5. EBITA Margin
     * 6. Effective Tax Rate
     * 7. Adjusted Tax Rate
     * 8. NOPAT
     * 9. Net Working Capital
     * 10. Net Long Term Operating Assets
     * 11. Invested Capital
     * 12. Capital Turnover, Annualized
     * 13. ROIC, Annualized
     * 14. Diluted Shares Outstanding
     * 
     * This ensures consistency across all views and prevents data mismatches.
     */

    // Determine metadata
    const timePeriod = historicalCalculations.time_period || incomeStatement?.time_period || 'N/A'
    const currency = incomeStatement?.currency || 'N/A'
    const unit = incomeStatement?.unit ? incomeStatement.unit.replace('_', ' ') : 'N/A'

    // Extract revenue - try top-level property first, then search line items, then fallback to organic growth data
    let revenue = incomeStatement?.total_revenue
    if (revenue == null && incomeStatement?.line_items) {
        const revItem = incomeStatement.line_items.find(item =>
            item.line_name.includes('Total Net Revenue') ||
            item.line_name === 'Total Revenue' ||
            item.line_name === 'Revenue'
        )
        revenue = revItem?.line_value
    }
    if (revenue == null) {
        revenue = organicGrowth?.current_period_revenue
    }

    const revenueGrowth = organicGrowth?.organic_revenue_growth
    const simpleRevenueGrowth = organicGrowth?.simple_revenue_growth
    const ebita = historicalCalculations.ebita
    const ebitaMargin = revenue ? (ebita / revenue) : (historicalCalculations.ebita_margin)
    const nopat = historicalCalculations.nopat
    const investedCapital = historicalCalculations.invested_capital
    const capitalTurnover = historicalCalculations.capital_turnover || (investedCapital ? (revenue / investedCapital) : null)
    const roic = historicalCalculations.roic

    const dilutedShares = incomeStatement?.diluted_shares_outstanding
    const netLongTermAssets = historicalCalculations.net_long_term_operating_assets

    return (
        <div>
            <h3>Summary Table</h3>
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Time Period:</strong> {timePeriod}</span>
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit}</span>
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
                        {/* Revenue Section */}
                        {revenue != null && (
                            <tr>
                                <td className="col-name">Revenue</td>
                                <td className="text-right col-value">{formatNumber(revenue, unit)}</td>
                            </tr>
                        )}
                        {simpleRevenueGrowth != null && (
                            <tr>
                                <td className="col-name">Simple Revenue Growth</td>
                                <td className="text-right col-value">{(parseFloat(simpleRevenueGrowth) * 100).toFixed(2)}%</td>
                            </tr>
                        )}
                        {revenueGrowth != null && (
                            <tr>
                                <td className="col-name">Organic Growth</td>
                                <td className="text-right col-value">{parseFloat(revenueGrowth).toFixed(2)}%</td>
                            </tr>
                        )}

                        {/* Profitability Section */}
                        {ebita != null && (
                            <tr>
                                <td className="col-name">EBITA</td>
                                <td className="text-right col-value">{formatNumber(ebita, unit)}</td>
                            </tr>
                        )}
                        {ebitaMargin != null && !isNaN(parseFloat(ebitaMargin)) && (
                            <tr>
                                <td className="col-name">EBITA Margin</td>
                                <td className="text-right col-value">{(parseFloat(ebitaMargin) * 100).toFixed(2)}%</td>
                            </tr>
                        )}

                        {/* Tax Section */}
                        {historicalCalculations.effective_tax_rate != null && (
                            <tr>
                                <td className="col-name">Effective Tax Rate</td>
                                <td className="text-right col-value">{(parseFloat(historicalCalculations.effective_tax_rate) * 100).toFixed(2)}%</td>
                            </tr>
                        )}
                        {historicalCalculations.adjusted_tax_rate != null && (
                            <tr>
                                <td className="col-name">Adjusted Tax Rate</td>
                                <td className="text-right col-value">{(parseFloat(historicalCalculations.adjusted_tax_rate) * 100).toFixed(2)}%</td>
                            </tr>
                        )}

                        {/* NOPAT */}
                        {nopat != null && (
                            <tr>
                                <td className="col-name">NOPAT</td>
                                <td className="text-right col-value">{formatNumber(nopat, unit)}</td>
                            </tr>
                        )}

                        {/* Invested Capital Section */}
                        {historicalCalculations.net_working_capital != null && (
                            <tr>
                                <td className="col-name">Net Working Capital</td>
                                <td className="text-right col-value">{formatNumber(historicalCalculations.net_working_capital, unit)}</td>
                            </tr>
                        )}
                        {netLongTermAssets != null && (
                            <tr>
                                <td className="col-name">Net Long Term Operating Assets</td>
                                <td className="text-right col-value">{formatNumber(netLongTermAssets, unit)}</td>
                            </tr>
                        )}
                        {investedCapital != null && (
                            <tr>
                                <td className="col-name">Invested Capital</td>
                                <td className="text-right col-value">{formatNumber(investedCapital, unit)}</td>
                            </tr>
                        )}

                        {/* Return Metrics */}
                        {capitalTurnover != null && !isNaN(parseFloat(capitalTurnover)) && (
                            <tr>
                                <td className="col-name">Capital Turnover, Annualized</td>
                                <td className="text-right col-value">{parseFloat(capitalTurnover).toFixed(4)}</td>
                            </tr>
                        )}
                        {roic != null && (
                            <tr>
                                <td className="col-name">ROIC, Annualized</td>
                                <td className="text-right col-value">
                                    {roic < 0 ? 'negative' : `${(roic * 100).toFixed(2)}%`}
                                </td>
                            </tr>
                        )}

                        {/* Shares Section */}
                        {dilutedShares != null && (
                            <tr>
                                <td className="col-name">Diluted Shares Outstanding</td>
                                <td className="text-right col-value">{dilutedShares.toLocaleString()}</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
