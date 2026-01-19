import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { API_BASE_URL } from '../../../config'
import FinancialModel from './FinancialModel'
import './Company.css'

function CompanyAnalysisView({ selectedCompany }) {
    const { isAuthenticated, token } = useAuth()
    const [companyHistoricalCalculations, setCompanyHistoricalCalculations] = useState(null)
    const [companyHistoricalError, setCompanyHistoricalError] = useState(null)
    const [companyHistoricalLoading, setCompanyHistoricalLoading] = useState(false)

    useEffect(() => {
        const loadCompanyHistoricalCalculations = async () => {
            if (!selectedCompany?.id) return

            setCompanyHistoricalLoading(true)
            setCompanyHistoricalError(null)

            try {
                const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
                const response = await axios.get(
                    `${API_BASE_URL}/companies/${selectedCompany.id}/historical-calculations`,
                    { headers }
                )
                setCompanyHistoricalCalculations(response.data)
            } catch (err) {
                console.error('Error loading company historical calculations:', err)
                setCompanyHistoricalError('Failed to load historical calculations')
            } finally {
                setCompanyHistoricalLoading(false)
            }
        }

        loadCompanyHistoricalCalculations()
    }, [selectedCompany?.id, isAuthenticated, token])

    const formatNumber = (value, unit) => {
        if (value === null || value === undefined) return 'N/A'
        const num = parseFloat(value)
        if (isNaN(num)) return 'N/A'
        return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
    }

    const formatPercent = (value, multiplier = 1) => {
        if (value === null || value === undefined) return 'N/A'
        const num = parseFloat(value) * multiplier
        if (isNaN(num)) return 'N/A'
        return `${num.toFixed(1)}%`
    }

    const formatDecimal = (value, decimals = 2) => {
        if (value === null || value === undefined) return 'N/A'
        const num = parseFloat(value)
        if (isNaN(num)) return 'N/A'
        return num.toFixed(decimals)
    }

    const formatRoic = (val) => {
        if (val === null || val === undefined) return 'N/A'
        if (val < 0) return 'negative'
        if (val > 1) return '>100%'
        return formatPercent(val, 100)
    }

    const hasCompanyData = companyHistoricalCalculations?.entries && companyHistoricalCalculations.entries.length > 0
    const companyEntries = (companyHistoricalCalculations?.entries || []).filter(e => e.time_period?.includes('Q'))
    const timePeriods = companyEntries.map(e => e.time_period)

    const calculateStats = (accessor) => {
        const values = companyEntries.map(accessor).map(v => parseFloat(v)).filter(v => v !== null && v !== undefined && !isNaN(v))
        if (values.length === 0) return { average: null, median: null }

        // Average based on last 4 valid entries (L4Q)
        const last4Values = values.slice(-4)
        const average = last4Values.reduce((a, b) => a + b, 0) / last4Values.length

        const sorted = [...values].sort((a, b) => a - b)
        const median = sorted.length % 2 === 0
            ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
            : sorted[Math.floor(sorted.length / 2)]

        return { average, median }
    }

    const rows = [
        {
            label: 'Revenue',
            render: (entry) => formatNumber(entry.revenue, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.revenue),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'Simple Revenue Growth',
            render: (entry) => formatPercent(entry.simple_revenue_growth, 1),
            stats: calculateStats(e => e.simple_revenue_growth),
            formatStats: (val) => formatPercent(val, 1)
        },
        {
            label: 'Organic Growth',
            render: (entry) => formatPercent(entry.organic_revenue_growth, 1),
            stats: calculateStats(e => e.organic_revenue_growth),
            formatStats: (val) => formatPercent(val, 1)
        },
        {
            label: 'EBITA',
            render: (entry) => formatNumber(entry.ebita, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.ebita),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'EBITA Margin',
            render: (entry) => formatPercent(entry.ebita_margin, 100),
            stats: calculateStats(e => e.ebita_margin),
            formatStats: (val) => formatPercent(val, 100)
        },
        {
            label: 'Effective Tax Rate',
            render: (entry) => formatPercent(entry.effective_tax_rate, 100),
            stats: calculateStats(e => e.effective_tax_rate),
            formatStats: (val) => formatPercent(val, 100)
        },
        {
            label: 'Adjusted Tax Rate',
            render: (entry) => formatPercent(entry.adjusted_tax_rate, 100),
            stats: calculateStats(e => e.adjusted_tax_rate),
            formatStats: (val) => formatPercent(val, 100)
        },
        {
            label: 'NOPAT',
            render: (entry) => formatNumber(entry.nopat, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.nopat),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'Net Working Capital',
            render: (entry) => formatNumber(entry.net_working_capital, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.net_working_capital),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'Net Long Term Operating Assets',
            render: (entry) => formatNumber(entry.net_long_term_operating_assets, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.net_long_term_operating_assets),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'Invested Capital',
            render: (entry) => formatNumber(entry.invested_capital, companyHistoricalCalculations?.unit),
            stats: calculateStats(e => e.invested_capital),
            formatStats: (val) => formatNumber(val, companyHistoricalCalculations?.unit)
        },
        {
            label: 'Capital Turnover, Annualized',
            render: (entry) => formatDecimal(entry.capital_turnover, 4),
            stats: calculateStats(e => e.capital_turnover),
            formatStats: (val) => formatDecimal(val, 4)
        },
        {
            label: 'ROIC, Annualized',
            render: (entry) => formatRoic(entry.roic),
            stats: calculateStats(e => e.roic),
            formatStats: (val) => formatRoic(val)
        },
        {
            label: 'Diluted Shares Outstanding',
            render: (entry) => {
                const val = entry.diluted_shares_outstanding || entry.basic_shares_outstanding;
                if (!val) return 'N/A';
                return Number(val).toLocaleString();
            },
            stats: calculateStats(e => e.diluted_shares_outstanding || e.basic_shares_outstanding),
            formatStats: (val) => val ? Number(val).toLocaleString() : 'N/A'
        }
    ]

    if (!selectedCompany) {
        return (
            <div className="right-panel">
                <div className="panel-content">
                    <p className="placeholder-text">
                        Select a company to view financial analysis
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div className="right-panel">
            <div className="panel-content">
                <div className="panel-header">
                    <h2 style={{ fontSize: '0.9rem', fontWeight: 500, margin: 0 }}>
                        {selectedCompany.name} Financial Analysis
                    </h2>
                </div>
                <div className="company-analysis">
                    {companyHistoricalLoading && (
                        <p className="placeholder-text">Loading historical calculations...</p>
                    )}
                    {companyHistoricalError && (
                        <p className="placeholder-text">{companyHistoricalError}</p>
                    )}
                    {!companyHistoricalLoading && !companyHistoricalError && hasCompanyData && (
                        <>
                            <h3 style={{ marginTop: 0 }}>Historical Data</h3>
                            <div className="table-container">
                                <div className="table-header">
                                    <div className="table-meta">
                                        <span>
                                            <strong>Currency:</strong> {companyHistoricalCalculations?.currency || 'N/A'}
                                        </span>
                                        <span>
                                            <strong>Unit:</strong> {companyHistoricalCalculations?.unit || 'N/A'}
                                        </span>
                                        <span>
                                            <em>Units do not apply to percentages and ratios.</em>
                                        </span>
                                    </div>
                                </div>
                                <div className="financial-table-container">
                                    <table className="financial-table company-analysis-table">
                                        <thead>
                                            <tr>
                                                <th>Line Item</th>
                                                {timePeriods.map((period) => (
                                                    <th key={period} className="text-right">{period}</th>
                                                ))}
                                                <th className="text-right" style={{ borderLeft: '1px solid var(--border)' }}>L4Q Average</th>
                                                <th className="text-right">Median</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {rows.map((row) => (
                                                <tr key={row.label}>
                                                    <td>{row.label}</td>
                                                    {companyEntries.map((entry) => (
                                                        <td key={`${row.label}-${entry.time_period}`} className="text-right">
                                                            {row.render(entry)}
                                                        </td>
                                                    ))}
                                                    <td className="text-right" style={{ borderLeft: '1px solid var(--border)', fontWeight: 500 }}>
                                                        {row.formatStats(row.stats.average)}
                                                    </td>
                                                    <td className="text-right" style={{ fontWeight: 500 }}>
                                                        {row.formatStats(row.stats.median)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {/* Financial Modeling Section */}
                            <FinancialModel
                                selectedCompany={selectedCompany}
                                historicalEntries={companyEntries}
                                unit={companyHistoricalCalculations?.unit}
                                currency={companyHistoricalCalculations?.currency}
                            />
                        </>
                    )}
                    {!companyHistoricalLoading && !companyHistoricalError && !hasCompanyData && (
                        <p className="placeholder-text">
                            Company analysis will be displayed here once financial analysis is completed.
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}

export default CompanyAnalysisView
