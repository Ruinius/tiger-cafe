import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
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
    if (assumptions) {
        loadModel()
    }
  }, [assumptions, selectedCompany])
  // Warning: if loadModel depends on assumptions being saved in backend,
  // we need to make sure we save them first or pass them to the calc endpoint.
  // The backend endpoint reads from DB. So we must save to DB.

  const handleAssumptionChange = (key, value) => {
    setAssumptions(prev => ({
        ...prev,
        [key]: parseFloat(value)
    }))
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
    return `${(value * 100).toFixed(1)}%`
  }

  const formatDecimal = (value) => {
      if (value === null || value === undefined) return 'N/A'
      return value.toFixed(2)
  }

  if (!assumptions) return <div>Loading assumptions...</div>

  return (
    <div className="financial-model">
      <h3>Financial Modeling</h3>

      <div className="assumptions-section">
        <h4>Assumptions</h4>
        <div className="assumptions-grid">
            {/* Revenue Growth */}
            <div className="assumption-group">
                <h5>Revenue Growth</h5>
                <label>
                    Stage 1 (Y1-5):
                    <input
                        type="number" step="0.01"
                        value={assumptions.revenue_growth_stage1}
                        onChange={(e) => handleAssumptionChange('revenue_growth_stage1', e.target.value)}
                    />
                </label>
                <label>
                    Stage 2 (Y6-10):
                    <input
                        type="number" step="0.01"
                        value={assumptions.revenue_growth_stage2}
                        onChange={(e) => handleAssumptionChange('revenue_growth_stage2', e.target.value)}
                    />
                </label>
                <label>
                    Terminal:
                    <input
                        type="number" step="0.01"
                        value={assumptions.revenue_growth_terminal}
                        onChange={(e) => handleAssumptionChange('revenue_growth_terminal', e.target.value)}
                    />
                </label>
            </div>

            {/* EBITA Margin */}
            <div className="assumption-group">
                <h5>EBITA Margin</h5>
                <label>
                    Stage 1 (Y1-5):
                    <input
                        type="number" step="0.01"
                        value={assumptions.ebita_margin_stage1}
                        onChange={(e) => handleAssumptionChange('ebita_margin_stage1', e.target.value)}
                    />
                </label>
                <label>
                    Stage 2 (Y6-10):
                    <input
                        type="number" step="0.01"
                        value={assumptions.ebita_margin_stage2}
                        onChange={(e) => handleAssumptionChange('ebita_margin_stage2', e.target.value)}
                    />
                </label>
                <label>
                    Terminal:
                    <input
                        type="number" step="0.01"
                        value={assumptions.ebita_margin_terminal}
                        onChange={(e) => handleAssumptionChange('ebita_margin_terminal', e.target.value)}
                    />
                </label>
            </div>

            {/* Marginal Capital Turnover */}
            <div className="assumption-group">
                <h5>Marginal Capital Turnover</h5>
                <label>
                    Stage 1 (Y1-5):
                    <input
                        type="number" step="0.1"
                        value={assumptions.marginal_capital_turnover_stage1}
                        onChange={(e) => handleAssumptionChange('marginal_capital_turnover_stage1', e.target.value)}
                    />
                </label>
                <label>
                    Stage 2 (Y6-10):
                    <input
                        type="number" step="0.1"
                        value={assumptions.marginal_capital_turnover_stage2}
                        onChange={(e) => handleAssumptionChange('marginal_capital_turnover_stage2', e.target.value)}
                    />
                </label>
                <label>
                    Terminal:
                    <input
                        type="number" step="0.1"
                        value={assumptions.marginal_capital_turnover_terminal}
                        onChange={(e) => handleAssumptionChange('marginal_capital_turnover_terminal', e.target.value)}
                    />
                </label>
            </div>

            {/* Other */}
            <div className="assumption-group">
                <h5>Other</h5>
                <label>
                    Tax Rate:
                    <input
                        type="number" step="0.01"
                        value={assumptions.adjusted_tax_rate}
                        onChange={(e) => handleAssumptionChange('adjusted_tax_rate', e.target.value)}
                    />
                </label>
                <label>
                    WACC:
                    <input
                        type="number" step="0.01"
                        value={assumptions.wacc}
                        onChange={(e) => handleAssumptionChange('wacc', e.target.value)}
                    />
                </label>
            </div>
        </div>
        <button onClick={saveAssumptions} className="button-primary" style={{marginTop: '1rem'}}>
            Recalculate Model
        </button>
      </div>

      {loading && <p>Calculating model...</p>}
      {error && <p className="error-text">{error}</p>}

      {modelData && modelData.projections && (
          <div className="model-results">
              <h4>DCF Projections</h4>
              <div className="balance-sheet-table-container">
                <table className="balance-sheet-table">
                    <thead>
                        <tr>
                            <th>Year</th>
                            {modelData.projections.map(p => <th key={p.year} className="text-right">{p.year}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Revenue</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.revenue)}</td>)}
                        </tr>
                        <tr>
                            <td>Growth</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatPercent(p.growth_rate)}</td>)}
                        </tr>
                        <tr>
                            <td>EBITA</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.ebita)}</td>)}
                        </tr>
                        <tr>
                            <td>NOPAT</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.nopat)}</td>)}
                        </tr>
                        <tr>
                            <td>Invested Capital</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.invested_capital)}</td>)}
                        </tr>
                        <tr>
                            <td>ROIC</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatPercent(p.roic)}</td>)}
                        </tr>
                        <tr>
                            <td>FCF</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.fcf)}</td>)}
                        </tr>
                        <tr>
                            <td>Discount Factor</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatDecimal(p.discount_factor)}</td>)}
                        </tr>
                        <tr>
                            <td>PV of FCF</td>
                            {modelData.projections.map(p => <td key={p.year} className="text-right">{formatNumber(p.pv_fcf)}</td>)}
                        </tr>
                    </tbody>
                </table>
              </div>

              <div className="valuation-summary" style={{marginTop: '2rem'}}>
                  <h4>Valuation</h4>
                  <div className="balance-sheet-table-container">
                    <table className="balance-sheet-table" style={{maxWidth: '400px'}}>
                        <tbody>
                            <tr>
                                <td>PV of FCF (10y)</td>
                                <td className="text-right">{formatNumber(modelData.projections.reduce((sum, p) => sum + p.pv_fcf, 0))}</td>
                            </tr>
                            <tr>
                                <td>Terminal Value</td>
                                <td className="text-right">{formatNumber(modelData.terminal_value)}</td>
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
