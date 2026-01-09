import React from 'react'
import '../views/document/Document.css'

export default function NopatRoicTable({ historicalCalculations, incomeStatement, formatNumber }) {
    if (!historicalCalculations || historicalCalculations.nopat == null) return null

    // Determine metadata
    const timePeriod = historicalCalculations.time_period || incomeStatement?.time_period || 'N/A'
    const currency = incomeStatement?.currency || 'N/A'
    const unit = incomeStatement?.unit ? incomeStatement.unit.replace('_', ' ') : 'N/A'

    const ebita = historicalCalculations.ebita
    const nopat = historicalCalculations.nopat
    const roic = historicalCalculations.roic
    const investedCapital = historicalCalculations.invested_capital

    return (
        <div>
            <h3>NOPAT & ROIC</h3>
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
                        <tr>
                            <td className="col-name">EBITA</td>
                            <td className="text-right col-value">{formatNumber(ebita, historicalCalculations.unit)}</td>
                        </tr>
                        <tr>
                            <td className="col-name">Less: Adjusted Taxes</td>
                            <td className="text-right col-value">
                                {historicalCalculations.adjusted_tax_rate != null && !isNaN(parseFloat(historicalCalculations.adjusted_tax_rate))
                                    ? `(${(parseFloat(historicalCalculations.adjusted_tax_rate) * 100).toFixed(1)}%)`
                                    : '(—)'
                                }
                            </td>
                        </tr>
                        <tr className="key-total-row">
                            <td className="col-name">NOPAT (Net Operating Profit After Tax)</td>
                            <td className="text-right col-value">{formatNumber(nopat, historicalCalculations.unit)}</td>
                        </tr>
                        <tr>
                            <td className="col-name">Invested Capital</td>
                            <td className="text-right col-value">{formatNumber(investedCapital, historicalCalculations.unit)}</td>
                        </tr>
                        <tr className="key-total-row">
                            <td className="col-name">ROIC (Return on Invested Capital)</td>
                            <td className="text-right col-value">
                                {roic != null && !isNaN(parseFloat(roic))
                                    ? `${(parseFloat(roic) * 100).toFixed(2)}%`
                                    : 'N/A'
                                }
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    )
}
