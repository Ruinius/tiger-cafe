import React from 'react'
import '../views/document/Document.css'

export default function EBITATable({ historicalCalculations, incomeStatement, formatNumber }) {
    if (!historicalCalculations || historicalCalculations.ebita == null) return null

    // Determine metadata
    const timePeriod = historicalCalculations.time_period || incomeStatement?.time_period || 'N/A'
    const currency = incomeStatement?.currency || 'N/A'
    const unit = incomeStatement?.unit ? incomeStatement.unit.replace('_', ' ') : 'N/A'

    // Use breakdown from backend if available
    const ebitaData = historicalCalculations?.ebita_breakdown || {}
    const ebitaAdjustments = ebitaData.adjustments || []

    /**
     * @doc EBITA Table Layout (DO NOT REFACTOR)
     * This component implements specific logic for displaying EBITA adjustments:
     * 1. Conditional Columns: "Category" column should ONLY appear if there are adjustments.
     * 2. Status Pills: "Type" column must display "Operating" (Green) or "Non-Operating" (Amber) pills.
     * 3. Row Order:
     *      - Operating Income (Reported)
     *      - Adjustments List
     *      - EBITA (Total)
     */
    const operatingIncome = ebitaData.operating_income

    return (
        <div>
            <h3>EBITA</h3>
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
                            {ebitaAdjustments.length > 0 && <th className="col-category">Category</th>}
                            <th className="text-right col-value">Amount</th>
                            <th className="col-type text-right">Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {operatingIncome != null && (
                            <tr>
                                <td className="col-name">Operating Income (Reported)</td>
                                {ebitaAdjustments.length > 0 && <td className="col-category">N/A</td>}
                                <td className="text-right col-value">{formatNumber(operatingIncome, historicalCalculations.unit)}</td>
                                <td className="col-type text-right">
                                    <span className="type-badge operating">Operating</span>
                                </td>
                            </tr>
                        )}

                        {ebitaAdjustments.length > 0 ? (
                            <>
                                {ebitaAdjustments.map((item, idx) => (
                                    <tr key={`ebita-adj-${idx}`}>
                                        <td className="col-name">{item.line_name}</td>
                                        <td className="col-category">{item.category || item.line_category || 'N/A'}</td>
                                        <td className="text-right col-value">{formatNumber(item.line_value, historicalCalculations.unit)}</td>
                                        <td className="col-type text-right">
                                            {item.is_operating === true ? (
                                                <span className="type-badge operating">Operating</span>
                                            ) : item.is_operating === false ? (
                                                <span className="type-badge non-operating">Non-Operating</span>
                                            ) : (
                                                <span className="text-muted">—</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                <tr className="key-total-row">
                                    <td className="col-name">EBITA</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                    <td></td>
                                </tr>
                            </>
                        ) : (
                            <tr className="key-total-row">
                                <td className="col-name">EBITA</td>
                                <td className="text-right col-value">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                <td></td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
