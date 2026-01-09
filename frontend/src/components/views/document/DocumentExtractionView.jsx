import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'
import { useAnalysisEvents } from '../../../hooks/useAnalysisEvents'
import { API_BASE_URL } from '../../../config'




import { formatNumber, formatPercent, formatDecimal } from '../../../utils/formatting'
import './Document.css'

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
        ['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type?.toLowerCase())

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
            <div className="panel-content document-extraction-view">


                {!isEligibleForFinancialStatements && (
                    <div className="info-section">
                        <p className="info-text">This document type is not yet implemented.</p>
                    </div>
                )}

                {isEligibleForFinancialStatements && (
                    <>
                        {/* Progress Tracker */}
                        {financialStatementProgress && (
                            <div className="info-section">
                                <h3 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Processing Tracker</h3>
                                <div className="processing-tracker">
                                    {[
                                        { key: 'balance_sheet', label: 'Extracting & classifying balance sheet' },
                                        { key: 'income_statement', label: 'Extracting & classifying income statement' },
                                        { key: 'extracting_additional_items', label: 'Extracting additional items' },
                                        { key: 'classifying_non_operating_items', label: 'Classifying non-operating items' }
                                    ].map((milestone) => {
                                        const milestoneData = financialStatementProgress.milestones?.[milestone.key]
                                        const status = milestoneData?.status || 'checking'

                                        // If the global process appears complete (all terminals set), hide unstarted/checking items
                                        if (areAllMilestonesTerminal() && (!milestoneData || status === 'checking')) {
                                            return null
                                        }

                                        const message = milestoneData?.message

                                        return (
                                            <div key={milestone.key} className="processing-milestone-item">
                                                <div className="milestone-header">
                                                    <div className={`milestone-indicator ${status}`}>
                                                        {status === 'completed' ? '✓' :
                                                            status === 'error' ? '✗' :
                                                                status === 'in_progress' ? <span className="status-spinner"></span> :
                                                                    '○'}
                                                    </div>
                                                    <span className="milestone-label">{milestone.label}</span>
                                                    <span className={`status-badge ${status}`}>
                                                        {status.replace(/_/g, ' ')}
                                                    </span>
                                                </div>

                                                {/* Only show logs if NOT completed to avoid redundant text */}
                                                {status !== 'completed' && (
                                                    <>
                                                        {(milestoneData?.logs && milestoneData.logs.length > 0) ? (
                                                            <div className="milestone-logs">
                                                                {milestoneData.logs.map((log, idx) => (
                                                                    <div
                                                                        key={idx}
                                                                        className={`milestone-log-entry ${idx === milestoneData.logs.length - 1 ? 'latest' : ''}`}
                                                                    >
                                                                        <span className="log-timestamp">
                                                                            {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                                                        </span>
                                                                        <span className="log-message">{log.message}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        ) : message && (
                                                            <div className="milestone-logs">
                                                                <div className="milestone-log-entry">
                                                                    <span className="log-message">{message}</span>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </>
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
                                <h3>Non-GAAP Reconciliation</h3>
                                <LineItemTable
                                    data={amortization}
                                    formatNumber={formatNumber}
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

                        {/* Historical Calculations Section */}
                        {historicalCalculations && (
                            <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>




                                {/* Invested Capital Breakdown */}
                                {historicalCalculations.invested_capital != null && balanceSheet && (
                                    <div style={{ marginTop: '1.5rem' }}>
                                        <h3>Invested Capital</h3>
                                        <div className="balance-sheet-header" style={{ marginBottom: '1rem', marginTop: '0.5rem' }}>
                                            <div className="balance-sheet-meta">
                                                <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                                                <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                                                {(balanceSheet?.unit || incomeStatement?.unit) && (
                                                    <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                                                )}
                                            </div>
                                        </div>

                                        {(() => {
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
                                                <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                                    <div style={{ marginBottom: '0.5rem' }}>

                                                        <div className="balance-sheet-table-container">
                                                            <table className="balance-sheet-table">
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

                                                    <div style={{ marginBottom: '0.5rem' }}>

                                                        <div className="balance-sheet-table-container">
                                                            <table className="balance-sheet-table">
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
                                                                                    <span className="text-muted">ΓÇö</span>
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
                                                                                    <span className="text-muted">ΓÇö</span>
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

                                                    <div style={{ marginTop: '0.5rem', paddingTop: '0.25rem' }}>
                                                        <div className="balance-sheet-table-container">
                                                            <table className="balance-sheet-table">
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
                                            )
                                        })()}
                                    </div>
                                )}




                                {/* EBITA Breakdown */}
                                {historicalCalculations.ebita != null && incomeStatement && (
                                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                                        <h3>EBITA</h3>
                                        <div className="balance-sheet-header" style={{ marginBottom: '1rem', marginTop: '0.5rem' }}>
                                            <div className="balance-sheet-meta">
                                                <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                                                <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                                                {(balanceSheet?.unit || incomeStatement?.unit) && (
                                                    <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                                                )}
                                            </div>
                                        </div>

                                        {(() => {
                                            const breakdown = historicalCalculations.ebita_breakdown

                                            if (breakdown) {
                                                return (
                                                    <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                                        <div className="balance-sheet-table-container">
                                                            <table className="balance-sheet-table">
                                                                <thead>
                                                                    <tr>
                                                                        <th className="col-name">Line Item</th>
                                                                        <th className="col-category">Category</th>
                                                                        <th className="text-right col-value">Amount</th>
                                                                        <th className="col-type text-right">Type</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    <tr>
                                                                        <td className="col-name">Operating Income</td>
                                                                        <td className="col-category">Total</td>
                                                                        <td className="text-right col-value">{formatNumber(breakdown.operating_income, historicalCalculations.unit)}</td>
                                                                        <td className="col-type text-right">
                                                                            <span className="type-badge operating">Operating</span>
                                                                        </td>
                                                                    </tr>
                                                                    {breakdown.adjustments && breakdown.adjustments.length > 0 && (
                                                                        <>
                                                                            <tr>
                                                                                <td colSpan="4" style={{ fontWeight: 600, paddingTop: '0.5rem' }}>Non-GAAP Adjustments</td>
                                                                            </tr>
                                                                            {breakdown.adjustments.map((item, idx) => (
                                                                                <tr key={`adj-${idx}`}>
                                                                                    <td className="col-name">{item.line_name}</td>
                                                                                    <td className="col-category">{item.category || 'One-Time'}</td>
                                                                                    <td className="text-right col-value">{formatNumber(item.line_value, historicalCalculations.unit)}</td>
                                                                                    <td className="col-type text-right">
                                                                                        <span className="type-badge non-operating">Non-Operating</span>
                                                                                    </td>
                                                                                </tr>
                                                                            ))}
                                                                        </>
                                                                    )}
                                                                    <tr className="key-total-row">
                                                                        <td className="col-name">= EBITA</td>
                                                                        <td className="col-category">Total</td>
                                                                        <td className="text-right col-value">{formatNumber(breakdown.total, historicalCalculations.unit)}</td>
                                                                        <td></td>
                                                                    </tr>
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                )
                                            }

                                            // Fallback for older calculations without breakdown
                                            return (
                                                <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                                    <p style={{ fontStyle: 'italic', color: 'var(--text-secondary)', padding: '1rem' }}>
                                                        Detailed breakdown not available. Please re-run historical calculations to see the breakdown of Operating Income and Non-GAAP Adjustments.
                                                    </p>
                                                    <div className="balance-sheet-table-container">
                                                        <table className="balance-sheet-table">
                                                            <tbody>
                                                                <tr className="key-total-row">
                                                                    <td className="col-name">EBITA</td>
                                                                    <td className="text-right col-value">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                            )
                                        })()}
                                    </div>
                                )}

                                {historicalCalculations.adjusted_tax_rate != null && (
                                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                                        <h3>Adjusted Tax Rate</h3>
                                        <div className="balance-sheet-header" style={{ marginBottom: '1rem', marginTop: '0.5rem' }}>
                                            <div className="balance-sheet-meta">
                                                <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                                                <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                                                {(balanceSheet?.unit || incomeStatement?.unit) && (
                                                    <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                                                )}
                                            </div>
                                        </div>
                                        {(() => {
                                            const breakdown = historicalCalculations.adjusted_tax_rate_breakdown

                                            if (breakdown) {
                                                return (
                                                    <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                                        <div className="balance-sheet-table-container">
                                                            <table className="balance-sheet-table">
                                                                <thead>
                                                                    <tr>
                                                                        <th className="col-name">Line Item</th>
                                                                        <th className="col-category">Category</th>
                                                                        <th className="text-right col-value">Amount</th>
                                                                        <th className="col-type text-right">Type</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {/* Reported Tax */}
                                                                    <tr>
                                                                        <td className="col-name">Reported Tax Expense</td>
                                                                        <td className="col-category">Total</td>
                                                                        <td className="text-right col-value">{formatNumber(breakdown.reported_tax_expense, historicalCalculations.unit)}</td>
                                                                        <td className="col-type text-right">
                                                                            <span className="type-badge operating">Operating</span>
                                                                        </td>
                                                                    </tr>

                                                                    {/* Adjustments */}
                                                                    {breakdown.adjustments && breakdown.adjustments.length > 0 && (
                                                                        <>
                                                                            <tr>
                                                                                <td colSpan="4" style={{ fontWeight: 600, paddingTop: '0.5rem' }}>Deductible Adjustments</td>
                                                                            </tr>
                                                                            {breakdown.adjustments.map((item, idx) => (
                                                                                <tr key={`tax-adj-${idx}`}>
                                                                                    <td className="col-name">{item.line_name}</td>
                                                                                    <td className="col-category">Deductible</td>
                                                                                    <td className="text-right col-value">{formatNumber(item.line_value, historicalCalculations.unit)}</td>
                                                                                    <td className="col-type text-right">
                                                                                        <span className="type-badge non-operating">Non-Operating</span>
                                                                                    </td>
                                                                                </tr>
                                                                            ))}

                                                                            {/* Summary Calculation Block */}
                                                                            <tr style={{ borderTop: '1px solid var(--border-light)' }}>
                                                                                <td className="col-name">Total Deductible Items</td>
                                                                                <td className="col-category">Sum</td>
                                                                                <td className="text-right col-value">
                                                                                    {formatNumber(breakdown.adjustments.reduce((sum, item) => sum + (item.line_value || 0), 0), historicalCalculations.unit)}
                                                                                </td>
                                                                                <td></td>
                                                                            </tr>
                                                                            <tr>
                                                                                <td className="col-name">× Marginal Tax Rate</td>
                                                                                <td className="col-category">Rate</td>
                                                                                <td className="text-right col-value">25%</td>
                                                                                <td></td>
                                                                            </tr>
                                                                            <tr>
                                                                                <td className="col-name">= Tax Effect</td>
                                                                                <td className="col-category">Benefit/Cost</td>
                                                                                <td className="text-right col-value">
                                                                                    {formatNumber(breakdown.adjustments.reduce((sum, item) => sum + (item.line_value || 0), 0) * 0.25, historicalCalculations.unit)}
                                                                                </td>
                                                                                <td></td>
                                                                            </tr>
                                                                        </>
                                                                    )}

                                                                    {/* Adjusted Tax */}
                                                                    <tr className="key-total-row">
                                                                        <td className="col-name">= Adjusted Tax</td>
                                                                        <td className="col-category">Total</td>
                                                                        <td className="text-right col-value">{formatNumber(breakdown.adjusted_tax_expense, historicalCalculations.unit)}</td>
                                                                        <td></td>
                                                                    </tr>

                                                                    {/* EBITA Division Line */}
                                                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                                        <td className="col-name">/ EBITA</td>
                                                                        <td className="col-category">Total</td>
                                                                        <td className="text-right col-value">{formatNumber(breakdown.ebita, historicalCalculations.unit)}</td>
                                                                        <td></td>
                                                                    </tr>

                                                                    {/* Adjusted Tax Rate */}
                                                                    <tr className="key-total-row" style={{ borderTop: 'none' }}>
                                                                        <td className="col-name">= Adjusted Tax Rate</td>
                                                                        <td className="col-category">Rate</td>
                                                                        <td className="text-right col-value">{formatPercent(breakdown.adjusted_tax_rate, 100)}</td>
                                                                        <td></td>
                                                                    </tr>

                                                                    {/* Effective Tax Rate Comparison */}
                                                                    <tr>
                                                                        <td className="col-name" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Effective Tax Rate (Comparison)</td>
                                                                        <td className="col-category" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Rate</td>
                                                                        <td className="text-right col-value" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                                                            {formatPercent(historicalCalculations.effective_tax_rate, 100)}
                                                                        </td>
                                                                        <td></td>
                                                                    </tr>
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                )
                                            }

                                            // Fallback
                                            return (
                                                <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                                    <p style={{ fontStyle: 'italic', color: 'var(--text-secondary)', padding: '1rem' }}>
                                                        Detailed breakdown not available. Please re-run historical calculations.
                                                    </p>
                                                    <div className="balance-sheet-table-container">
                                                        <table className="balance-sheet-table">
                                                            <tbody>
                                                                <tr className="key-total-row">
                                                                    <td className="col-name">Adjusted Tax Rate</td>
                                                                    <td className="text-right col-value">{formatPercent(historicalCalculations.adjusted_tax_rate, 100)}</td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                            )
                                        })()}
                                    </div>
                                )}

                                {historicalCalculations.nopat != null && (
                                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                                        <h3>NOPAT & ROIC</h3>
                                        <div className="balance-sheet-header" style={{ marginBottom: '1rem', marginTop: '0.5rem' }}>
                                            <div className="balance-sheet-meta">
                                                <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                                                <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                                                {(balanceSheet?.unit || incomeStatement?.unit) && (
                                                    <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                            <div className="balance-sheet-table-container">
                                                <table className="balance-sheet-table">
                                                    <thead>
                                                        <tr>
                                                            <th className="col-name">Line Item</th>
                                                            <th className="text-right col-value">Amount</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td className="col-name">EBITA</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                                        </tr>
                                                        <tr>
                                                            <td className="col-name">– Adjusted Taxes (EBITA × {formatPercent(historicalCalculations.adjusted_tax_rate, 100)})</td>
                                                            <td className="text-right col-value" style={{ color: 'var(--text-secondary)' }}>
                                                                ({formatNumber((historicalCalculations.ebita || 0) * (historicalCalculations.adjusted_tax_rate || 0), historicalCalculations.unit)})
                                                            </td>
                                                        </tr>
                                                        <tr className="key-total-row">
                                                            <td className="col-name">= NOPAT</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.nopat, historicalCalculations.unit)}</td>
                                                        </tr>

                                                        {/* Show Annualized NOPAT if Quarterly */}
                                                        {historicalCalculations.time_period &&
                                                            (historicalCalculations.time_period.toUpperCase().includes('Q') && !historicalCalculations.time_period.toUpperCase().startsWith('FY')) && (
                                                                <tr>
                                                                    <td className="col-name">Annualized NOPAT</td>
                                                                    <td className="text-right col-value">
                                                                        {formatNumber((historicalCalculations.nopat || 0) * 4, historicalCalculations.unit)}
                                                                    </td>
                                                                </tr>
                                                            )}

                                                        <tr>
                                                            <td className="col-name" style={{ paddingTop: '1rem' }}>Invested Capital</td>
                                                            <td className="text-right col-value" style={{ paddingTop: '1rem' }}>
                                                                {formatNumber(historicalCalculations.invested_capital, historicalCalculations.unit)}
                                                            </td>
                                                        </tr>

                                                        <tr className="key-total-row" style={{ borderTop: 'none' }}>
                                                            <td className="col-name">= ROIC, Annualized</td>
                                                            <td className="text-right col-value">{formatPercent(historicalCalculations.roic, 100)}</td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                                    <h3>Summary Table</h3>
                                    <div className="balance-sheet-container">
                                        <div className="balance-sheet-header">
                                            <div className="balance-sheet-meta">
                                                <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                                                <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                                                {(balanceSheet?.unit || incomeStatement?.unit) && (
                                                    <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="balance-sheet-table-container">
                                            <table className="balance-sheet-table">
                                                <thead>
                                                    <tr>
                                                        <th className="col-name">Line Item</th>
                                                        <th className="text-right col-value">Amount</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {organicGrowth && organicGrowth.current_period_revenue != null && (
                                                        <tr>
                                                            <td className="col-name">Revenue</td>
                                                            <td className="text-right col-value">{formatNumber(organicGrowth.current_period_revenue, organicGrowth.current_period_revenue_unit)}</td>
                                                        </tr>
                                                    )}
                                                    {incomeStatement && incomeStatement.revenue_growth_yoy != null && (
                                                        <tr>
                                                            <td className="col-name">YOY Revenue Growth</td>
                                                            <td className="text-right col-value">{formatPercent(incomeStatement.revenue_growth_yoy, 1)}</td>
                                                        </tr>
                                                    )}
                                                    {organicGrowth && organicGrowth.organic_revenue_growth != null && (
                                                        <tr>
                                                            <td className="col-name">Organic Growth</td>
                                                            <td className="text-right col-value">{formatPercent(organicGrowth.organic_revenue_growth, 1)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.ebita != null && (
                                                        <tr>
                                                            <td className="col-name">EBITA</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.ebita_margin != null && (
                                                        <tr>
                                                            <td className="col-name">EBITA Margin</td>
                                                            <td className="text-right col-value">{formatPercent(historicalCalculations.ebita_margin, 100)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.effective_tax_rate != null && (
                                                        <tr>
                                                            <td className="col-name">Effective Tax Rate</td>
                                                            <td className="text-right col-value">{formatPercent(historicalCalculations.effective_tax_rate, 100)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.adjusted_tax_rate != null && (
                                                        <tr>
                                                            <td className="col-name">Adjusted Tax Rate</td>
                                                            <td className="text-right col-value">{formatPercent(historicalCalculations.adjusted_tax_rate, 100)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.nopat != null && (
                                                        <tr>
                                                            <td className="col-name">NOPAT</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.nopat, historicalCalculations.unit)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.net_working_capital != null && (
                                                        <tr>
                                                            <td className="col-name">Net Working Capital</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.net_working_capital, historicalCalculations.unit)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.net_long_term_operating_assets != null && (
                                                        <tr>
                                                            <td className="col-name">Net Long Term Operating Assets</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.net_long_term_operating_assets, historicalCalculations.unit)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.invested_capital != null && (
                                                        <tr>
                                                            <td className="col-name">Invested Capital</td>
                                                            <td className="text-right col-value">{formatNumber(historicalCalculations.invested_capital, historicalCalculations.unit)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.capital_turnover != null && (
                                                        <tr>
                                                            <td className="col-name">Capital Turnover, Annualized</td>
                                                            <td className="text-right col-value">{formatDecimal(historicalCalculations.capital_turnover, 4)}</td>
                                                        </tr>
                                                    )}
                                                    {historicalCalculations && historicalCalculations.roic != null && (
                                                        <tr>
                                                            <td className="col-name">ROIC, Annualized</td>
                                                            <td className="text-right col-value">{formatPercent(historicalCalculations.roic, 100)}</td>
                                                        </tr>
                                                    )}
                                                    {incomeStatement && (incomeStatement.diluted_shares_outstanding != null || incomeStatement.basic_shares_outstanding != null) && (
                                                        <tr>
                                                            <td className="col-name">{incomeStatement.diluted_shares_outstanding != null ? 'Diluted Shares Outstanding' : 'Basic Shares Outstanding'}</td>
                                                            <td className="text-right col-value">
                                                                {(incomeStatement.diluted_shares_outstanding || incomeStatement.basic_shares_outstanding).toLocaleString()}
                                                            </td>
                                                        </tr>
                                                    )}
                                                </tbody>
                                            </table>
                                        </div>

                                        {/* Calculation Notes */}
                                        {historicalCalculations.calculation_notes && (() => {
                                            try {
                                                const notes = JSON.parse(historicalCalculations.calculation_notes)
                                                if (notes && notes.length > 0) {
                                                    return (
                                                        <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px' }}>
                                                            <h4 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '0.9rem' }}>Notes:</h4>
                                                            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                                                                {notes.map((note, idx) => (
                                                                    <li key={idx} style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>{note}</li>
                                                                ))}
                                                            </ul>
                                                        </div>
                                                    )
                                                }
                                            } catch (e) {
                                                return null
                                            }
                                            return null
                                        })()}
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

function SharesOutstandingTable({ incomeStatement }) {
    if (!incomeStatement) return null

    const basic = incomeStatement.basic_shares_outstanding
    const diluted = incomeStatement.diluted_shares_outstanding

    const hasShares = (basic !== null && basic !== undefined) || (diluted !== null && diluted !== undefined)

    if (!hasShares) {
        return (
            <div className="info-section">
                <p className="info-text" style={{ color: 'var(--error)', fontWeight: 500 }}>
                    Shares outstanding data is missing.
                </p>
                <p className="info-text" style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                    This critical information could not be extracted from the document. Please verify the document contains shares outstanding data.
                </p>
            </div>
        )
    }

    // Determine unit from shares data
    const unit = incomeStatement.basic_shares_outstanding_unit || incomeStatement.diluted_shares_outstanding_unit || 'shares'

    return (
        <div className="balance-sheet-container">
            <div className="balance-sheet-header">
                <div className="balance-sheet-meta">
                    <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
                </div>
            </div>

            <div className="balance-sheet-table-container">
                <table className="balance-sheet-table">
                    <thead>
                        <tr>
                            <th className="col-name">Line Item</th>
                            <th className="text-right col-value">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(basic !== null && basic !== undefined) && (
                            <tr>
                                <td className="col-name">Basic Shares Outstanding</td>
                                <td className="text-right col-value">{basic.toLocaleString()}</td>
                            </tr>
                        )}
                        {(diluted !== null && diluted !== undefined) && (
                            <tr>
                                <td className="col-name">Diluted Shares Outstanding</td>
                                <td className="text-right col-value">{diluted.toLocaleString()}</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function OrganicGrowthTable({ data, formatNumber }) {
    if (!data) return null

    // Determine currency and unit from data
    const currency = data.currency || 'N/A'
    const unit = data.prior_period_revenue_unit || data.current_period_revenue_unit || 'N/A'

    return (
        <div className="balance-sheet-container">
            <div className="balance-sheet-header">
                <div className="balance-sheet-meta">
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit && unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
                    )}
                </div>
            </div>

            <div className="balance-sheet-table-container">
                <table className="balance-sheet-table">
                    <thead>
                        <tr>
                            <th className="col-name">Line Item</th>
                            <th className="text-right col-value">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.prior_period_revenue !== null && (
                            <tr>
                                <td className="col-name">Prior Period Revenue</td>
                                <td className="text-right col-value">{formatNumber(data.prior_period_revenue, data.prior_period_revenue_unit)}</td>
                            </tr>
                        )}
                        {data.current_period_revenue !== null && (
                            <tr>
                                <td className="col-name">Current Period Revenue</td>
                                <td className="text-right col-value">{formatNumber(data.current_period_revenue, data.current_period_revenue_unit)}</td>
                            </tr>
                        )}
                        {data.acquisition_revenue_impact !== null && (
                            <tr>
                                <td className="col-name">Acquisition Revenue Impact</td>
                                <td className="text-right col-value">{formatNumber(data.acquisition_revenue_impact, data.acquisition_revenue_impact_unit)}</td>
                            </tr>
                        )}
                        {data.current_period_adjusted_revenue !== null && (
                            <tr>
                                <td className="col-name">Adjusted Revenue</td>
                                <td className="text-right col-value">{formatNumber(data.current_period_adjusted_revenue, data.current_period_adjusted_revenue_unit)}</td>
                            </tr>
                        )}
                        {data.simple_revenue_growth !== null && (
                            <tr>
                                <td className="col-name">Simple Revenue Growth</td>
                                <td className="text-right col-value">{parseFloat(data.simple_revenue_growth).toFixed(2)}%</td>
                            </tr>
                        )}
                        {data.organic_revenue_growth !== null && (
                            <tr>
                                <td className="col-name">Organic Revenue Growth</td>
                                <td className="text-right col-value">{parseFloat(data.organic_revenue_growth).toFixed(2)}%</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function LineItemTable({ data, formatNumber, balanceSheet, incomeStatement, typeOverride, categoryFormatter, showCategory = true }) {
    if (!data || !data.line_items || data.line_items.length === 0) return null

    // Determine currency and unit from data or source documents
    const currency = data.currency || balanceSheet?.currency || incomeStatement?.currency || 'N/A'
    const unit = data.unit || balanceSheet?.unit || incomeStatement?.unit || (data.line_items[0]?.unit ? data.line_items[0].unit.replace('_', ' ') : 'N/A')
    const timePeriod = data.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'

    return (
        <div className="balance-sheet-container">
            <div className="balance-sheet-header">
                <div className="balance-sheet-meta">
                    <span><strong>Time Period:</strong> {timePeriod}</span>
                    <span><strong>Currency:</strong> {currency}</span>
                    {unit && unit !== 'N/A' && (
                        <span><strong>Unit:</strong> {unit.replace('_', ' ')}</span>
                    )}
                </div>
            </div>

            <div className="balance-sheet-table-container">
                <table className="balance-sheet-table">
                    <thead>
                        <tr>
                            <th className="col-name">Line Item</th>
                            {showCategory && <th className="col-category">Category</th>}
                            <th className="text-right col-value">Amount</th>
                            <th className="text-right col-type">Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.line_items.map((item, index) => {
                            const categoryValue = item.category || item.line_category
                            const category = categoryFormatter ? categoryFormatter(categoryValue) : (categoryValue || 'N/A')

                            let typeContent;
                            if (typeOverride) {
                                typeContent = typeOverride
                            } else {
                                typeContent = item.is_operating === null || item.is_operating === undefined ? (
                                    <span className="text-muted">—</span>
                                ) : (
                                    <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                        {item.is_operating ? 'Operating' : 'Non-operating'}
                                    </span>
                                )
                            }

                            const nameLower = (item.line_name || '').toLowerCase()
                            const categoryLower = (categoryValue || '').toLowerCase()
                            const isKey = nameLower.includes('total') ||
                                nameLower.includes('subtotal') ||
                                nameLower.includes('revenue') ||
                                nameLower === 'gross profit' ||
                                nameLower === 'operating income' ||
                                nameLower === 'net income' ||
                                nameLower === 'ebita' ||
                                nameLower === 'ebitda' ||
                                nameLower === 'invested capital' ||
                                nameLower === 'net working capital' ||
                                categoryLower === 'total'

                            return (
                                <tr key={`${item.line_name}-${index}`} className={isKey ? 'key-total-row' : ''}>
                                    <td className="col-name">{item.line_name}</td>
                                    {showCategory && <td className="col-category">{category}</td>}
                                    <td className="text-right col-value">{formatNumber(item.line_value, item.unit)}</td>
                                    <td className="text-right col-type">{typeContent}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div >
        </div >
    )
}

export default DocumentExtractionView
