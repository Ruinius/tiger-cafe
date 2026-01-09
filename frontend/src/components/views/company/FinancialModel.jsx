import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import './FinancialModel.css'

function FinancialModel({ selectedCompany, historicalEntries, unit, currency }) {
    const API_BASE_URL = 'http://localhost:8000/api'
    const { isAuthenticated, token } = useAuth()
    const [modelData, setModelData] = useState(null)
    const [assumptions, setAssumptions] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    // Initial load of assumptions
    useEffect(() => {
        if (!selectedCompany) return

        const loadAssumptions = async () => {
            try {
                const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                const response = await axios.get(
                    `${API_BASE_URL}/companies/${selectedCompany.id}/assumptions`,
                    { headers }
                )
                // If API returns empty/null fields, set defaults for UI
                const data = response.data
                setAssumptions({
                    revenue_growth_stage1: data.revenue_growth_stage1 ?? 0.05,
                    revenue_growth_stage2: data.revenue_growth_stage2 ?? 0.04,
                    revenue_growth_terminal: data.revenue_growth_terminal ?? 0.03,
                    ebita_margin_stage1: data.ebita_margin_stage1 ?? 0.20,
                    ebita_margin_stage2: data.ebita_margin_stage2 ?? 0.20,
                    ebita_margin_terminal: data.ebita_margin_terminal ?? 0.20,
                    marginal_capital_turnover_stage1: data.marginal_capital_turnover_stage1 ?? 1.0,
                    marginal_capital_turnover_stage2: data.marginal_capital_turnover_stage2 ?? 1.0,
                    marginal_capital_turnover_terminal: data.marginal_capital_turnover_terminal ?? 1.0,
                    adjusted_tax_rate: data.adjusted_tax_rate ?? 0.25,
                    wacc: data.wacc ?? 0.08
                })
            } catch (err) {
                console.error("Failed to load assumptions", err)
                // Set defaults if failed
                setAssumptions({
                    revenue_growth_stage1: 0.05,
                    revenue_growth_stage2: 0.04,
                    revenue_growth_terminal: 0.03,
                    ebita_margin_stage1: 0.20,
                    ebita_margin_stage2: 0.20,
                    ebita_margin_terminal: 0.20,
                    marginal_capital_turnover_stage1: 1.0,
                    marginal_capital_turnover_stage2: 1.0,
                    marginal_capital_turnover_terminal: 1.0,
                    adjusted_tax_rate: 0.25,
                    wacc: 0.08
                })
            }
        }
        loadAssumptions()
    }, [selectedCompany, isAuthenticated, token])

    // Load Model whenever assumptions change (debounced?)
    // For now, let's load it on mount or when assumptions are saved.
    const loadModel = async () => {
        if (!selectedCompany) return
        setLoading(true)
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/companies/${selectedCompany.id}/financial-model`,
                { headers }
            )
            setModelData(response.data)
        } catch (err) {
            setError("Failed to calculate financial model")
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // Load model initially once assumptions are loaded?
    useEffect(() => {
        if (assumptions && !modelData) {
            loadModel()
        }
    }, [assumptions, selectedCompany])

    // New component for formatted input handling
    const FormattedInput = ({ value, onChange, isPercentage }) => {
        const [localValue, setLocalValue] = useState('')
        const [isEditing, setIsEditing] = useState(false)

        useEffect(() => {
            if (!isEditing) {
                if (value === null || value === undefined) {
                    setLocalValue('')
                } else {
                    setLocalValue(isPercentage ? `${(value * 100).toFixed(1)}%` : Number(value).toFixed(1))
                }
            }
        }, [value, isPercentage, isEditing])

        const handleFocus = () => {
            setIsEditing(true)
            // On focus, show raw value (percentage as whole number for easier editing, e.g. 5 for 5%)
            if (value !== null && value !== undefined) {
                setLocalValue(isPercentage ? (value * 100).toFixed(1) : Number(value).toFixed(1))
            }
        }

        const handleChange = (e) => {
            setLocalValue(e.target.value)
        }

        const handleBlur = () => {
            setIsEditing(false)
            let numericVal = parseFloat(localValue)
            if (isNaN(numericVal)) {
                // Reset to original
                if (value !== null && value !== undefined) {
                    setLocalValue(isPercentage ? `${(value * 100).toFixed(1)}%` : Number(value).toFixed(1))
                } else {
                    setLocalValue('')
                }
                return
            }

            // Convert back 
            if (isPercentage) {
                numericVal = numericVal / 100
            }

            onChange(numericVal)
        }

        const handleKeyDown = (e) => {
            if (e.key === 'Enter') {
                e.target.blur()
            }
        }

        return (
            <input
                type="text"
                value={localValue}
                onChange={handleChange}
                onFocus={handleFocus}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
            />
        )
    }

    const handleAssumptionChange = (key, value) => {
        setAssumptions(prev => ({
            ...prev,
            [key]: value
        }))
    }

    // Local state for assumption inputs
    const [localAssumptions, setLocalAssumptions] = useState({ ...assumptions })

    // Update local state when assumptions prop changes
    useEffect(() => {
        if (assumptions) {
            setLocalAssumptions({ ...assumptions })
        }
    }, [assumptions])

    const handleLocalChange = (key, value) => {
        setLocalAssumptions(prev => ({
            ...prev,
            [key]: value
        }))
    }

    const handleInputBlur = (key) => {
        // Parse the value
        let val = localAssumptions[key]

        // Allow user to clear input
        if (val === '' || val === null || val === undefined) {
            // Revert to original if empty? Or keep as is? Let's revert for safety or default to 0
            // Ideally we just don't save. But let's see.
            // If we want to allow typing, valid numbers need to be parsed.
            return
        }

        // Remove % if present for percentage fields
        let numericVal = parseFloat(String(val).replace('%', ''))

        // Identify percentage fields based on key name or known lists
        const isPercentage = [
            'revenue_growth_stage1', 'revenue_growth_stage2', 'revenue_growth_terminal',
            'ebita_margin_stage1', 'ebita_margin_stage2', 'ebita_margin_terminal',
            'adjusted_tax_rate', 'wacc'
        ].includes(key)

        if (isNaN(numericVal)) {
            // Revert to saved value if invalid
            setLocalAssumptions(prev => ({ ...prev, [key]: assumptions[key] }))
            return
        }

        // Divide by 100 if it was entered as a whole number for percentage fields
        // BUT wait, users might enter "5" meaning 0.05 (5%).
        // Logic: If user enters > 1 for these fields, assume they meant percent.
        // OR simply strict: User sees "5.0%", types "6", resulting in 6 (600%)?
        // Let's implement smart formatting:
        // On blur, we format it back to display string

        // Actually, we want to update the main state (and 'save' conceptually)
        // But the requirement is: "only recalculate when I hit the Re-run button"

        // So we update the 'assumptions' state but do NOT trigger loadModel or API save yet?
        // The original code calculated on mount. The button 'saveAssumptions' calls API then loadModel.
        // So updating 'assumptions' state is fine as long as we don't trigger effects.
        // BUT! 'assumptions' state is what gets sent to API.

        // The issue: "only recalculate when I hit the Re-run button" 
        // My previous implementation had `handleAssumptionChange` which updated `assumptions` state.
        // And `saveAssumptions` which sent `assumptions` to backend.
        // Does `loadModel` trigger on `assumptions` change?
        // Step 305/308 code: 
        // useEffect(() => { if (assumptions) { loadModel() } }, [assumptions, selectedCompany])
        // THIS is the auto-recalculate culprit.

        // We need to REMOVE that effect and use the local inputs.

        // Let's just update the main assumptions state here (as a staging area) 
        // The user wants formatting. So inputs should display "5.0%" and accept "5.0" or "0.05"?
        // Simpler: Inputs are text. show "5.0%". User edits to "6.0". Blur -> update state to 0.06.

        if (isPercentage) {
            if (numericVal > 1) {
                numericVal = numericVal / 100
            }
        }

        // Update the main assumptions state (staging)
        setAssumptions(prev => ({
            ...prev,
            [key]: numericVal
        }))
    }

    const formatInputValue = (key, value) => {
        if (value === null || value === undefined) return ''
        // If user is currently typing (focused), show raw value? 
        // Actually controlled inputs with formatting are tricky.
        // Best approach:
        // 1. Display value is computed from state.
        // 2. On change, update raw state.
        // 3. On blur, format.

        // Let's stick to: display raw number in input, but format it nicely?
        // User asked "Fix the number formatting for the numbers in the assumption cells".
        // Likely means they want to see "5%" instead of "0.05".

        const isPercentage = [
            'revenue_growth_stage1', 'revenue_growth_stage2', 'revenue_growth_terminal',
            'ebita_margin_stage1', 'ebita_margin_stage2', 'ebita_margin_terminal',
            'adjusted_tax_rate', 'wacc'
        ].includes(key)

        if (isPercentage) {
            return `${(value * 100).toFixed(1)}%`
        }
        return value
    }

    const saveAssumptions = async () => {
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            await axios.post(
                `${API_BASE_URL}/companies/${selectedCompany.id}/assumptions`,
                assumptions,
                { headers }
            )
            // After save, reload model
            loadModel()
        } catch (err) {
            setError("Failed to save assumptions")
        }
    }

    const formatNumber = (value) => {
        if (value === null || value === undefined) return 'N/A'
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value)
    }

    const formatPercent = (value) => {
        if (value === null || value === undefined) return 'N/A'
        return `${(parseFloat(value) * 100).toFixed(1)}%`
    }

    const formatRoic = (value) => {
        if (value === null || value === undefined) return 'N/A'
        const num = parseFloat(value)
        if (num < 0) return 'negative'
        if (num > 1) return '>100%'
        return formatPercent(value)
    }

    const formatDecimal = (value) => {
        if (value === null || value === undefined) return 'N/A'
        return value.toFixed(2)
    }

    if (!assumptions) return <div>Loading assumptions...</div>

    return (
        <div className="financial-model">
            {/* Assumptions Title outside the card */}
            <h3 style={{ marginBottom: '1rem' }}>Assumptions</h3>

            <div className="assumptions-section">
                <div className="assumptions-grid">
                    {/* Revenue Growth */}
                    <div className="assumption-group">
                        <h5>Organic Revenue Growth</h5>
                        <label>
                            Stage 1 (Y1-5):
                            <FormattedInput
                                value={assumptions.revenue_growth_stage1}
                                onChange={(val) => handleAssumptionChange('revenue_growth_stage1', val)}
                                isPercentage={true}
                            />
                        </label>
                        <label>
                            Stage 2 (Y6-10):
                            <FormattedInput
                                value={assumptions.revenue_growth_stage2}
                                onChange={(val) => handleAssumptionChange('revenue_growth_stage2', val)}
                                isPercentage={true}
                            />
                        </label>
                        <label>
                            Terminal:
                            <FormattedInput
                                value={assumptions.revenue_growth_terminal}
                                onChange={(val) => handleAssumptionChange('revenue_growth_terminal', val)}
                                isPercentage={true}
                            />
                        </label>
                    </div>

                    <div className="assumption-divider"></div>

                    {/* EBITA Margin */}
                    <div className="assumption-group">
                        <h5>EBITA Margin</h5>
                        <label>
                            Stage 1 (Y1-5):
                            <FormattedInput
                                value={assumptions.ebita_margin_stage1}
                                onChange={(val) => handleAssumptionChange('ebita_margin_stage1', val)}
                                isPercentage={true}
                            />
                        </label>
                        <label>
                            Stage 2 (Y6-10):
                            <FormattedInput
                                value={assumptions.ebita_margin_stage2}
                                onChange={(val) => handleAssumptionChange('ebita_margin_stage2', val)}
                                isPercentage={true}
                            />
                        </label>
                        <label>
                            Terminal:
                            <FormattedInput
                                value={assumptions.ebita_margin_terminal}
                                onChange={(val) => handleAssumptionChange('ebita_margin_terminal', val)}
                                isPercentage={true}
                            />
                        </label>
                    </div>

                    <div className="assumption-divider"></div>

                    {/* Marginal Capital Turnover */}
                    <div className="assumption-group">
                        <h5>Marginal Capital Turnover</h5>
                        <label>
                            Stage 1 (Y1-5):
                            <FormattedInput
                                value={assumptions.marginal_capital_turnover_stage1}
                                onChange={(val) => handleAssumptionChange('marginal_capital_turnover_stage1', val)}
                                isPercentage={false}
                            />
                        </label>
                        <label>
                            Stage 2 (Y6-10):
                            <FormattedInput
                                value={assumptions.marginal_capital_turnover_stage2}
                                onChange={(val) => handleAssumptionChange('marginal_capital_turnover_stage2', val)}
                                isPercentage={false}
                            />
                        </label>
                        <label>
                            Terminal:
                            <FormattedInput
                                value={assumptions.marginal_capital_turnover_terminal}
                                onChange={(val) => handleAssumptionChange('marginal_capital_turnover_terminal', val)}
                                isPercentage={false}
                            />
                        </label>
                    </div>

                    <div className="assumption-divider"></div>

                    {/* Other */}
                    <div className="assumption-group">
                        <h5>Other</h5>
                        <label>
                            Operating Tax Rate:
                            <FormattedInput
                                value={assumptions.adjusted_tax_rate}
                                onChange={(val) => handleAssumptionChange('adjusted_tax_rate', val)}
                                isPercentage={true}
                            />
                        </label>
                        <label>
                            WACC:
                            <FormattedInput
                                value={assumptions.wacc}
                                onChange={(val) => handleAssumptionChange('wacc', val)}
                                isPercentage={true}
                            />
                        </label>
                    </div>
                </div>
                <button onClick={saveAssumptions} className="button-primary" style={{ marginTop: '1rem' }} disabled={loading}>
                    Re-run Valuation
                </button>
            </div>

            {loading && <p>Calculating model...</p>}
            {error && <p className="error-text">{error}</p>}

            {modelData && modelData.projections && (
                <div className="model-results">
                    <h3>Discounted Cash Flow Model</h3>
                    <div className="balance-sheet-table-container">
                        <table className="balance-sheet-table">
                            <thead>
                                <tr>
                                    <th>Year</th>
                                    <th className="text-right">Base</th>
                                    {modelData.projections.map(p => <th key={p.year} className="text-right">{p.year}</th>)}
                                    <th className="text-right">Terminal</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Revenue</td>
                                    <td className="text-right">{formatNumber(modelData.base_year?.revenue)}</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.revenue)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.revenue)}</td>
                                </tr>
                                <tr>
                                    <td>Growth</td>
                                    <td className="text-right">N/A</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatPercent(p.growth_rate)}</td>)}
                                    <td className="text-right">{formatPercent(modelData.terminal_column?.growth_rate)}</td>
                                </tr>
                                <tr>
                                    <td>EBITA</td>
                                    <td className="text-right">{formatNumber(modelData.base_year?.ebita)}</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.ebita)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.ebita)}</td>
                                </tr>
                                <tr>
                                    <td>NOPAT</td>
                                    <td className="text-right">{formatNumber(modelData.base_year?.nopat)}</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.nopat)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.nopat)}</td>
                                </tr>
                                <tr>
                                    <td>Invested Capital</td>
                                    <td className="text-right">{formatNumber(modelData.base_year?.invested_capital)}</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.invested_capital)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.invested_capital)}</td>
                                </tr>
                                <tr>
                                    <td>ROIC</td>
                                    <td className="text-right">{formatRoic(modelData.base_year?.roic)}</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatRoic(p.roic)}</td>)}
                                    <td className="text-right">{formatRoic(modelData.terminal_column?.roic)}</td>
                                </tr>
                                <tr>
                                    <td>FCF</td>
                                    <td className="text-right">N/A</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.fcf)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.fcf)}</td>
                                </tr>
                                <tr>
                                    <td>Discount Factor</td>
                                    <td className="text-right">N/A</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatDecimal(p.discount_factor)}</td>)}
                                    <td className="text-right">{formatDecimal(modelData.terminal_column?.discount_factor)}</td>
                                </tr>
                                <tr>
                                    <td>Present Value</td>
                                    <td className="text-right">N/A</td>
                                    {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.pv_fcf)}</td>)}
                                    <td className="text-right">{formatNumber(modelData.terminal_column?.pv_fcf)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div className="valuation-summary" style={{ marginTop: '2rem' }}>
                        <h3>Intrinsic Value</h3>
                        <div className="balance-sheet-table-container">
                            <table className="balance-sheet-table" style={{ maxWidth: '400px' }}>
                                <tbody>
                                    <tr>
                                        <td>PV of FCF (10y)</td>
                                        <td className="text-right">{formatNumber(modelData.projections.reduce((sum, p) => sum + p.pv_fcf, 0))}</td>
                                    </tr>
                                    <tr>
                                        <td>PV of Terminal Value</td>
                                        <td className="text-right">{formatNumber(modelData.pv_terminal_value)}</td>
                                    </tr>
                                    <tr className="key-total-row">
                                        <td>Enterprise Value</td>
                                        <td className="text-right">{formatNumber(modelData.enterprise_value)}</td>
                                    </tr>
                                    {modelData.current_share_price && parseFloat(modelData.current_share_price) > 0 && (
                                        <>
                                            <tr style={{ height: '20px' }}></tr>
                                            <tr className="key-total-row">
                                                <td>Current Share Price ({selectedCompany.ticker})</td>
                                                <td className="text-right">${formatDecimal(parseFloat(modelData.current_share_price))}</td>
                                            </tr>
                                        </>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default FinancialModel
