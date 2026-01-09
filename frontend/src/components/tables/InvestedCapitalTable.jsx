import React from 'react'
import '../views/document/Document.css'

export default function InvestedCapitalTable({ historicalCalculations, balanceSheet, formatNumber }) {
    if (!historicalCalculations || historicalCalculations.invested_capital == null || !balanceSheet) return null

    // Determine metadata
    const timePeriod = historicalCalculations.time_period || balanceSheet?.time_period || 'N/A'
    const currency = balanceSheet?.currency || 'N/A'
    const unit = balanceSheet?.unit ? balanceSheet.unit.replace('_', ' ') : 'N/A'

    // Use breakdown from backend if available, otherwise calculate from balance sheet
    let currentAssetsOperating = []
    let currentLiabilitiesOperating = []
    let currentAssetsTotal = 0
    let currentLiabilitiesTotal = 0
    let netWorkingCapital = 0

    if (historicalCalculations?.net_working_capital_breakdown) {
        // Use breakdown from backend
        const breakdown = historicalCalculations.net_working_capital_breakdown
        currentAssetsOperating = breakdown.current_assets || []
        currentLiabilitiesOperating = breakdown.current_liabilities || []
        currentAssetsTotal = breakdown.current_assets_total || 0
        currentLiabilitiesTotal = breakdown.current_liabilities_total || 0
        netWorkingCapital = breakdown.total || 0
    } else if (balanceSheet?.line_items) {
        // Fallback: calculate from balance sheet
        balanceSheet.line_items.forEach(item => {
            const categoryLower = (item.line_category || '').toLowerCase()

            // Check for non-current first (to avoid matching "non-current" when checking for "current")
            const isNonCurrent = categoryLower.includes('non-current') ||
                (categoryLower.includes('long') && categoryLower.includes('term'))
            const isCurrent = !isNonCurrent && categoryLower.includes('current')
            const isAsset = categoryLower.includes('asset')
            const isLiability = categoryLower.includes('liability')
            const isTotal = categoryLower.includes('total') || item.line_name.toLowerCase().includes('total') || item.line_name.toLowerCase().includes('subtotal')

            const isCurrentAsset = isCurrent && isAsset && !isTotal
            const isCurrentLiability = isCurrent && isLiability && !isTotal

            if (isCurrentAsset && item.is_operating === true) {
                currentAssetsOperating.push({
                    line_name: item.line_name,
                    line_value: item.line_value,
                    line_category: item.line_category,
                    is_operating: item.is_operating
                })
            } else if (isCurrentLiability && item.is_operating === true) {
                currentLiabilitiesOperating.push({
                    line_name: item.line_name,
                    line_value: item.line_value,
                    line_category: item.line_category,
                    is_operating: item.is_operating
                })
            }
        })

        currentAssetsTotal = currentAssetsOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0)
        currentLiabilitiesTotal = currentLiabilitiesOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0)
        netWorkingCapital = currentAssetsTotal - currentLiabilitiesTotal
    }

    // Extract line items for net long term operating assets calculation
    let nonCurrentAssetsOperating = []
    let nonCurrentLiabilitiesOperating = []
    let nonCurrentAssetsTotal = 0
    let nonCurrentLiabilitiesTotal = 0
    let netLongTerm = 0

    if (historicalCalculations?.net_long_term_operating_assets_breakdown) {
        const breakdown = historicalCalculations.net_long_term_operating_assets_breakdown
        nonCurrentAssetsOperating = breakdown.non_current_assets || []
        nonCurrentLiabilitiesOperating = breakdown.non_current_liabilities || []
        nonCurrentAssetsTotal = breakdown.non_current_assets_total || 0
        nonCurrentLiabilitiesTotal = breakdown.non_current_liabilities_total || 0
        netLongTerm = breakdown.total || 0
    } else if (balanceSheet?.line_items) {
        balanceSheet.line_items.forEach(item => {
            const categoryLower = (item.line_category || '').toLowerCase()

            // Check for non-current first (to avoid matching "non-current" when checking for "current")
            const isNonCurrent = categoryLower.includes('non-current') ||
                (categoryLower.includes('long') && categoryLower.includes('term'))
            const isAsset = categoryLower.includes('asset')
            const isLiability = categoryLower.includes('liability')
            const isTotal = categoryLower.includes('total') || item.line_name.toLowerCase().includes('total') || item.line_name.toLowerCase().includes('subtotal')

            const isNonCurrentAsset = isNonCurrent && isAsset && !isTotal
            const isNonCurrentLiability = isNonCurrent && isLiability && !isTotal

            if (isNonCurrentAsset && item.is_operating === true) {
                nonCurrentAssetsOperating.push(item)
            } else if (isNonCurrentLiability && item.is_operating === true) {
                nonCurrentLiabilitiesOperating.push(item)
            }
        })

        nonCurrentAssetsTotal = nonCurrentAssetsOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0)
        nonCurrentLiabilitiesTotal = nonCurrentLiabilitiesOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0)
        netLongTerm = nonCurrentAssetsTotal - nonCurrentLiabilitiesTotal
    }

    return (
        <div>
            <h3>Invested Capital</h3>
            <div className="table-header">
                <div className="table-meta">
                    <span><strong>Time Period:</strong> {timePeriod}</span>
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit}</span>
                    )}
                </div>
            </div>

            <div className="table-container" style={{ marginTop: '1rem' }}>
                {/* Current Assets/Liabilities Table */}
                <div style={{ marginBottom: '0.5rem' }}>
                    <div className="financial-table-container">
                        <table className="financial-table">
                            <thead>
                                <tr>
                                    <th className="col-name">Line Item</th>
                                    <th className="col-category">Category</th>
                                    <th className="text-right col-value">Amount</th>
                                    <th className="col-type text-right">Type</th>
                                </tr>
                            </thead>
                            <tbody>
                                {currentAssetsOperating.length > 0 ? currentAssetsOperating.map((item, idx) => (
                                    <tr key={`ca-${idx}`}>
                                        <td className="col-name">{item.line_name}</td>
                                        <td className="col-category">{item.line_category || 'N/A'}</td>
                                        <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet?.unit || historicalCalculations?.unit)}</td>
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
                                )) : (
                                    <tr>
                                        <td colSpan="4" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating current assets found</td>
                                    </tr>
                                )}
                                <tr className="key-total-row">
                                    <td className="col-name">Total Current Assets (Operating)</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(currentAssetsTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                    <td></td>
                                </tr>

                                {currentLiabilitiesOperating.length > 0 ? currentLiabilitiesOperating.map((item, idx) => (
                                    <tr key={`cl-${idx}`}>
                                        <td className="col-name">{item.line_name}</td>
                                        <td className="col-category">{item.line_category || 'N/A'}</td>
                                        <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet?.unit || historicalCalculations?.unit)}</td>
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
                                )) : (
                                    <tr>
                                        <td colSpan="4" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating current liabilities found</td>
                                    </tr>
                                )}
                                <tr className="key-total-row">
                                    <td className="col-name">Total Current Liabilities (Operating)</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(currentLiabilitiesTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                    <td></td>
                                </tr>

                                <tr className="key-total-row">
                                    <td className="col-name">Net Working Capital</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(netWorkingCapital, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                    <td></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Non-Current Assets/Liabilities Table */}
                <div style={{ marginBottom: '0.5rem' }}>
                    <div className="financial-table-container">
                        <table className="financial-table">
                            <thead>
                                <tr>
                                    <th className="col-name">Line Item</th>
                                    <th className="col-category">Category</th>
                                    <th className="text-right col-value">Amount</th>
                                    <th className="col-type text-right">Type</th>
                                </tr>
                            </thead>
                            <tbody>
                                {nonCurrentAssetsOperating.length > 0 ? nonCurrentAssetsOperating.map((item, idx) => (
                                    <tr key={`nca-${idx}`}>
                                        <td className="col-name">{item.line_name}</td>
                                        <td className="col-category">{item.line_category || 'N/A'}</td>
                                        <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet?.unit)}</td>
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
                                )) : (
                                    <tr>
                                        <td colSpan="4" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating non-current assets found</td>
                                    </tr>
                                )}
                                <tr className="key-total-row">
                                    <td className="col-name">Total Non-Current Assets (Operating)</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(nonCurrentAssetsTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                    <td></td>
                                </tr>

                                {nonCurrentLiabilitiesOperating.length > 0 ? nonCurrentLiabilitiesOperating.map((item, idx) => (
                                    <tr key={`ncl-${idx}`}>
                                        <td className="col-name">{item.line_name}</td>
                                        <td className="col-category">{item.line_category || 'N/A'}</td>
                                        <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet.unit)}</td>
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
                                )) : (
                                    <tr>
                                        <td colSpan="4" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating non-current liabilities found</td>
                                    </tr>
                                )}
                                <tr className="key-total-row">
                                    <td className="col-name">Total Non-Current Liabilities (Operating)</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(nonCurrentLiabilitiesTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                    <td></td>
                                </tr>

                                <tr className="key-total-row">
                                    <td className="col-name">Net Long Term Operating Assets</td>
                                    <td className="col-category"></td>
                                    <td className="text-right col-value">{formatNumber(netLongTerm, balanceSheet?.unit)}</td>
                                    <td></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Final Calculation Table */}
                <div style={{ marginTop: '0.5rem', paddingTop: '0.25rem' }}>
                    <div className="financial-table-container">
                        <table className="financial-table">
                            <thead>
                                <tr>
                                    <th className="col-name">Line Item</th>
                                    <th className="text-right col-value">Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr style={{ fontWeight: 600 }}>
                                    <td className="col-name">Net Working Capital</td>
                                    <td className="text-right col-value">{formatNumber(netWorkingCapital, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                </tr>
                                <tr style={{ fontWeight: 600 }}>
                                    <td className="col-name">+ Net Long Term Operating Assets</td>
                                    <td className="text-right col-value">{formatNumber(netLongTerm, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                </tr>
                                <tr className="key-total-row">
                                    <td className="col-name">= Invested Capital</td>
                                    <td className="text-right col-value">{formatNumber(historicalCalculations.invested_capital, historicalCalculations.unit)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    )
}
