import React from 'react'
import '../views/document/Document.css'

export default function AdjustedTaxTable({ historicalCalculations, incomeStatement, formatNumber }) {
    if (!historicalCalculations || historicalCalculations.nopat == null) return null

    // Determine metadata
    const timePeriod = historicalCalculations.time_period || incomeStatement?.time_period || 'N/A'
    const currency = incomeStatement?.currency || 'N/A'
    const unit = incomeStatement?.unit ? incomeStatement.unit.replace('_', ' ') : 'N/A'

    // Extract breakdown data
    const breakdown = historicalCalculations.adjusted_tax_rate_breakdown || {}
    const adjustments = breakdown.adjustments || []

    /**
     * @doc Adjusted Tax Rate Table Layout (DO NOT REFACTOR)
     * This component implements a specialized layout required by the Product Specs:
     * 1. Two-table layout:
     *      - Table 1: Detailed adjustments list (Operating/Non-Operating).
     *      - Table 2: Compact Summary (max-width: 500px) showing exact calculation steps.
     * 2. Specific Line Items:
     *      - Effective Tax Rate (calculated locally)
     *      - Adjusted Tax Rate (bolded, bottom row)
     * 3. Styling:
     *      - Uses inline styles for the summary table (maxWidth: 500px) to prevent global CSS pollution.
     *      - This is INTENTIONAL. Do not "fix" this to be a standard full-width table.
    */
    const marginalRate = breakdown.marginal_rate || 0.25
    const reportedTax = breakdown.reported_tax_expense
    const adjustedTaxRate = historicalCalculations.adjusted_tax_rate
    const ebita = historicalCalculations.ebita

    const totalTaxAdjustments = adjustments.reduce((sum, adj) => sum + parseFloat(adj.tax_effect || 0), 0)
    const adjustedTaxExpense = (reportedTax || 0) + totalTaxAdjustments

    // Look for standard name for tax expense
    const taxExpenseItem = incomeStatement?.line_items?.find(item =>
        item.line_name.includes('Provision') && item.line_name.includes('Income Taxes')
    )
    const taxExpenseName = taxExpenseItem?.line_name || 'Provision (Benefit) for Income Taxes'

    // Use backend-calculated effective tax rate (already computed in historical_calculations.py)
    const effectiveTaxRate = historicalCalculations.effective_tax_rate

    return (
        <div>
            <h3>Adjusted Tax Rate</h3>
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Time Period:</strong> {timePeriod}</span>
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit}</span>
                    )}
                </div>
            </div>

            <div className="table-container">
                <div className="financial-table-container">
                    <table className="financial-table">
                        <thead>
                            <tr>
                                <th className="col-name">Line Item</th>
                                <th className="text-right col-value">Amount</th>
                                <th className="text-right col-value">Tax Effect (@{(marginalRate * 100).toFixed(0)}%)</th>
                                <th className="col-type text-right">Type</th>
                            </tr>
                        </thead>
                        <tbody>
                            {adjustments.length > 0 && adjustments.map((adj, idx) => (
                                <tr key={`tax-adj-${idx}`}>
                                    <td className="col-name">{adj.line_name}</td>
                                    <td className="text-right col-value">{formatNumber(adj.line_value, historicalCalculations.unit)}</td>
                                    <td className="text-right col-value">{formatNumber(adj.tax_effect, historicalCalculations.unit)}</td>
                                    <td className="col-type text-right">
                                        <span className="type-badge non-operating">Non-Operating</span>
                                    </td>
                                </tr>
                            ))}

                            <tr className="key-total-row">
                                <td className="col-name">Total Tax Adjustments</td>
                                <td className="text-right col-value">—</td>
                                <td className="text-right col-value">{formatNumber(totalTaxAdjustments, historicalCalculations.unit)}</td>
                                <td></td>
                            </tr>
                        </tbody>
                    </table>
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
                                <td className="col-name">Effective Tax Rate</td>
                                <td className="text-right col-value">
                                    {effectiveTaxRate != null ? `${(effectiveTaxRate * 100).toFixed(1)}%` : '—'}
                                </td>
                            </tr>
                            <tr>
                                <td className="col-name">{taxExpenseName}</td>
                                <td className="text-right col-value">{formatNumber(reportedTax, historicalCalculations.unit)}</td>
                            </tr>
                            <tr>
                                <td className="col-name">Total Tax Adjustments</td>
                                <td className="text-right col-value">{formatNumber(totalTaxAdjustments, historicalCalculations.unit)}</td>
                            </tr>
                            <tr className="key-total-row">
                                <td className="col-name">Adjusted Tax Expense</td>
                                <td className="text-right col-value">{formatNumber(adjustedTaxExpense, historicalCalculations.unit)}</td>
                            </tr>
                            <tr>
                                <td className="col-name">EBITA</td>
                                <td className="text-right col-value">{formatNumber(ebita, historicalCalculations.unit)}</td>
                            </tr>
                            <tr className="key-total-row">
                                <td className="col-name"><strong>Adjusted Tax Rate</strong></td>
                                <td className="text-right col-value">
                                    <strong>
                                        {adjustedTaxRate != null && !isNaN(parseFloat(adjustedTaxRate))
                                            ? `${(parseFloat(adjustedTaxRate) * 100).toFixed(2)}%`
                                            : 'N/A'
                                        }
                                    </strong>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    )
}
