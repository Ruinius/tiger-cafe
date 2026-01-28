import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { API_BASE_URL } from '../../../config'
import './FinancialModel.css'

function FinancialModel({ selectedCompany, historicalEntries, unit, currency }) {
    const { isAuthenticated, token } = useAuth()
    const [modelData, setModelData] = useState(null)
    const [assumptions, setAssumptions] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    // Helper function to bound WACC to 7-11% range
    const boundWacc = (value) => {
        if (value === null || value === undefined) return 0.09 // Default to 9% if no value
        const numValue = parseFloat(value)
        return Math.max(0.07, Math.min(0.11, numValue))
    }

    const ToolTip = ({ text }) => (
        <div className="tooltip-container">
            <div className="tooltip-icon">i</div>
            <div className="tooltip-text">{text}</div>
        </div>
    )

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
                    beta: data.beta ?? 1.0,
                    adjusted_tax_rate: data.adjusted_tax_rate ?? 0.25,
                    wacc: boundWacc(data.wacc),
                    diluted_shares_outstanding: data.diluted_shares_outstanding ?? null,
                    base_revenue: data.base_revenue ?? null,
                    weight_of_equity: data.weight_of_equity ?? 1.0,
                    cost_of_debt: data.cost_of_debt ?? 0.05,
                    calculated_wacc: data.calculated_wacc ?? 0.09,
                    market_cap: data.market_cap ?? 0,
                    currency_conversion_rate: data.currency_conversion_rate ?? 1.0,
                    adr_conversion_factor: data.adr_conversion_factor ?? 1.0
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
                    beta: 1.0,
                    adjusted_tax_rate: 0.25,
                    wacc: 0.09,
                    diluted_shares_outstanding: null,
                    base_revenue: null,
                    weight_of_equity: 1.0,
                    cost_of_debt: 0.05,
                    calculated_wacc: 0.09,
                    market_cap: 0
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

    // Load model initially once assumptions are loaded
    const hasLoadedInitialModel = React.useRef(false)
    useEffect(() => {
        if (selectedCompany && assumptions && !hasLoadedInitialModel.current) {
            loadModel()
            hasLoadedInitialModel.current = true
        }
    }, [selectedCompany, assumptions])

    // Reset the ref when company changes
    useEffect(() => {
        hasLoadedInitialModel.current = false
    }, [selectedCompany])


    const [valuations, setValuations] = useState([])

    // Load valuations
    useEffect(() => {
        if (!selectedCompany) return
        const loadValuations = async () => {
            try {
                const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                const response = await axios.get(
                    `${API_BASE_URL}/companies/${selectedCompany.id}/valuations`,
                    { headers }
                )
                setValuations(response.data)
            } catch (err) {
                console.error("Failed to load valuations", err)
            }
        }
        loadValuations()
    }, [selectedCompany, isAuthenticated, token])

    const handleSaveValuation = async () => {
        if (!modelData) return
        setLoading(true)
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const payload = {
                fair_value: modelData.fair_value_per_share,
                share_price_at_time: modelData.current_share_price ? parseFloat(modelData.current_share_price) : null,
                percent_undervalued: modelData.percent_undervalued
            }
            await axios.post(
                `${API_BASE_URL}/companies/${selectedCompany.id}/valuations`,
                payload,
                { headers }
            )
            // Reload valuations
            const response = await axios.get(
                `${API_BASE_URL}/companies/${selectedCompany.id}/valuations`,
                { headers }
            )
            setValuations(response.data)
        } catch (err) {
            setError("Failed to save valuation")
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleDeleteValuation = async (id) => {
        // Optimistic delete
        setValuations(prev => prev.filter(v => v.id !== id))
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            await axios.delete(
                `${API_BASE_URL}/companies/${selectedCompany.id}/valuations/${id}`,
                { headers }
            )
        } catch (err) {
            console.error("Failed to delete valuation", err)
            // Reload if failed
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/companies/${selectedCompany.id}/valuations`,
                { headers }
            )
            setValuations(response.data)
        }
    }


    // New component for formatted input handling
    const FormattedInput = ({ value, onChange, isPercentage, decimalPlaces = 1, useSeparators = false, ...props }) => {
        const [localValue, setLocalValue] = useState('')
        const [isEditing, setIsEditing] = useState(false)

        useEffect(() => {
            if (!isEditing) {
                if (value === null || value === undefined) {
                    setLocalValue('')
                } else {
                    if (isPercentage) {
                        setLocalValue(`${(value * 100).toFixed(decimalPlaces)}%`)
                    } else if (useSeparators) {
                        setLocalValue(new Intl.NumberFormat('en-US', {
                            minimumFractionDigits: decimalPlaces,
                            maximumFractionDigits: decimalPlaces
                        }).format(value))
                    } else {
                        setLocalValue(Number(value).toFixed(decimalPlaces))
                    }
                }
            }
        }, [value, isPercentage, isEditing, decimalPlaces, useSeparators])

        const handleFocus = () => {
            setIsEditing(true)
            // On focus, show raw value (no separators for easier editing)
            if (value !== null && value !== undefined) {
                setLocalValue(isPercentage ? (value * 100).toFixed(decimalPlaces) : Number(value).toFixed(decimalPlaces))
            }
        }

        const handleChange = (e) => {
            setLocalValue(e.target.value)
        }

        const handleBlur = () => {
            setIsEditing(false)
            // Remove commas if present
            const cleanValue = localValue.toString().replace(/,/g, '')
            let numericVal = parseFloat(cleanValue)
            if (isNaN(numericVal)) {
                // Reset to original
                if (value !== null && value !== undefined) {
                    if (isPercentage) {
                        setLocalValue(`${(value * 100).toFixed(decimalPlaces)}%`)
                    } else if (useSeparators) {
                        setLocalValue(new Intl.NumberFormat('en-US', {
                            minimumFractionDigits: decimalPlaces,
                            maximumFractionDigits: decimalPlaces
                        }).format(value))
                    } else {
                        setLocalValue(Number(value).toFixed(decimalPlaces))
                    }
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
                {...props}
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

    const resetAssumptions = async () => {
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.delete(
                `${API_BASE_URL}/companies/${selectedCompany.id}/assumptions`,
                { headers }
            )
            // Update local state with reset values
            console.log('[resetAssumptions] Received response.data:', response.data)
            console.log('[resetAssumptions] currency_conversion_rate:', response.data.currency_conversion_rate)
            console.log('[resetAssumptions] adr_conversion_factor:', response.data.adr_conversion_factor)
            setAssumptions({
                revenue_growth_stage1: response.data.revenue_growth_stage1 ?? 0.05,
                revenue_growth_stage2: response.data.revenue_growth_stage2 ?? 0.04,
                revenue_growth_terminal: response.data.revenue_growth_terminal ?? 0.03,
                ebita_margin_stage1: response.data.ebita_margin_stage1 ?? 0.20,
                ebita_margin_stage2: response.data.ebita_margin_stage2 ?? 0.20,
                ebita_margin_terminal: response.data.ebita_margin_terminal ?? 0.20,
                marginal_capital_turnover_stage1: response.data.marginal_capital_turnover_stage1 ?? 1.0,
                marginal_capital_turnover_stage2: response.data.marginal_capital_turnover_stage2 ?? 1.0,
                marginal_capital_turnover_terminal: response.data.marginal_capital_turnover_terminal ?? 1.0,
                beta: response.data.beta ?? 1.0,
                adjusted_tax_rate: response.data.adjusted_tax_rate ?? 0.25,
                wacc: boundWacc(response.data.wacc),
                diluted_shares_outstanding: response.data.diluted_shares_outstanding ?? null,
                base_revenue: response.data.base_revenue ?? null,
                weight_of_equity: response.data.weight_of_equity ?? 1.0,
                cost_of_debt: response.data.cost_of_debt ?? 0.05,
                calculated_wacc: response.data.calculated_wacc ?? 0.09,
                market_cap: response.data.market_cap ?? 0,
                currency_conversion_rate: response.data.currency_conversion_rate ?? 1.0,
                adr_conversion_factor: response.data.adr_conversion_factor ?? 1.0
            })
            // Reload model with new defaults
            loadModel()
        } catch (err) {
            setError("Failed to reset assumptions")
            console.error(err)
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
        const num = parseFloat(value)
        if (isNaN(num)) return 'N/A'
        return num.toFixed(2)
    }

    if (!assumptions) return <div>Loading assumptions...</div>

    return (
        <div className="financial-model">
            {/* Assumptions Title outside the card */}
            <h3 style={{ marginBottom: '1rem', marginTop: 0 }}>Assumptions</h3>

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
                                decimalPlaces={2}
                            />
                        </label>
                        <label>
                            Stage 2 (Y6-10):
                            <FormattedInput
                                value={assumptions.marginal_capital_turnover_stage2}
                                onChange={(val) => handleAssumptionChange('marginal_capital_turnover_stage2', val)}
                                isPercentage={false}
                                decimalPlaces={2}
                            />
                        </label>
                        <label>
                            Terminal:
                            <FormattedInput
                                value={assumptions.marginal_capital_turnover_terminal}
                                onChange={(val) => handleAssumptionChange('marginal_capital_turnover_terminal', val)}
                                isPercentage={false}
                                decimalPlaces={2}
                            />
                        </label>
                    </div>

                    <div className="assumption-divider"></div>

                    {/* WACC - Column 1 */}
                    <div className="assumption-group">
                        <h5>WACC</h5>
                        <label>
                            Beta:
                            <input
                                type="text"
                                value={typeof assumptions.beta === 'number' ? assumptions.beta.toFixed(2) : (Number(assumptions.beta) || 1.0).toFixed(2)}
                                disabled
                                style={{ backgroundColor: 'var(--bg-base)', cursor: 'not-allowed' }}
                                title="Beta pulled from Yahoo Finance"
                            />
                        </label>
                        <label>
                            <span>Cost of Equity: <ToolTip text="Calculated using CAPM: 4.2% risk-free rate + Beta × 5.0% market risk premium" /></span>
                            <input
                                type="text"
                                value={formatPercent(0.042 + (Number(assumptions.beta) || 1.0) * 0.05)}
                                disabled
                                style={{ backgroundColor: 'var(--bg-base)', cursor: 'not-allowed' }}
                            />
                        </label>
                        <label>
                            <span>Weight of Equity <ToolTip text={`Market Cap / (Market Cap + Debt). Market Cap: ${formatNumber(assumptions.market_cap / (unit === 'millions' ? 1000000 : unit === 'billions' ? 1000000000 : unit === 'thousands' ? 1000 : 1))} ${unit || ''}`} />:</span>
                            <input
                                type="text"
                                value={formatPercent(assumptions.weight_of_equity)}
                                disabled
                                style={{ backgroundColor: 'var(--bg-base)', cursor: 'not-allowed' }}
                            />
                        </label>
                    </div>

                    {/* WACC - Column 2 */}
                    <div className="assumption-group">
                        <h5>&nbsp;</h5>
                        <label>
                            <span>Cost of Debt: <ToolTip text="Annualized interest expense / total debt. Minimum 5.0%." /></span>
                            <input
                                type="text"
                                value={formatPercent(assumptions.cost_of_debt)}
                                disabled
                                style={{ backgroundColor: 'var(--bg-base)', cursor: 'not-allowed' }}
                            />
                        </label>
                        <label>
                            <span>Calculated WACC: <ToolTip text="(Cost of Equity × Weight of Equity) + (Cost of Debt × (1 - 25% Tax) × (1 - Weight of Equity))" /></span>
                            <input
                                type="text"
                                value={formatPercent(assumptions.calculated_wacc)}
                                disabled
                                style={{ backgroundColor: 'var(--bg-base)', cursor: 'not-allowed' }}
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
                            Diluted Shares Outstanding:
                            <FormattedInput
                                value={assumptions.diluted_shares_outstanding}
                                onChange={(val) => handleAssumptionChange('diluted_shares_outstanding', val)}
                                isPercentage={false}
                                decimalPlaces={3}
                                useSeparators={true}
                            />
                        </label>
                        <label>
                            Base Revenue:
                            <FormattedInput
                                value={assumptions.base_revenue}
                                onChange={(val) => handleAssumptionChange('base_revenue', val)}
                                isPercentage={false}
                                decimalPlaces={0}
                                useSeparators={true}
                            />
                        </label>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                    <button onClick={saveAssumptions} className="button-primary" disabled={loading}>
                        Re-run Valuation
                    </button>
                    <button
                        onClick={resetAssumptions}
                        className="button-secondary"
                        disabled={loading}
                    >
                        Reset Assumptions
                    </button>
                    <button
                        onClick={handleSaveValuation}
                        className="button-secondary"
                        disabled={loading}
                    >
                        Save Valuation
                    </button>
                </div>
            </div>

            {loading && <p>Calculating model...</p>}
            {error && <p className="error-text">{error}</p>}

            {modelData && modelData.projections && (
                <div className="model-results">
                    <h3>Discounted Cash Flow Model</h3>
                    <div className="financial-table-container">
                        <table className="financial-table company-analysis-table">
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

                    <div className="valuation-section" style={{ marginTop: '2rem', display: 'flex', gap: '2rem', alignItems: 'flex-start' }}>
                        <div style={{ flex: 1 }}>
                            <h3 style={{ margin: 0, marginBottom: '1rem' }}>Intrinsic Value</h3>
                            <div className="financial-table-container">
                                <table className="financial-table" style={{ width: '100%' }}>
                                    <tbody>
                                        <tr className="key-total-row">
                                            <td>Enterprise Value</td>
                                            <td className="text-right">{formatNumber(modelData.enterprise_value)}</td>
                                        </tr>
                                        {/* Bridge Items */}
                                        <tr>
                                            <td> + Cash</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.cash)}</td>
                                        </tr>
                                        <tr>
                                            <td> + Short Term Investments</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.short_term_investments)}</td>
                                        </tr>
                                        <tr>
                                            <td> + Other Financial or Physical Assets</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.other_financial_physical_assets)}</td>
                                        </tr>
                                        <tr>
                                            <td> - Debt</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.debt)}</td>
                                        </tr>
                                        <tr>
                                            <td> - Other Financial Liabilities</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.other_financial_liabilities)}</td>
                                        </tr>
                                        <tr>
                                            <td> - Preferred Equity</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.preferred_equity)}</td>
                                        </tr>
                                        <tr>
                                            <td> - Minority Interest</td>
                                            <td className="text-right">{formatNumber(modelData.bridge_items?.minority_interest)}</td>
                                        </tr>

                                        <tr className="key-total-row">
                                            <td>Value of Common Equity</td>
                                            <td className="text-right">{formatNumber(modelData.equity_value)}</td>
                                        </tr>
                                        <tr>
                                            <td>Diluted Shares Outstanding</td>
                                            <td className="text-right">{formatNumber(modelData.diluted_shares_outstanding)}</td>
                                        </tr>
                                        <tr className="key-total-row">
                                            <td>{currency && currency !== 'USD' ? `Fair Value per Share (${currency})` : "Fair Value per Share"}</td>
                                            <td className="text-right">{formatDecimal(modelData.fair_value_per_share)}</td>
                                        </tr>

                                        {currency && currency !== 'USD' && (
                                            <>
                                                <tr>
                                                    <td>Currency Conversion (USD/{currency})</td>
                                                    <td className="text-right">
                                                        {assumptions.currency_conversion_rate ? Number(assumptions.currency_conversion_rate).toFixed(4) : 'N/A'}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td>Fair Value per Share (USD)</td>
                                                    <td className="text-right">
                                                        {formatDecimal(modelData.fair_value_per_share * (assumptions.currency_conversion_rate || 1))}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td>ADR Conversion Factor (Shares per ADR)</td>
                                                    <td className="text-right" style={{ padding: '0.75rem 1.5rem' }}>
                                                        <FormattedInput
                                                            value={assumptions.adr_conversion_factor}
                                                            onChange={(val) => handleAssumptionChange('adr_conversion_factor', val)}
                                                            isPercentage={false}
                                                            decimalPlaces={2}
                                                            style={{
                                                                width: '100px',
                                                                padding: '0.25rem 0.5rem',
                                                                border: '1px solid var(--border)',
                                                                borderRadius: '4px',
                                                                backgroundColor: 'var(--bg-primary)',
                                                                color: 'var(--text-primary)',
                                                                textAlign: 'right',
                                                                fontSize: '0.9rem'
                                                            }}
                                                        />
                                                    </td>
                                                </tr>
                                                <tr className="key-total-row">
                                                    <td>Fair Value per ADR (USD)</td>
                                                    <td className="text-right">
                                                        {formatDecimal(modelData.fair_value_per_share * (assumptions.currency_conversion_rate || 1) * (assumptions.adr_conversion_factor || 1))}
                                                    </td>
                                                </tr>
                                            </>
                                        )}

                                        {modelData.current_share_price && parseFloat(modelData.current_share_price) > 0 && (
                                            <>
                                                <tr>
                                                    <td>Current Share Price ({selectedCompany.ticker})</td>
                                                    <td className="text-right">{formatDecimal(parseFloat(modelData.current_share_price))}</td>
                                                </tr>
                                                <tr className="key-total-row">
                                                    <td>Percent Undervalued (or Overvalued)</td>
                                                    <td className={`text-right ${modelData.percent_undervalued > 0 ? 'text-green' : 'text-red'}`}>
                                                        {formatPercent(modelData.percent_undervalued)}
                                                    </td>
                                                </tr>
                                            </>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                            <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                                {/* Move Reset button here or keep above? The "Save Valuation" button was requested Next to "Reset Assumptions" */}
                            </div>
                        </div>

                        {/* Past Valuations Table */}
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0 }}>Past Valuations</h3>
                            </div>
                            <div className="financial-table-container">
                                <table className="financial-table">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Created By</th>
                                            <th className="text-right">Fair Value</th>
                                            <th className="text-right">Share Price</th>
                                            <th className="text-right">% Diff</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {valuations.length === 0 ? (
                                            <tr>
                                                <td colSpan="6" style={{ textAlign: 'center', color: '#888' }}>
                                                    No saved valuations
                                                </td>
                                            </tr>
                                        ) : (
                                            valuations.map(v => (
                                                <tr key={v.id}>
                                                    <td>{new Date(v.date).toLocaleDateString()}</td>
                                                    <td>{v.user_name || v.user_email || 'Unknown'}</td>
                                                    <td className="text-right">${formatDecimal(parseFloat(v.fair_value))}</td>
                                                    <td className="text-right">{v.share_price_at_time ? `$${formatDecimal(parseFloat(v.share_price_at_time))}` : 'N/A'}</td>
                                                    <td className={`text-right ${parseFloat(v.percent_undervalued) > 0 ? 'text-green' : 'text-red'}`}>
                                                        {v.percent_undervalued ? formatPercent(parseFloat(v.percent_undervalued)) : 'N/A'}
                                                    </td>
                                                    <td className="text-right">
                                                        <button
                                                            onClick={() => handleDeleteValuation(v.id)}
                                                            className="delete-valuation-btn"
                                                            title="Delete"
                                                        >
                                                            <svg
                                                                viewBox="0 0 24 24"
                                                                fill="none"
                                                                stroke="currentColor"
                                                                strokeWidth="1.5"
                                                                strokeLinecap="round"
                                                                strokeLinejoin="round"
                                                            >
                                                                <path d="M3 6h18"></path>
                                                                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                                                                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                                                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                                                <line x1="14" y1="11" x2="14" y2="17"></line>
                                                            </svg>
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default FinancialModel
