import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { useAnalysisEvents } from '../../../hooks/useAnalysisEvents'
import { API_BASE_URL } from '../../../config'
import LineItemTable from '../../shared/tables/LineItemTable'
import OrganicGrowthTable from '../../shared/tables/OrganicGrowthTable'
import StandardizedBreakdownTable from '../../shared/tables/StandardizedBreakdownTable'
import SharesOutstandingTable from '../../shared/tables/SharesOutstandingTable'
import { formatNumber, formatPercent, formatDecimal } from '../../../utils/formatting'

function DocumentExtractionView({ selectedDocument }) {
    const { isAuthenticated, token } = useAuth()

    // State
    const [balanceSheet, setBalanceSheet] = useState(null)
    const [incomeStatement, setIncomeStatement] = useState(null)
    const [organicGrowth, setOrganicGrowth] = useState(null)
    const [amortization, setAmortization] = useState(null)
    const [otherAssets, setOtherAssets] = useState(null)
    const [otherLiabilities, setOtherLiabilities] = useState(null)
    const [nonOperatingClassification, setNonOperatingClassification] = useState(null)
    const [historicalCalculations, setHistoricalCalculations] = useState(null)
    const [financialStatementProgress, setFinancialStatementProgress] = useState(null)
    const [error, setError] = useState(null)

    // Loading states & Refs
    const [additionalItemsLoadAttempted, setAdditionalItemsLoadAttempted] = useState(false)
    const [historicalCalculationsLoadAttempted, setHistoricalCalculationsLoadAttempted] = useState(false)
    const [balanceSheetLoadAttempts, setBalanceSheetLoadAttempts] = useState(0)
    const [incomeStatementLoadAttempts, setIncomeStatementLoadAttempts] = useState(0)

    const progressPollingIntervalRef = useRef(null)
    const balanceSheetLoadingRef = useRef(false)
    const incomeStatementLoadingRef = useRef(false)
    const balanceSheetAttemptsRef = useRef(0)
    const incomeStatementAttemptsRef = useRef(0)
    const MAX_LOAD_ATTEMPTS = 3

    const isEligibleForFinancialStatements = selectedDocument &&
        ['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)

    // Helper: Check if all milestones are terminal
    const areAllMilestonesTerminal = useCallback(() => {
        if (!financialStatementProgress) return false
        if (financialStatementProgress.status === 'not_started') return false
        if (!financialStatementProgress.milestones) return false
        const allMilestones = Object.values(financialStatementProgress.milestones)
        if (allMilestones.length === 0) return false

        return allMilestones.every((milestone) =>
            milestone.status === 'completed' || milestone.status === 'error' || milestone.status === 'not_found'
        )
    }, [financialStatementProgress])

    // Loaders
    const loadFinancialStatementProgress = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        try {
            const endpoint = isAuthenticated ? 'financial-statement-progress' : 'financial-statement-progress-test'
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                { headers }
            )
            setFinancialStatementProgress(response.data)
        } catch (err) {
            setFinancialStatementProgress(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, isAuthenticated, token])

    const loadBalanceSheet = useCallback(async () => {
        if (!selectedDocument?.id) return
        if (balanceSheetLoadingRef.current) return
        if (balanceSheetAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return

        balanceSheetLoadingRef.current = true
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/balance-sheet`,
                { headers }
            )
            if (response.data && response.data.status === 'exists') {
                setBalanceSheet(response.data.data)
                balanceSheetAttemptsRef.current = 0
                setBalanceSheetLoadAttempts(0)
            } else {
                setBalanceSheet(null)
                balanceSheetAttemptsRef.current += 1
                setBalanceSheetLoadAttempts(prev => prev + 1)
            }
        } catch (err) {
            setBalanceSheet(null)
            balanceSheetAttemptsRef.current += 1
            setBalanceSheetLoadAttempts(prev => prev + 1)
        } finally {
            balanceSheetLoadingRef.current = false
        }
    }, [selectedDocument?.id, isAuthenticated, token])

    const loadIncomeStatement = useCallback(async () => {
        if (!selectedDocument?.id) return
        if (incomeStatementLoadingRef.current) return
        if (incomeStatementAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return

        incomeStatementLoadingRef.current = true
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/income-statement`,
                { headers }
            )
            if (response.data && response.data.status === 'exists') {
                setIncomeStatement(response.data.data)
                incomeStatementAttemptsRef.current = 0
                setIncomeStatementLoadAttempts(0)
            } else {
                setIncomeStatement(null)
                incomeStatementAttemptsRef.current += 1
                setIncomeStatementLoadAttempts(prev => prev + 1)
            }
        } catch (err) {
            setIncomeStatement(null)
            incomeStatementAttemptsRef.current += 1
            setIncomeStatementLoadAttempts(prev => prev + 1)
        } finally {
            incomeStatementLoadingRef.current = false
        }
    }, [selectedDocument?.id, isAuthenticated, token])

    const loadAdditionalItems = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const isEarningsAnnouncement = selectedDocument.document_type === 'earnings_announcement' ||
            selectedDocument.document_type === 'EARNINGS_ANNOUNCEMENT'

        const endpoints = {
            organicGrowth: 'organic-growth',
            amortization: 'amortization',
            ...(isEarningsAnnouncement ? {} : {
                otherAssets: 'other-assets',
                otherLiabilities: 'other-liabilities',
            }),
            nonOperatingClassification: 'non-operating-classification'
        }

        const results = await Promise.allSettled(
            Object.entries(endpoints).map(([key, endpoint]) =>
                axios.get(`${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`, { headers })
                    .then(response => ({ key, data: response.data?.data || null }))
            )
        )

        results.forEach(result => {
            if (result.status === 'fulfilled') {
                const { key, data } = result.value
                if (key === 'organicGrowth') setOrganicGrowth(data)
                if (key === 'amortization') setAmortization(data)
                if (key === 'otherAssets') setOtherAssets(data)
                if (key === 'otherLiabilities') setOtherLiabilities(data)
                if (key === 'nonOperatingClassification') setNonOperatingClassification(data)
            }
        })
    }, [selectedDocument?.id, selectedDocument?.document_type, isEligibleForFinancialStatements, isAuthenticated, token])

    const loadHistoricalCalculations = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        try {
            const endpoint = isAuthenticated ? 'historical-calculations' : 'historical-calculations/test'
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                { headers }
            )
            setHistoricalCalculations(response.data)
        } catch (err) {
            setHistoricalCalculations(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, isAuthenticated, token])

    // Event Listeners
    useAnalysisEvents({
        onProcessingComplete: () => {
            // Handled by polling effect mostly, but good for sync
        },
        onClearData: () => {
            setBalanceSheet(null)
            setIncomeStatement(null)
            setOrganicGrowth(null)
            setAmortization(null)
            setOtherAssets(null)
            setOtherLiabilities(null)
            setNonOperatingClassification(null)
            setAdditionalItemsLoadAttempted(false)
            setHistoricalCalculations(null)
            setHistoricalCalculationsLoadAttempted(false)
            setBalanceSheetLoadAttempts(0)
            setIncomeStatementLoadAttempts(0)
            balanceSheetLoadingRef.current = false
            incomeStatementLoadingRef.current = false
            balanceSheetAttemptsRef.current = 0
            incomeStatementAttemptsRef.current = 0
        },
        onReloadHistorical: () => {
            if (selectedDocument && isEligibleForFinancialStatements) {
                setHistoricalCalculations(null)
                setHistoricalCalculationsLoadAttempted(false)
                loadHistoricalCalculations()
                setHistoricalCalculationsLoadAttempted(true)
            }
        },
        onReloadProgress: () => {
            setTimeout(() => {
                loadFinancialStatementProgress()
            }, 500)
        },
        onResetProgress: (detail) => {
            if (detail?.documentId === selectedDocument?.id) {
                setFinancialStatementProgress({
                    status: 'processing',
                    milestones: {
                        balance_sheet: { status: 'pending', message: 'Waiting to start...' },
                        income_statement: { status: 'pending', message: 'Waiting to start...' },
                        extracting_additional_items: { status: 'pending', message: 'Waiting to start...' },
                        classifying_non_operating_items: { status: 'pending', message: 'Waiting to start...' }
                    }
                })
                setTimeout(() => loadFinancialStatementProgress(), 1000)
            }
        }
    })

    // Initial Load
    useEffect(() => {
        // Reset state on document change
        setFinancialStatementProgress(null)
        setBalanceSheet(null)
        setIncomeStatement(null)
        setOrganicGrowth(null)
        setAmortization(null)
        setOtherAssets(null)
        setOtherLiabilities(null)
        setNonOperatingClassification(null)
        setAdditionalItemsLoadAttempted(false)
        setError(null)
        setBalanceSheetLoadAttempts(0)
        setIncomeStatementLoadAttempts(0)
        balanceSheetLoadingRef.current = false
        incomeStatementLoadingRef.current = false
        balanceSheetAttemptsRef.current = 0
        incomeStatementAttemptsRef.current = 0
        setHistoricalCalculations(null)
        setHistoricalCalculationsLoadAttempted(false)

        if (progressPollingIntervalRef.current) {
            clearInterval(progressPollingIntervalRef.current)
            progressPollingIntervalRef.current = null
        }

        if (selectedDocument?.id && isEligibleForFinancialStatements) {
            loadFinancialStatementProgress()
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

    // Polling
    useEffect(() => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return

        const hasActiveMilestones = financialStatementProgress &&
            financialStatementProgress.milestones &&
            Object.values(financialStatementProgress.milestones).some((milestone) =>
                milestone.status === 'in_progress' || milestone.status === 'pending'
            )

        if (hasActiveMilestones) {
            const interval = setInterval(() => {
                loadFinancialStatementProgress()
            }, 3000)
            progressPollingIntervalRef.current = interval
            return () => {
                clearInterval(interval)
                progressPollingIntervalRef.current = null
            }
        } else {
            if (progressPollingIntervalRef.current) {
                clearInterval(progressPollingIntervalRef.current)
                progressPollingIntervalRef.current = null
            }
        }
    }, [financialStatementProgress, selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

    // Data Loading when milestones complete
    useEffect(() => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        if (!areAllMilestonesTerminal()) return

        const bsStatus = financialStatementProgress?.milestones?.balance_sheet?.status
        if (balanceSheetAttemptsRef.current < MAX_LOAD_ATTEMPTS && !balanceSheet && !balanceSheetLoadingRef.current) {
            if (bsStatus === 'completed' || bsStatus === 'error') {
                loadBalanceSheet()
            }
        }

        const isStatus = financialStatementProgress?.milestones?.income_statement?.status
        if (incomeStatementAttemptsRef.current < MAX_LOAD_ATTEMPTS && !incomeStatement && !incomeStatementLoadingRef.current) {
            if (isStatus === 'completed' || isStatus === 'error') {
                loadIncomeStatement()
            }
        }

        if (!additionalItemsLoadAttempted) {
            loadAdditionalItems().then(() => setAdditionalItemsLoadAttempted(true))
        }
    }, [
        areAllMilestonesTerminal,
        selectedDocument?.id,
        balanceSheet,
        incomeStatement,
        additionalItemsLoadAttempted,
        loadBalanceSheet,
        loadIncomeStatement,
        loadAdditionalItems
    ])

    // Historical Calculations Loading
    useEffect(() => {
        if (!selectedDocument || !isEligibleForFinancialStatements) return
        if (areAllMilestonesTerminal() && balanceSheet && incomeStatement && !historicalCalculationsLoadAttempted) {
            setHistoricalCalculationsLoadAttempted(true)
            loadHistoricalCalculations()
        }
    }, [areAllMilestonesTerminal, selectedDocument, balanceSheet, incomeStatement, historicalCalculationsLoadAttempted, loadHistoricalCalculations])

    // Helpers
    const formatCategoryLabel = (category) => {
        if (!category) return 'N/A'
        return category.replace(/_/g, ' ').split(' ').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ')
    }

    if (!selectedDocument) return null

    const hasNoData = !balanceSheet && !incomeStatement
    const allAttemptsExhausted = balanceSheetLoadAttempts >= MAX_LOAD_ATTEMPTS && incomeStatementLoadAttempts >= MAX_LOAD_ATTEMPTS
    const showNothingMessage = hasNoData && (allAttemptsExhausted || areAllMilestonesTerminal())

    return (
        <div className="right-panel">
            <div className="panel-content">
                <h2>Document Analysis</h2>

                {!isEligibleForFinancialStatements && (
                    <div className="info-section">
                        <p className="info-text">This document type is not yet implemented.</p>
                    </div>
                )}

                {isEligibleForFinancialStatements && (
                    <>
                        {/* Progress Tracker */}
                        {financialStatementProgress && (
                            <div className="info-section" style={{ marginBottom: '2rem', padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px' }}>
                                <h4 style={{ marginTop: 0, marginBottom: '1rem' }}>Processing Tracker</h4>
                                <div className="progress-milestones">
                                    {[
                                        { key: 'balance_sheet', label: 'Balance Sheet' },
                                        { key: 'income_statement', label: 'Income Statement' },
                                        { key: 'extracting_additional_items', label: 'Extracting Additional Items' },
                                        { key: 'classifying_non_operating_items', label: 'Classifying Non-Operating Items' }
                                    ].map((milestone) => {
                                        const milestoneData = financialStatementProgress.milestones?.[milestone.key]
                                        const status = milestoneData?.status || 'checking'
                                        const message = milestoneData?.message

                                        return (
                                            <div key={milestone.key} className="progress-milestone-item" style={{ marginBottom: '0.75rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <span style={{
                                                        color: status === 'completed' ? 'var(--success)' :
                                                            status === 'error' ? 'var(--error)' :
                                                                status === 'in_progress' ? 'var(--accent)' : 'var(--text-secondary)'
                                                    }}>
                                                        {status === 'completed' ? '✓' : status === 'error' ? '✗' : '○'}
                                                    </span>
                                                    <span>{milestone.label}: {status}</span>
                                                </div>
                                                {message && (
                                                    <div style={{
                                                        marginLeft: '1.5rem',
                                                        fontSize: '0.875rem',
                                                        color: 'var(--text-secondary)',
                                                        marginTop: '0.25rem'
                                                    }}>
                                                        {message}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}

                        {showNothingMessage && <p className="placeholder-text">Nothing to see here.</p>}

                        {/* Extractions */}
                        {balanceSheet && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Balance Sheet</h3>
                                <LineItemTable
                                    data={balanceSheet}
                                    formatNumber={formatNumber}
                                    balanceSheet={balanceSheet}
                                    categoryFormatter={formatCategoryLabel}
                                />
                            </div>
                        )}

                        {incomeStatement && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Income Statement</h3>
                                <LineItemTable
                                    data={incomeStatement}
                                    formatNumber={formatNumber}
                                    incomeStatement={incomeStatement}
                                    categoryFormatter={formatCategoryLabel}
                                />
                            </div>
                        )}

                        {/* Additional Tables */}
                        {organicGrowth && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Organic Revenue Growth</h3>
                                <OrganicGrowthTable
                                    data={organicGrowth}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}

                        {amortization && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Amortization of Intangibles</h3>
                                <LineItemTable
                                    data={amortization}
                                    formatNumber={formatNumber}
                                    showCategory={false}
                                />
                            </div>
                        )}

                        {otherAssets && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Other Assets Breakdown</h3>
                                <StandardizedBreakdownTable
                                    data={otherAssets}
                                    formatNumber={formatNumber}
                                    balanceSheet={balanceSheet}
                                    standardReferences={[
                                        { id: 1, label: 'Other Current Assets', category: 'Current Assets' },
                                        { id: 2, label: 'Other Non-Current Assets', category: 'Non-Current Assets' }
                                    ]}
                                />
                            </div>
                        )}

                        {otherLiabilities && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Other Liabilities Breakdown</h3>
                                <StandardizedBreakdownTable
                                    data={otherLiabilities}
                                    formatNumber={formatNumber}
                                    balanceSheet={balanceSheet}
                                    standardReferences={[
                                        { id: 1, label: 'Other Current Liabilities', category: 'Current Liabilities' },
                                        { id: 2, label: 'Other Non-Current Liabilities', category: 'Non-Current Liabilities' }
                                    ]}
                                />
                            </div>
                        )}

                        {incomeStatement && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Shares Outstanding</h3>
                                <SharesOutstandingTable
                                    incomeStatement={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}

                        {nonOperatingClassification && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h3>Non-Operating Items Classification</h3>
                                <LineItemTable
                                    data={nonOperatingClassification}
                                    formatNumber={formatNumber}
                                    categoryFormatter={formatCategoryLabel}
                                    typeOverride={<span className="type-badge non-operating">Non-Operating</span>}
                                />
                            </div>
                        )}

                        {historicalCalculations && historicalCalculations.entries && historicalCalculations.entries.length > 0 && (() => {
                            const entry = historicalCalculations.entries[0] || {}
                            const unit = historicalCalculations.unit || 'USD'
                            const currency = historicalCalculations.currency || 'USD'

                            return (
                                <>
                                    <div style={{ marginBottom: '2rem' }}>
                                        <h3>Historical Calculations</h3>
                                        <div className="section-intro">
                                            Calculated metrics based on extracted financial statements.
                                        </div>
                                    </div>

                                    {/* 1. Invested Capital Analysis */}
                                    {entry.net_working_capital_breakdown && (
                                        <div style={{ marginBottom: '2rem' }}>
                                            <h4>1. Invested Capital Analysis</h4>

                                            {/* Net Working Capital */}
                                            <div style={{ marginBottom: '1.5rem', paddingLeft: '1rem' }}>
                                                <h5>Net Working Capital</h5>
                                                <div className="balance-sheet-table-container">
                                                    <table className="balance-sheet-table extraction-table">
                                                        <thead>
                                                            <tr>
                                                                <th>Line Item</th>
                                                                <th>Category</th>
                                                                <th className="text-right">Amount</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {entry.net_working_capital_breakdown.current_assets?.map((item, idx) => (
                                                                <tr key={`ca-${idx}`}>
                                                                    <td>{item.line_name}</td>
                                                                    <td>Current Assets</td>
                                                                    <td className="text-right">{formatNumber(item.line_value, unit)}</td>
                                                                </tr>
                                                            ))}
                                                            <tr className="subtotal-row">
                                                                <td><strong>Total Operating Current Assets</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>{formatNumber(entry.net_working_capital_breakdown.current_assets_total, unit)}</strong></td>
                                                            </tr>
                                                            {entry.net_working_capital_breakdown.current_liabilities?.map((item, idx) => (
                                                                <tr key={`cl-${idx}`}>
                                                                    <td>{item.line_name}</td>
                                                                    <td>Current Liabilities</td>
                                                                    <td className="text-right">({formatNumber(item.line_value, unit)})</td>
                                                                </tr>
                                                            ))}
                                                            <tr className="subtotal-row">
                                                                <td><strong>Total Operating Current Liabilities</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>({formatNumber(entry.net_working_capital_breakdown.current_liabilities_total, unit)})</strong></td>
                                                            </tr>
                                                            <tr className="total-row">
                                                                <td><strong>Net Working Capital</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>{formatNumber(entry.net_working_capital, unit)}</strong></td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>

                                            {/* Net Long Term Operating Assets */}
                                            <div style={{ marginBottom: '1.5rem', paddingLeft: '1rem' }}>
                                                <h5>Net Long-Term Operating Assets</h5>
                                                <div className="balance-sheet-table-container">
                                                    <table className="balance-sheet-table extraction-table">
                                                        <thead>
                                                            <tr>
                                                                <th>Line Item</th>
                                                                <th>Category</th>
                                                                <th className="text-right">Amount</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {entry.net_long_term_operating_assets_breakdown?.non_current_assets?.map((item, idx) => (
                                                                <tr key={`nca-${idx}`}>
                                                                    <td>{item.line_name}</td>
                                                                    <td>Non-Current Assets</td>
                                                                    <td className="text-right">{formatNumber(item.line_value, unit)}</td>
                                                                </tr>
                                                            ))}
                                                            <tr className="subtotal-row">
                                                                <td><strong>Total Operating Non-Current Assets</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>{formatNumber(entry.net_long_term_operating_assets_breakdown?.non_current_assets_total, unit)}</strong></td>
                                                            </tr>
                                                            {entry.net_long_term_operating_assets_breakdown?.non_current_liabilities?.map((item, idx) => (
                                                                <tr key={`ncl-${idx}`}>
                                                                    <td>{item.line_name}</td>
                                                                    <td>Non-Current Liabilities</td>
                                                                    <td className="text-right">({formatNumber(item.line_value, unit)})</td>
                                                                </tr>
                                                            ))}
                                                            <tr className="subtotal-row">
                                                                <td><strong>Total Operating Non-Current Liabilities</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>({formatNumber(entry.net_long_term_operating_assets_breakdown?.non_current_liabilities_total, unit)})</strong></td>
                                                            </tr>
                                                            <tr className="total-row">
                                                                <td><strong>Net Long-Term Operating Assets</strong></td>
                                                                <td></td>
                                                                <td className="text-right"><strong>{formatNumber(entry.net_long_term_operating_assets, unit)}</strong></td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>

                                            {/* Total Invested Capital Summary */}
                                            <div style={{ paddingLeft: '1rem' }}>
                                                <div className="balance-sheet-table-container">
                                                    <table className="balance-sheet-table extraction-table">
                                                        <tbody>
                                                            <tr className="total-row">
                                                                <td><strong>Total Invested Capital</strong></td>
                                                                <td className="text-right"><strong>{formatNumber(entry.invested_capital, unit)}</strong></td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* 2. EBITA Analysis */}
                                    {entry.ebita_breakdown && (
                                        <div style={{ marginBottom: '2rem' }}>
                                            <h4>2. EBITA Analysis</h4>
                                            <div className="balance-sheet-table-container">
                                                <table className="balance-sheet-table extraction-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Line Item</th>
                                                            <th>Type</th>
                                                            <th className="text-right">Amount</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>Operating Income</td>
                                                            <td>GAAP</td>
                                                            <td className="text-right">{formatNumber(entry.ebita_breakdown.operating_income, unit)}</td>
                                                        </tr>
                                                        {entry.ebita_breakdown.adjustments?.map((adj, idx) => (
                                                            <tr key={`adj-${idx}`}>
                                                                <td>{adj.line_name || 'Adjustment'}</td>
                                                                <td>Non-Operating</td>
                                                                <td className="text-right">{formatNumber(adj.line_value, unit)}</td>
                                                            </tr>
                                                        ))}
                                                        <tr className="total-row">
                                                            <td><strong>EBITA</strong></td>
                                                            <td>Non-GAAP</td>
                                                            <td className="text-right"><strong>{formatNumber(entry.ebita, unit)}</strong></td>
                                                        </tr>
                                                        <tr>
                                                            <td>Revenue</td>
                                                            <td>GAAP</td>
                                                            <td className="text-right">{formatNumber(entry.revenue, unit)}</td>
                                                        </tr>
                                                        <tr className="subtotal-row">
                                                            <td><strong>EBITA Margin</strong></td>
                                                            <td>Calculated</td>
                                                            <td className="text-right"><strong>{formatPercent(entry.ebita_margin)}</strong></td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}

                                    {/* 3. Adjusted Tax Rate Analysis */}
                                    {entry.adjusted_tax_rate_breakdown && (
                                        <div style={{ marginBottom: '2rem' }}>
                                            <h4>3. Adjusted Tax Rate Analysis</h4>
                                            <div className="balance-sheet-table-container">
                                                <table className="balance-sheet-table extraction-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Line Item</th>
                                                            <th>Notes</th>
                                                            <th className="text-right">Amount</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>Reported Tax Expense</td>
                                                            <td>From Income Statement</td>
                                                            <td className="text-right">{formatNumber(entry.adjusted_tax_rate_breakdown.reported_tax_expense, unit)}</td>
                                                        </tr>
                                                        {entry.adjusted_tax_rate_breakdown.adjustments?.map((adj, idx) => (
                                                            <tr key={`tax-adj-${idx}`}>
                                                                <td>Tax Effect: {adj.line_name}</td>
                                                                <td>{adj.source} @ 25%</td>
                                                                <td className="text-right">{formatNumber(adj.tax_effect, unit)}</td>
                                                            </tr>
                                                        ))}
                                                        <tr className="total-row">
                                                            <td><strong>Adjusted Tax Expense</strong></td>
                                                            <td></td>
                                                            <td className="text-right"><strong>{formatNumber(entry.adjusted_tax_rate_breakdown.adjusted_tax_expense, unit)}</strong></td>
                                                        </tr>
                                                        <tr className="subtotal-row">
                                                            <td><strong>Adjusted Tax Rate</strong></td>
                                                            <td>(Adj Tax / EBITA)</td>
                                                            <td className="text-right"><strong>{formatPercent(entry.adjusted_tax_rate)}</strong></td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}

                                    {/* 4. NOPAT & ROIC */}
                                    <div style={{ marginBottom: '2rem' }}>
                                        <h4>4. NOPAT & ROIC Analysis</h4>
                                        <div className="balance-sheet-table-container">
                                            <table className="balance-sheet-table extraction-table">
                                                <thead>
                                                    <tr>
                                                        <th>Metric</th>
                                                        <th>Formula</th>
                                                        <th className="text-right">Value</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <tr>
                                                        <td>EBITA</td>
                                                        <td>From Analysis</td>
                                                        <td className="text-right">{formatNumber(entry.ebita, unit)}</td>
                                                    </tr>
                                                    <tr>
                                                        <td>Adjusted Tax Rate</td>
                                                        <td>From Analysis</td>
                                                        <td className="text-right">{formatPercent(entry.adjusted_tax_rate)}</td>
                                                    </tr>
                                                    <tr className="total-row">
                                                        <td><strong>NOPAT</strong></td>
                                                        <td>EBITA * (1 - Tax Rate)</td>
                                                        <td className="text-right"><strong>{formatNumber(entry.nopat, unit)}</strong></td>
                                                    </tr>
                                                    <tr>
                                                        <td>Invested Capital</td>
                                                        <td>From Analysis</td>
                                                        <td className="text-right">{formatNumber(entry.invested_capital, unit)}</td>
                                                    </tr>
                                                    <tr className="total-row">
                                                        <td><strong>ROIC</strong></td>
                                                        <td>NOPAT / Invested Capital</td>
                                                        <td className="text-right"><strong>{formatPercent(entry.roic)}</strong></td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>

                                    {/* 5. Summary Table */}
                                    <div style={{ marginBottom: '2rem' }}>
                                        <h4>5. Summary Table</h4>
                                        <div className="balance-sheet-table-container">
                                            <table className="balance-sheet-table extraction-table">
                                                <thead>
                                                    <tr>
                                                        <th>Line Item</th>
                                                        <th className="text-right">Amount</th>
                                                        <th>Category</th>
                                                        <th>Type</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {/* We can iterate over a standard list of keys or just use what's returned */}
                                                    {[
                                                        { label: 'Revenue', key: 'revenue' },
                                                        { label: 'YOY Revenue Growth', key: 'revenue_growth_yoy', isPercent: true },
                                                        { label: 'EBITA', key: 'ebita' },
                                                        { label: 'EBITA Margin', key: 'ebita_margin', isPercent: true },
                                                        { label: 'Effective Tax Rate', key: 'effective_tax_rate', isPercent: true },
                                                        { label: 'Adjusted Tax Rate', key: 'adjusted_tax_rate', isPercent: true },
                                                        { label: 'Net Working Capital', key: 'net_working_capital' },
                                                        { label: 'Net Long Term Operating Assets', key: 'net_long_term_operating_assets' },
                                                        { label: 'Invested Capital', key: 'invested_capital' },
                                                        { label: 'Capital Turnover (Annualized)', key: 'capital_turnover', isDecimal: true },
                                                        { label: 'NOPAT', key: 'nopat' },
                                                        { label: 'ROIC', key: 'roic', isPercent: true },
                                                        { label: 'YOY Marginal Capital Turnover', key: 'marginal_capital_turnover', isDecimal: true }
                                                    ].map(row => {
                                                        let value = entry[row.key]

                                                        let displayValue = 'N/A'
                                                        if (row.isPercent) {
                                                            displayValue = formatPercent(value, row.key === 'ebita_margin' || row.key === 'effective_tax_rate' || row.key === 'adjusted_tax_rate' ? 100 : 1)
                                                            if (row.key === 'roic') {
                                                                if (value < 0) displayValue = 'negative'
                                                                else if (value > 1) displayValue = '>100%'
                                                                else displayValue = formatPercent(value, 100)
                                                            }
                                                        } else if (row.isDecimal) {
                                                            displayValue = formatDecimal(value, 4)
                                                        } else {
                                                            displayValue = formatNumber(value, unit)
                                                        }

                                                        return (
                                                            <tr key={row.key}>
                                                                <td>{row.label}</td>
                                                                <td className="text-right">{displayValue}</td>
                                                                <td>Calculated</td>
                                                                <td></td>
                                                            </tr>
                                                        )
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </>
                            )
                        })()}
                    </>
                )}
            </div>
        </div>
    )
}

export default DocumentExtractionView
