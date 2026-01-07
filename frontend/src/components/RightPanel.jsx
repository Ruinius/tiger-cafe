import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import LineItemTable from './LineItemTable'
import OrganicGrowthTable from './OrganicGrowthTable'
import StandardizedBreakdownTable from './StandardizedBreakdownTable'
import SharesOutstandingTable from './SharesOutstandingTable'
import './RightPanel.css'

function RightPanel({ selectedCompany, selectedDocument }) {
  const API_BASE_URL = 'http://localhost:8000/api'
  const { isAuthenticated, token } = useAuth()
  const [balanceSheet, setBalanceSheet] = useState(null)
  const [incomeStatement, setIncomeStatement] = useState(null)
  const [organicGrowth, setOrganicGrowth] = useState(null)
  const [amortization, setAmortization] = useState(null)
  const [otherAssets, setOtherAssets] = useState(null)
  const [otherLiabilities, setOtherLiabilities] = useState(null)
  const [nonOperatingClassification, setNonOperatingClassification] = useState(null)
  const [additionalItemsLoadAttempted, setAdditionalItemsLoadAttempted] = useState(false)
  const [historicalCalculations, setHistoricalCalculations] = useState(null)
  const [historicalCalculationsLoadAttempted, setHistoricalCalculationsLoadAttempted] = useState(false)
  const [companyHistoricalCalculations, setCompanyHistoricalCalculations] = useState(null)
  const [companyHistoricalError, setCompanyHistoricalError] = useState(null)
  const [companyHistoricalLoading, setCompanyHistoricalLoading] = useState(false)
  const [financialStatementProgress, setFinancialStatementProgress] = useState(null)
  const [error, setError] = useState(null)
  const [balanceSheetLoadAttempts, setBalanceSheetLoadAttempts] = useState(0)
  const [incomeStatementLoadAttempts, setIncomeStatementLoadAttempts] = useState(0)
  const progressPollingIntervalRef = useRef(null)
  const balanceSheetLoadingRef = useRef(false)
  const incomeStatementLoadingRef = useRef(false)
  const balanceSheetAttemptsRef = useRef(0)
  const incomeStatementAttemptsRef = useRef(0)
  const MAX_LOAD_ATTEMPTS = 3

  // Check if document is eligible for financial statement processing
  const isEligibleForFinancialStatements = selectedDocument &&
    ['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)

  // Check if all milestones are in terminal state (completed or error, not pending, checking, or in_progress)
  const areAllMilestonesTerminal = useCallback(() => {
    if (!financialStatementProgress) {
      return false
    }

    // If status is "not_started", don't treat as terminal - wait for checking to complete
    if (financialStatementProgress.status === 'not_started') {
      return false
    }

    if (!financialStatementProgress.milestones) {
      return false
    }

    const milestones = financialStatementProgress.milestones
    const allMilestones = Object.values(milestones)

    // If no milestones exist, don't treat as terminal
    if (allMilestones.length === 0) {
      return false
    }

    // All milestones must be completed, error, or not_found (not pending, checking, or in_progress)
    return allMilestones.every((milestone) =>
      milestone.status === 'completed' || milestone.status === 'error' || milestone.status === 'not_found'
    )
  }, [financialStatementProgress])

  const loadFinancialStatementProgress = useCallback(async () => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return

    try {
      const endpoint = isAuthenticated ? 'financial-statement-progress' : 'financial-statement-progress-test'
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
        { headers }
      )
      setFinancialStatementProgress(response.data)
    } catch (err) {
      // If endpoint doesn't exist or error, set to null
      setFinancialStatementProgress(null)
    }
  }, [selectedDocument, isEligibleForFinancialStatements, isAuthenticated, token])

  const loadBalanceSheet = useCallback(async () => {
    if (!selectedDocument) return
    if (balanceSheetLoadingRef.current) return // Prevent concurrent calls
    if (balanceSheetAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return // Don't retry if max attempts reached

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
        setBalanceSheetLoadAttempts(0) // Reset attempts on success
      } else {
        setBalanceSheet(null)
        balanceSheetAttemptsRef.current += 1
        setBalanceSheetLoadAttempts(prev => prev + 1)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setBalanceSheet(null)
        balanceSheetAttemptsRef.current += 1
        setBalanceSheetLoadAttempts(prev => prev + 1)
      } else {
        setError(err.response?.data?.detail || 'Failed to load balance sheet')
        balanceSheetAttemptsRef.current += 1
        setBalanceSheetLoadAttempts(prev => prev + 1)
      }
    } finally {
      balanceSheetLoadingRef.current = false
    }
  }, [selectedDocument, isAuthenticated, token])

  const loadIncomeStatement = useCallback(async () => {
    if (!selectedDocument) return
    if (incomeStatementLoadingRef.current) return // Prevent concurrent calls
    if (incomeStatementAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return // Don't retry if max attempts reached

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
        setIncomeStatementLoadAttempts(0) // Reset attempts on success
      } else {
        setIncomeStatement(null)
        incomeStatementAttemptsRef.current += 1
        setIncomeStatementLoadAttempts(prev => prev + 1)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setIncomeStatement(null)
        incomeStatementAttemptsRef.current += 1
        setIncomeStatementLoadAttempts(prev => prev + 1)
      } else {
        setError(err.response?.data?.detail || 'Failed to load income statement')
        incomeStatementAttemptsRef.current += 1
        setIncomeStatementLoadAttempts(prev => prev + 1)
      }
    } finally {
      incomeStatementLoadingRef.current = false
    }
  }, [selectedDocument, isAuthenticated, token])

  const loadAdditionalItems = useCallback(async () => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return

    const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}

    // Check if document is earnings announcement
    const isEarningsAnnouncement = selectedDocument.document_type === 'earnings_announcement' ||
      selectedDocument.document_type === 'EARNINGS_ANNOUNCEMENT'

    const endpoints = {
      organicGrowth: 'organic-growth',
      amortization: 'amortization',
      // Skip other-assets and other-liabilities for earnings announcements
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
      } else {
        const message = result.reason?.response?.data?.detail
        if (message && message.includes('not found')) {
          // Keep null for not found
        } else {
          setError(result.reason?.response?.data?.detail || 'Failed to load additional items')
        }
      }
    })
  }, [selectedDocument, isEligibleForFinancialStatements, isAuthenticated, token])

  // Load progress tracker first when document is selected
  useEffect(() => {
    // Reset state when document changes
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

    // Clear any existing polling intervals
    if (progressPollingIntervalRef.current) {
      clearInterval(progressPollingIntervalRef.current)
      progressPollingIntervalRef.current = null
    }

    if (selectedDocument && isEligibleForFinancialStatements) {
      // Always load progress tracker first
      loadFinancialStatementProgress()
    }
  }, [selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

  // Poll for progress when there are active milestones
  useEffect(() => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return

    // Check if any milestone is in progress or pending
    const hasActiveMilestones = financialStatementProgress &&
      financialStatementProgress.milestones &&
      Object.values(financialStatementProgress.milestones).some((milestone) =>
        milestone.status === 'in_progress' || milestone.status === 'pending'
      )

    if (hasActiveMilestones) {
      const interval = setInterval(() => {
        loadFinancialStatementProgress()
      }, 3000) // Poll every 3 seconds (reduced frequency for better performance)

      progressPollingIntervalRef.current = interval

      return () => {
        clearInterval(interval)
        progressPollingIntervalRef.current = null
      }
    } else {
      // Clear interval if not processing
      if (progressPollingIntervalRef.current) {
        clearInterval(progressPollingIntervalRef.current)
        progressPollingIntervalRef.current = null
      }

      // Send event to LeftPanel to reset isProcessing when all milestones are terminal
      window.dispatchEvent(new CustomEvent('financialStatementsProcessingComplete'))
    }
  }, [financialStatementProgress, selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

  const loadHistoricalCalculations = useCallback(async () => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return

    try {
      const endpoint = isAuthenticated ? 'historical-calculations' : 'historical-calculations/test'
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
        { headers }
      )
      setHistoricalCalculations(response.data)
    } catch (err) {
      if (err.response?.status === 404) {
        setHistoricalCalculations(null)
      } else {
        console.error('Error loading historical calculations:', err)
        setHistoricalCalculations(null)
      }
    }
  }, [selectedDocument, isEligibleForFinancialStatements, isAuthenticated, token])

  // Load balance sheet and income statement only when all milestones are terminal
  useEffect(() => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return
    if (!areAllMilestonesTerminal()) return

    // Only load if attempts haven't exceeded max and data isn't already loaded and not currently loading
    if (balanceSheetAttemptsRef.current < MAX_LOAD_ATTEMPTS && !balanceSheet && !balanceSheetLoadingRef.current) {
      loadBalanceSheet()
    }

    if (incomeStatementAttemptsRef.current < MAX_LOAD_ATTEMPTS && !incomeStatement && !incomeStatementLoadingRef.current) {
      loadIncomeStatement()
    }

    if (!additionalItemsLoadAttempted) {
      const loadItems = async () => {
        await loadAdditionalItems()
        setAdditionalItemsLoadAttempted(true)
      }
      loadItems()
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

  // Reset historical calculations state when document changes
  useEffect(() => {
    setHistoricalCalculations(null)
    setHistoricalCalculationsLoadAttempted(false)
  }, [selectedDocument?.id])

  const loadCompanyHistoricalCalculations = useCallback(async () => {
    if (!selectedCompany || selectedDocument) return

    setCompanyHistoricalLoading(true)
    setCompanyHistoricalError(null)

    try {
      const endpoint = isAuthenticated
        ? 'historical-calculations'
        : 'historical-calculations/test'
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/companies/${selectedCompany.id}/${endpoint}`,
        { headers }
      )
      setCompanyHistoricalCalculations(response.data)
    } catch (err) {
      if (err.response?.status === 404) {
        setCompanyHistoricalCalculations(null)
      } else {
        setCompanyHistoricalError(err.response?.data?.detail || 'Failed to load company analysis')
        setCompanyHistoricalCalculations(null)
      }
    } finally {
      setCompanyHistoricalLoading(false)
    }
  }, [selectedCompany, selectedDocument, isAuthenticated, token])

  useEffect(() => {
    setCompanyHistoricalCalculations(null)
    setCompanyHistoricalError(null)

    if (selectedCompany && !selectedDocument) {
      loadCompanyHistoricalCalculations()
    }
  }, [selectedCompany?.id, selectedDocument?.id, loadCompanyHistoricalCalculations])

  // Load historical calculations only once when both balance sheet and income statement are loaded
  useEffect(() => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return

    // Only load historical calculations once when both are loaded and we haven't attempted yet
    if (areAllMilestonesTerminal() && balanceSheet && incomeStatement && !historicalCalculationsLoadAttempted) {
      setHistoricalCalculationsLoadAttempted(true)
      loadHistoricalCalculations()
    }
  }, [areAllMilestonesTerminal, selectedDocument?.id, balanceSheet, incomeStatement, historicalCalculationsLoadAttempted, loadHistoricalCalculations])

  const formatNumber = (value, unit = null) => {
    if (value === null || value === undefined) return 'N/A'

    // Values are stored in the reported unit (e.g., 100 if unit is "millions" means 100 million)
    // Display them as-is without conversion - the unit column shows the scale
    const displayValue = parseFloat(value)

    // Format as number with thousands separators, no currency symbol
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(displayValue)
  }

  const formatPercent = (value, multiplier = 1) => {
    if (value === null || value === undefined) return 'N/A'
    const percentValue = parseFloat(value) * multiplier
    if (Number.isNaN(percentValue)) return 'N/A'
    return `${percentValue.toFixed(2)}%`
  }

  const formatDecimal = (value, digits = 4) => {
    if (value === null || value === undefined) return 'N/A'
    const numericValue = parseFloat(value)
    if (Number.isNaN(numericValue)) return 'N/A'
    return numericValue.toFixed(digits)
  }

  // Expose function to clear data (for re-run and delete buttons)
  useEffect(() => {
    // Listen for custom events to clear data
    const handleClearData = () => {
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
    }

    // Listen for event to reload historical calculations
    const handleReloadHistoricalCalculations = () => {
      if (selectedDocument && isEligibleForFinancialStatements) {
        // Reset the flag so we can reload
        setHistoricalCalculationsLoadAttempted(false)
        loadHistoricalCalculations()
        setHistoricalCalculationsLoadAttempted(true)
      }
    }

    // Listen for event to reset progress to PENDING
    const handleResetProgressToPending = (event) => {
      const { documentId } = event.detail || {}
      // Only reset if it's for the current document
      if (documentId === selectedDocument?.id) {
        // Immediately set all milestones to PENDING
        // Use the exact milestone keys that the server uses
        setFinancialStatementProgress({
          status: 'processing',
          milestones: {
            balance_sheet: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            income_statement: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            extracting_additional_items: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            classifying_non_operating_items: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            }
          },
          last_updated: new Date().toISOString()
        })
        // Don't reload immediately - let the server reset first, then reload after delay
        setTimeout(() => {
          loadFinancialStatementProgress()
        }, 1000)
      }
    }

    // Listen for event to reload progress
    const handleReloadProgress = () => {
      if (selectedDocument && isEligibleForFinancialStatements) {
        // Delay reload slightly to ensure server has reset milestones
        setTimeout(() => {
          loadFinancialStatementProgress()
        }, 500)
      }
    }

    window.addEventListener('clearFinancialStatements', handleClearData)
    window.addEventListener('resetProgressToPending', handleResetProgressToPending)
    window.addEventListener('reloadProgress', handleReloadProgress)
    window.addEventListener('reloadHistoricalCalculations', handleReloadHistoricalCalculations)
    return () => {
      window.removeEventListener('clearFinancialStatements', handleClearData)
      window.removeEventListener('resetProgressToPending', handleResetProgressToPending)
      window.removeEventListener('reloadProgress', handleReloadProgress)
      window.removeEventListener('reloadHistoricalCalculations', handleReloadHistoricalCalculations)
    }
  }, [selectedDocument, isEligibleForFinancialStatements, loadFinancialStatementProgress, loadHistoricalCalculations])

  if (selectedDocument) {
    // Check if we should show "nothing to see here" (no data and all attempts exhausted or no progress)
    const hasNoData = !balanceSheet && !incomeStatement
    const allAttemptsExhausted = balanceSheetLoadAttempts >= MAX_LOAD_ATTEMPTS && incomeStatementLoadAttempts >= MAX_LOAD_ATTEMPTS
    const showNothingMessage = hasNoData && (allAttemptsExhausted || (areAllMilestonesTerminal() && !financialStatementProgress))

    return (
      <div className="right-panel">
        <div className="panel-content">
          <h2>Financial Statements</h2>

          {!isEligibleForFinancialStatements && (
            <div className="info-section">
              <p className="info-text" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                This document type is not yet implemented.
              </p>
              <p className="info-text" style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                Financial statement processing is currently only available for earnings announcements.
                Support for {selectedDocument?.document_type?.replace(/_/g, ' ') || 'this document type'} will be added in a future update.
              </p>
            </div>
          )}

          {isEligibleForFinancialStatements && (
            <>
              {/* Financial Statement Progress Tracker - Always show if progress exists */}
              {financialStatementProgress && (
                <div className="info-section" style={{ marginBottom: '2rem', padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px' }}>
                  <h4 style={{ marginTop: 0, marginBottom: '1rem' }}>Processing Progress</h4>
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
                        <div key={milestone.key} className="progress-milestone-item" style={{
                          marginBottom: '0.75rem',
                          padding: '0.5rem',
                          borderRadius: '4px',
                          backgroundColor: status === 'in_progress' ? 'var(--accent-light)' :
                            status === 'completed' ? 'var(--success-light)' :
                              status === 'error' ? 'var(--error-light)' :
                                status === 'checking' ? 'var(--bg-primary)' :
                                  status === 'not_found' ? 'var(--bg-secondary)' : 'transparent'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{
                              fontSize: '1.2rem',
                              color: status === 'completed' ? 'var(--success)' :
                                status === 'error' ? 'var(--error)' :
                                  status === 'in_progress' ? 'var(--accent)' :
                                    status === 'checking' ? 'var(--text-secondary)' :
                                      status === 'not_found' ? 'var(--text-secondary)' : 'var(--text-secondary)'
                            }}>
                              {status === 'completed' ? '✓' :
                                status === 'in_progress' ? <span className="status-spinner" aria-hidden="true" /> :
                                  status === 'error' ? '✗' :
                                    status === 'checking' ? <span className="status-spinner" aria-hidden="true" /> :
                                      status === 'not_found' ? '○' : '○'}
                            </span>
                            <span style={{ flex: 1, fontWeight: (status === 'in_progress' || status === 'checking') ? 'bold' : 'normal' }}>
                              {milestone.label}
                            </span>
                            <span style={{
                              fontSize: '0.875rem',
                              color: 'var(--text-secondary)',
                              textTransform: 'capitalize'
                            }}>
                              {status === 'in_progress' ? 'In Progress' :
                                status === 'completed' ? 'Completed' :
                                  status === 'error' ? 'Error' :
                                    status === 'checking' ? 'Checking...' :
                                      status === 'not_found' ? 'Not Found' : 'Pending'}
                            </span>
                          </div>
                          {/* Only show message for errors or in-progress, not for completed status */}
                          {message && (status === 'error' || status === 'in_progress' || status === 'checking') && (
                            <div style={{
                              marginTop: '0.25rem',
                              fontSize: '0.875rem',
                              color: 'var(--text-secondary)',
                              marginLeft: '1.75rem'
                            }}>
                              {message}
                            </div>
                          )}
                          {/* Display log messages if available */}
                          {milestoneData?.logs && milestoneData.logs.length > 0 && (
                            <div style={{
                              marginTop: '0.5rem',
                              marginLeft: '1.75rem',
                              fontSize: '0.8rem',
                              color: 'var(--text-secondary)'
                            }}>
                              {milestoneData.logs.map((log, idx) => (
                                <div
                                  key={idx}
                                  style={{
                                    marginBottom: '0.25rem',
                                    padding: '0.25rem 0',
                                    borderLeft: '2px solid var(--border)',
                                    paddingLeft: '0.5rem'
                                  }}
                                >
                                  {log.message}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Show "nothing to see here" if no data and all attempts exhausted or no progress */}
              {showNothingMessage && (
                <div className="info-section">
                  <p className="info-text">Nothing to see here.</p>
                </div>
              )}

              {/* Only show balance sheet and income statement if all milestones are terminal */}
              {areAllMilestonesTerminal() && !showNothingMessage && (
                <>
                  {/* Balance Sheet Section */}
                  {balanceSheet && (
                    <div style={{ marginBottom: '2rem' }}>
                      <h3>Balance Sheet</h3>
                      <div className="balance-sheet-container">
                        <div className="balance-sheet-header">
                          <div className="balance-sheet-meta">
                            <span><strong>Time Period:</strong> {balanceSheet.time_period || 'N/A'}</span>
                            <span><strong>Currency:</strong> {balanceSheet.currency || 'N/A'}</span>
                            {balanceSheet.unit && (
                              <span><strong>Unit:</strong> {balanceSheet.unit.replace('_', ' ')}</span>
                            )}
                            <span className={`validation-badge ${balanceSheet.is_valid ? 'valid' : 'invalid'}`}>
                              {balanceSheet.is_valid ? '✓ Valid' : '✗ Validation Errors'}
                            </span>
                          </div>
                        </div>

                        {!balanceSheet.is_valid && balanceSheet.validation_errors && (
                          <div className="validation-errors">
                            <h4>Validation Errors:</h4>
                            <ul>
                              {JSON.parse(balanceSheet.validation_errors).map((err, idx) => (
                                <li key={idx}>{err}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <div className="balance-sheet-table-container">
                          <table className="balance-sheet-table">
                            <thead>
                              <tr>
                                <th>Line Item</th>
                                <th>Category</th>
                                <th className="text-right">Amount</th>
                                <th className="text-right">Type</th>
                              </tr>
                            </thead>
                            <tbody>
                              {balanceSheet.line_items && balanceSheet.line_items.length > 0 ? (
                                balanceSheet.line_items.map((item) => {
                                  const lineNameLower = item.line_name.toLowerCase()
                                  const isTotalAssets = lineNameLower.includes('total assets') && !lineNameLower.includes('liabilities')
                                  const isTotalLiabilities = lineNameLower.includes('total liabilities') && !lineNameLower.includes('equity') && !lineNameLower.includes('stockholder')
                                  const isTotalEquity = (lineNameLower.includes('total equity') || lineNameLower.includes('total stockholder') || lineNameLower.includes('total shareholders')) && !lineNameLower.includes('liabilities')
                                  const isTotalLiabilitiesEquity = (lineNameLower.includes('total liabilities and equity') || lineNameLower.includes('total liabilities and stockholder') || lineNameLower.includes('total liabilities and shareholder'))

                                  const isKeyTotal = isTotalAssets || isTotalLiabilities || isTotalEquity || isTotalLiabilitiesEquity

                                  return (
                                    <tr
                                      key={item.id}
                                      className={isKeyTotal ? 'key-total-row' : (item.line_category?.toLowerCase().includes('total') ? 'total-row' : '')}
                                    >
                                      <td className={isKeyTotal ? 'bold-text' : ''}>{item.line_name}</td>
                                      <td className={isKeyTotal ? 'bold-text' : ''}>{item.line_category || 'N/A'}</td>
                                      <td className={`text-right ${isKeyTotal ? 'bold-text' : ''}`}>{formatNumber(item.line_value, balanceSheet.unit)}</td>
                                      <td className="text-right">
                                        {item.is_operating === null || item.is_operating === undefined ? (
                                          <span className="text-muted">—</span>
                                        ) : (
                                          <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                            {item.is_operating ? 'Operating' : 'Non-Operating'}
                                          </span>
                                        )}
                                      </td>
                                    </tr>
                                  )
                                })
                              ) : (
                                <tr>
                                  <td colSpan="4" className="no-data">No line items found</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Income Statement Section */}
                  {incomeStatement && (
                    <div style={{ marginTop: balanceSheet ? '2rem' : '0', borderTop: balanceSheet ? '1px solid var(--border)' : 'none', paddingTop: balanceSheet ? '2rem' : '0' }}>
                      <h3>Income Statement</h3>
                      <div className="balance-sheet-container">
                        <div className="balance-sheet-header">
                          <div className="balance-sheet-meta">
                            <span><strong>Time Period:</strong> {incomeStatement.time_period || 'N/A'}</span>
                            <span><strong>Currency:</strong> {incomeStatement.currency || 'N/A'}</span>
                            {incomeStatement.unit && (
                              <span><strong>Unit:</strong> {incomeStatement.unit.replace('_', ' ')}</span>
                            )}
                            <span className={`validation-badge ${incomeStatement.is_valid ? 'valid' : 'invalid'}`}>
                              {incomeStatement.is_valid ? '✓ Valid' : '✗ Validation Errors'}
                            </span>
                          </div>
                        </div>

                        {!incomeStatement.is_valid && incomeStatement.validation_errors && (
                          <div className="validation-errors">
                            <h4>Validation Errors:</h4>
                            <ul>
                              {JSON.parse(incomeStatement.validation_errors).map((err, idx) => (
                                <li key={idx}>{err}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <div className="balance-sheet-table-container">
                          <table className="balance-sheet-table">
                            <thead>
                              <tr>
                                <th>Line Item</th>
                                <th>Category</th>
                                <th className="text-right">Amount</th>
                                <th className="text-right">Type</th>
                              </tr>
                            </thead>
                            <tbody>
                              {incomeStatement.line_items && incomeStatement.line_items.length > 0 ? (
                                incomeStatement.line_items.map((item) => {
                                  const lineNameLower = item.line_name.toLowerCase()
                                  const isKeyTotal = lineNameLower.includes('total net revenue') ||
                                    lineNameLower.includes('gross profit') ||
                                    lineNameLower.includes('operating income') ||
                                    lineNameLower.includes('pretax income') ||
                                    lineNameLower.includes('net income')

                                  return (
                                    <tr
                                      key={item.id}
                                      className={isKeyTotal ? 'key-total-row' : ''}
                                    >
                                      <td className={isKeyTotal ? 'bold-text' : ''}>{item.line_name}</td>
                                      <td className="col-category">{item.line_category || 'N/A'}</td>
                                      <td className={`text-right ${isKeyTotal ? 'bold-text' : ''}`}>{formatNumber(item.line_value, incomeStatement.unit)}</td>
                                      <td className="text-right">
                                        {item.is_operating === null || item.is_operating === undefined ? (
                                          <span className="text-muted">—</span>
                                        ) : (
                                          <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                            {item.is_operating ? 'Operating' : 'Non-Operating'}
                                          </span>
                                        )}
                                      </td>
                                    </tr>
                                  )
                                })
                              ) : (
                                <tr>
                                  <td colSpan="4" className="no-data">No line items found</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>

                      </div>
                    </div>
                  )}

                  {/* Shares Outstanding Section */}
                  {incomeStatement && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Shares Outstanding</h3>
                      <SharesOutstandingTable incomeStatement={incomeStatement} />
                    </div>
                  )}

                  {/* Non-GAAP Reconciliation Section */}
                  {amortization && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Non-GAAP Reconciliation</h3>
                      <LineItemTable data={amortization} formatNumber={formatNumber} showCategory={false} />
                    </div>
                  )}

                  {/* Organic Growth Section */}
                  {organicGrowth && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Organic Growth</h3>
                      <OrganicGrowthTable data={organicGrowth} formatNumber={formatNumber} />
                    </div>
                  )}

                  {/* Other Assets Section */}
                  {otherAssets && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Other Assets</h3>
                      <StandardizedBreakdownTable
                        data={otherAssets}
                        balanceSheet={balanceSheet}
                        formatNumber={formatNumber}
                        standardReferences={[
                          { id: 1, label: 'Other Current Assets', category: 'Current Assets' },
                          { id: 2, label: 'Other Non-Current Assets', category: 'Non-Current Assets' }
                        ]}
                      />
                    </div>
                  )}

                  {/* Other Liabilities Section */}
                  {otherLiabilities && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Other Liabilities</h3>
                      <StandardizedBreakdownTable
                        data={otherLiabilities}
                        balanceSheet={balanceSheet}
                        formatNumber={formatNumber}
                        standardReferences={[
                          { id: 1, label: 'Other Current Liabilities', category: 'Current Liabilities' },
                          { id: 2, label: 'Other Non-Current Liabilities', category: 'Non-Current Liabilities' }
                        ]}
                      />
                    </div>
                  )}

                  {/* Non-Operating Classification Section */}
                  {nonOperatingClassification && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Non-Operating Classification</h3>
                      {nonOperatingClassification.line_items && nonOperatingClassification.line_items.length > 0 ? (
                        <LineItemTable
                          data={nonOperatingClassification}
                          formatNumber={formatNumber}
                          balanceSheet={balanceSheet}
                          incomeStatement={incomeStatement}
                          typeOverride={<span className="type-badge non-operating">Non-Operating</span>}
                          categoryFormatter={(value) => {
                            if (!value) return 'Unknown'
                            return value
                              .replace(/_/g, ' ')
                              .split(' ')
                              .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
                              .join(' ')
                          }}
                        />
                      ) : (
                        <div className="info-section">
                          <p className="info-text" style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                            No non-operating items found to classify.
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Historical Calculations Section */}
                  {historicalCalculations && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>


                      <div className="balance-sheet-header">
                        <div className="balance-sheet-meta">
                          <span><strong>Time Period:</strong> {historicalCalculations.time_period || balanceSheet?.time_period || incomeStatement?.time_period || 'N/A'}</span>
                          <span><strong>Currency:</strong> {balanceSheet?.currency || incomeStatement?.currency || 'N/A'}</span>
                          {(balanceSheet?.unit || incomeStatement?.unit) && (
                            <span><strong>Unit:</strong> {(balanceSheet?.unit || incomeStatement?.unit).replace('_', ' ')}</span>
                          )}
                        </div>
                      </div>

                      {/* Invested Capital Breakdown */}
                      {historicalCalculations.invested_capital != null && balanceSheet && (
                        <div style={{ marginTop: '1.5rem' }}>

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
                            const nonCurrentAssetsOperating = []
                            const nonCurrentLiabilitiesOperating = []

                            if (balanceSheet?.line_items) {
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
                            }

                            const netLongTerm = nonCurrentAssetsOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0) -
                              nonCurrentLiabilitiesOperating.reduce((sum, item) => sum + parseFloat(item.line_value || 0), 0)

                            return (
                              <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                <div style={{ marginBottom: '1.5rem' }}>

                                  <div className="balance-sheet-table-container">
                                    <table className="balance-sheet-table">
                                      <thead>
                                        <tr>
                                          <th className="col-name">Line Item</th>
                                          <th className="col-category">Category</th>
                                          <th className="col-type">Type</th>
                                          <th className="text-right col-value">Amount</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        <tr>
                                          <td colSpan="3" style={{ fontWeight: 600, paddingLeft: '1rem' }}>Current Assets (Operating)</td>
                                          <td className="text-right col-value"></td>
                                        </tr>
                                        {currentAssetsOperating.length > 0 ? currentAssetsOperating.map((item, idx) => (
                                          <tr key={`ca-${idx}`}>
                                            <td className="col-name" style={{ paddingLeft: '2rem' }}>{item.line_name}</td>
                                            <td className="col-category">{item.line_category || 'N/A'}</td>
                                            <td className="col-type">
                                              {item.is_operating === true ? (
                                                <span className="type-badge operating">Operating</span>
                                              ) : item.is_operating === false ? (
                                                <span className="type-badge non-operating">Non-Operating</span>
                                              ) : (
                                                <span className="text-muted">—</span>
                                              )}
                                            </td>
                                            <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                          </tr>
                                        )) : (
                                          <tr>
                                            <td colSpan="4" style={{ paddingLeft: '2rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating current assets found</td>
                                          </tr>
                                        )}
                                        <tr>
                                          <td colSpan="3" style={{ fontWeight: 600, paddingLeft: '1rem' }}>Current Liabilities (Operating)</td>
                                          <td className="text-right col-value"></td>
                                        </tr>
                                        {currentLiabilitiesOperating.length > 0 ? currentLiabilitiesOperating.map((item, idx) => (
                                          <tr key={`cl-${idx}`}>
                                            <td className="col-name" style={{ paddingLeft: '2rem' }}>{item.line_name}</td>
                                            <td className="col-category">{item.line_category || 'N/A'}</td>
                                            <td className="col-type">
                                              {item.is_operating === true ? (
                                                <span className="type-badge operating">Operating</span>
                                              ) : item.is_operating === false ? (
                                                <span className="type-badge non-operating">Non-Operating</span>
                                              ) : (
                                                <span className="text-muted">—</span>
                                              )}
                                            </td>
                                            <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                          </tr>
                                        )) : (
                                          <tr>
                                            <td colSpan="4" style={{ paddingLeft: '2rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating current liabilities found</td>
                                          </tr>
                                        )}
                                        <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 600 }}>
                                          <td colSpan="3" className="col-name">Total Current Assets (Operating)</td>
                                          <td className="text-right col-value">{formatNumber(currentAssetsTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                        </tr>
                                        <tr style={{ fontWeight: 600 }}>
                                          <td colSpan="3" className="col-name">Total Current Liabilities (Operating)</td>
                                          <td className="text-right col-value">{formatNumber(currentLiabilitiesTotal, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                        </tr>
                                        <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700, fontSize: '1.05rem' }}>
                                          <td colSpan="3" className="col-name">Net Working Capital</td>
                                          <td className="text-right col-value">{formatNumber(netWorkingCapital, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                        </tr>
                                      </tbody>
                                    </table>
                                  </div>
                                </div>

                                <div style={{ marginBottom: '1.5rem' }}>

                                  <div className="balance-sheet-table-container">
                                    <table className="balance-sheet-table">
                                      <thead>
                                        <tr>
                                          <th className="col-name">Line Item</th>
                                          <th className="col-category">Category</th>
                                          <th className="col-type">Type</th>
                                          <th className="text-right col-value">Amount</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        <tr>
                                          <td colSpan="3" style={{ fontWeight: 600, paddingLeft: '1rem' }}>Non-Current Assets (Operating)</td>
                                          <td className="text-right col-value"></td>
                                        </tr>
                                        {nonCurrentAssetsOperating.length > 0 ? nonCurrentAssetsOperating.map((item, idx) => (
                                          <tr key={`nca-${idx}`}>
                                            <td className="col-name" style={{ paddingLeft: '2rem' }}>{item.line_name}</td>
                                            <td className="col-category">{item.line_category || 'N/A'}</td>
                                            <td className="col-type">{item.is_operating === true ? 'Operating' : item.is_operating === false ? 'Non-Operating' : 'N/A'}</td>
                                            <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet.unit)}</td>
                                          </tr>
                                        )) : (
                                          <tr>
                                            <td colSpan="4" style={{ paddingLeft: '2rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating non-current assets found</td>
                                          </tr>
                                        )}
                                        <tr>
                                          <td colSpan="3" style={{ fontWeight: 600, paddingLeft: '1rem' }}>Non-Current Liabilities (Operating)</td>
                                          <td className="text-right col-value"></td>
                                        </tr>
                                        {nonCurrentLiabilitiesOperating.length > 0 ? nonCurrentLiabilitiesOperating.map((item, idx) => (
                                          <tr key={`ncl-${idx}`}>
                                            <td className="col-name" style={{ paddingLeft: '2rem' }}>{item.line_name}</td>
                                            <td className="col-category">{item.line_category || 'N/A'}</td>
                                            <td className="col-type">{item.is_operating === true ? 'Operating' : item.is_operating === false ? 'Non-Operating' : 'N/A'}</td>
                                            <td className="text-right col-value">{formatNumber(item.line_value, balanceSheet.unit)}</td>
                                          </tr>
                                        )) : (
                                          <tr>
                                            <td colSpan="4" style={{ paddingLeft: '2rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>No operating non-current liabilities found</td>
                                          </tr>
                                        )}
                                        <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 600 }}>
                                          <td colSpan="3" className="col-name">Net Long Term Operating Assets</td>
                                          <td className="text-right col-value">{formatNumber(netLongTerm, balanceSheet.unit)}</td>
                                        </tr>
                                      </tbody>
                                    </table>
                                  </div>
                                </div>

                                <div style={{ marginTop: '1.5rem', paddingTop: '1rem' }}>
                                  <div className="balance-sheet-table-container">
                                    <table className="balance-sheet-table">
                                      <tbody>
                                        <tr style={{ fontWeight: 600 }}>
                                          <td className="col-name">Net Working Capital</td>
                                          <td className="text-right col-value">{formatNumber(netWorkingCapital, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                        </tr>
                                        <tr style={{ fontWeight: 600 }}>
                                          <td className="col-name">+ Net Long Term Operating Assets</td>
                                          <td className="text-right col-value">{formatNumber(netLongTerm, balanceSheet?.unit || historicalCalculations?.unit)}</td>
                                        </tr>
                                        <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700, fontSize: '1.05rem' }}>
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
                        <div style={{ marginTop: '1.5rem' }}>

                          {(() => {
                            // Find operating income
                            let operatingIncome = null
                            let operatingIncomeItem = null
                            if (incomeStatement.line_items) {
                              for (const item of incomeStatement.line_items) {
                                if (item.line_name.includes('Operating Income (')) {
                                  operatingIncome = parseFloat(item.line_value || 0)
                                  operatingIncomeItem = item
                                  break
                                }
                              }
                              // Fallback search
                              if (operatingIncome === null) {
                                for (const item of incomeStatement.line_items) {
                                  const nameLower = item.line_name.toLowerCase()
                                  if ((nameLower.includes('operating income') || nameLower.includes('income from operations') || nameLower.includes('operating profit')) &&
                                    !nameLower.includes('total') && !nameLower.includes('subtotal')) {
                                    operatingIncome = parseFloat(item.line_value || 0)
                                    operatingIncomeItem = item
                                    break
                                  }
                                }
                              }
                            }

                            // Find revenue item
                            let revenueItem = null
                            if (incomeStatement.line_items) {
                              for (const item of incomeStatement.line_items) {
                                if (item.line_name.includes('Total Net Revenue')) {
                                  revenueItem = item
                                  break
                                }
                              }
                              if (!revenueItem) {
                                for (const item of incomeStatement.line_items) {
                                  const nameLower = item.line_name.toLowerCase()
                                  if ((nameLower.includes('revenue') || nameLower.includes('sales') || nameLower.includes('net sales')) && item.line_value > 0) {
                                    revenueItem = item
                                    break
                                  }
                                }
                              }
                            }

                            // Find non-operating items between revenue and operating income
                            const nonOperatingItems = []
                            if (incomeStatement.line_items && revenueItem && operatingIncomeItem) {
                              const sortedItems = [...incomeStatement.line_items].sort((a, b) => a.line_order - b.line_order)
                              for (const item of sortedItems) {
                                if (item.line_order > revenueItem.line_order && item.line_order < operatingIncomeItem.line_order) {
                                  if (item.is_operating === false) {
                                    nonOperatingItems.push(item)
                                  }
                                }
                              }
                            }

                            // Get amortization
                            const amortizationValue = incomeStatement.amortization ? parseFloat(incomeStatement.amortization) : null

                            const nonOperatingSum = nonOperatingItems.reduce((sum, item) => sum - parseFloat(item.line_value || 0), 0)
                            const ebitaCalc = operatingIncome + nonOperatingSum + (amortizationValue || 0)

                            return (
                              <div className="balance-sheet-container" style={{ marginTop: '1rem' }}>
                                <div className="balance-sheet-table-container">
                                  <table className="balance-sheet-table">
                                    <thead>
                                      <tr>
                                        <th className="col-name">Line Item</th>
                                        <th className="col-category">Category</th>
                                        <th className="col-type">Type</th>
                                        <th className="text-right col-value">Amount</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {operatingIncomeItem && (
                                        <tr>
                                          <td className="col-name">{operatingIncomeItem.line_name}</td>
                                          <td className="col-category">{operatingIncomeItem.line_category || 'N/A'}</td>
                                          <td className="col-type">{operatingIncomeItem.is_operating === true ? 'Operating' : operatingIncomeItem.is_operating === false ? 'Non-Operating' : 'N/A'}</td>
                                          <td className="text-right col-value">{formatNumber(operatingIncome, incomeStatement.unit)}</td>
                                        </tr>
                                      )}
                                      {nonOperatingItems.length > 0 && (
                                        <>
                                          <tr>
                                            <td colSpan="4" style={{ fontWeight: 600, paddingLeft: '1rem', paddingTop: '0.5rem' }}>Non-Operating Items (between Revenue and Operating Income)</td>
                                          </tr>
                                          {nonOperatingItems.map((item, idx) => (
                                            <tr key={`no-${idx}`}>
                                              <td className="col-name" style={{ paddingLeft: '2rem' }}>{item.line_name}</td>
                                              <td className="col-category">{item.line_category || 'N/A'}</td>
                                              <td className="col-type">{item.is_operating === false ? 'Non-Operating' : 'N/A'}</td>
                                              <td className="text-right col-value">{formatNumber(-item.line_value, incomeStatement.unit)}</td>
                                            </tr>
                                          ))}
                                          <tr>
                                            <td colSpan="3" style={{ paddingLeft: '2rem', fontStyle: 'italic' }}>Sum of Non-Operating Items</td>
                                            <td className="text-right col-value">{formatNumber(nonOperatingSum, incomeStatement.unit)}</td>
                                          </tr>
                                        </>
                                      )}
                                      {amortizationValue !== null && (
                                        <tr>
                                          <td className="col-name">Amortization</td>
                                          <td className="col-category">N/A</td>
                                          <td className="col-type">N/A</td>
                                          <td className="text-right col-value">{formatNumber(amortizationValue, incomeStatement.amortization_unit || incomeStatement.unit)}</td>
                                        </tr>
                                      )}
                                      <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700, fontSize: '1.05rem' }}>
                                        <td colSpan="3" className="col-name">= EBITA</td>
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

                      <div style={{ marginTop: '1.5rem' }}>

                        <p className="placeholder-text">NOPAT and ROIC calculations will appear here.</p>
                      </div>

                      <div style={{ marginTop: '1.5rem' }}>
                        <p className="placeholder-text">Adjusted tax rate breakdown will appear here.</p>
                      </div>

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
                                  <th>Metric</th>
                                  <th className="text-right">Amount</th>
                                  <th>Unit</th>
                                </tr>
                              </thead>
                              <tbody>
                                {organicGrowth && organicGrowth.current_period_revenue != null && (
                                  <tr>
                                    <td>Revenue</td>
                                    <td className="text-right">{formatNumber(organicGrowth.current_period_revenue, organicGrowth.current_period_revenue_unit)}</td>
                                    <td>{organicGrowth.current_period_revenue_unit ? organicGrowth.current_period_revenue_unit.replace('_', ' ') : 'N/A'}</td>
                                  </tr>
                                )}
                                {incomeStatement && incomeStatement.revenue_growth_yoy != null && (
                                  <tr>
                                    <td>YOY Revenue Growth</td>
                                    <td className="text-right">{formatPercent(incomeStatement.revenue_growth_yoy, 1)}</td>
                                    <td>—</td>
                                  </tr>
                                )}
                                {organicGrowth && organicGrowth.organic_revenue_growth != null && (
                                  <tr>
                                    <td>Organic Growth</td>
                                    <td className="text-right">{formatPercent(organicGrowth.organic_revenue_growth, 1)}</td>
                                    <td>—</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.ebita != null && (
                                  <tr>
                                    <td>EBITA</td>
                                    <td className="text-right">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                    <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.ebita_margin != null && (
                                  <tr>
                                    <td>EBITA Margin</td>
                                    <td className="text-right">{formatPercent(historicalCalculations.ebita_margin, 100)}</td>
                                    <td>—</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.adjusted_tax_rate != null && (
                                  <tr>
                                    <td>Adjusted Tax Rate</td>
                                    <td className="text-right">{formatPercent(historicalCalculations.adjusted_tax_rate, 100)}</td>
                                    <td>—</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.net_working_capital != null && (
                                  <tr>
                                    <td>Net Working Capital</td>
                                    <td className="text-right">{formatNumber(historicalCalculations.net_working_capital, historicalCalculations.unit)}</td>
                                    <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.net_long_term_operating_assets != null && (
                                  <tr>
                                    <td>Net Long Term Operating Assets</td>
                                    <td className="text-right">{formatNumber(historicalCalculations.net_long_term_operating_assets, historicalCalculations.unit)}</td>
                                    <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.invested_capital != null && (
                                  <tr>
                                    <td>Invested Capital</td>
                                    <td className="text-right">{formatNumber(historicalCalculations.invested_capital, historicalCalculations.unit)}</td>
                                    <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                  </tr>
                                )}
                                {historicalCalculations && historicalCalculations.capital_turnover != null && (
                                  <tr>
                                    <td>Capital Turnover, Annualized</td>
                                    <td className="text-right">{formatDecimal(historicalCalculations.capital_turnover, 4)}</td>
                                    <td>—</td>
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
            </>
          )}
        </div>
      </div>
    )
  }

  if (selectedCompany) {
    const companyEntries = companyHistoricalCalculations?.entries || []
    const hasCompanyData = companyEntries.length > 0
    const timePeriods = companyEntries.map((entry) => entry.time_period)

    const rows = [
      {
        label: 'Revenue',
        render: (entry) => formatNumber(entry.revenue, companyHistoricalCalculations?.unit)
      },
      {
        label: 'YOY Revenue Growth',
        render: (entry) => formatPercent(entry.revenue_growth_yoy, 1)
      },
      {
        label: 'EBITA',
        render: (entry) => formatNumber(entry.ebita, companyHistoricalCalculations?.unit)
      },
      {
        label: 'EBITA Margin',
        render: (entry) => formatPercent(entry.ebita_margin, 100)
      },
      {
        label: 'Effective Tax Rate',
        render: (entry) => formatPercent(entry.effective_tax_rate, 100)
      },
      {
        label: 'Adjusted Tax Rate',
        render: (entry) => formatPercent(entry.adjusted_tax_rate, 100)
      },
      {
        label: 'Net Working Capital',
        render: (entry) =>
          formatNumber(entry.net_working_capital, companyHistoricalCalculations?.unit)
      },
      {
        label: 'Net Long Term Operating Assets',
        render: (entry) =>
          formatNumber(entry.net_long_term_operating_assets, companyHistoricalCalculations?.unit)
      },
      {
        label: 'Invested Capital',
        render: (entry) => formatNumber(entry.invested_capital, companyHistoricalCalculations?.unit)
      },
      {
        label: 'Capital Turnover, Annualized',
        render: (entry) => formatDecimal(entry.capital_turnover, 4)
      }
    ]

    return (
      <div className="right-panel">
        <div className="panel-content">
          <h2>{selectedCompany.name} Analysis</h2>
          <div className="company-analysis">
            {companyHistoricalLoading && (
              <p className="placeholder-text">Loading historical calculations...</p>
            )}
            {companyHistoricalError && (
              <p className="placeholder-text">{companyHistoricalError}</p>
            )}
            {!companyHistoricalLoading && !companyHistoricalError && hasCompanyData && (
              <div className="balance-sheet-container">
                <div className="balance-sheet-header">
                  <h3>Historical Calculations</h3>
                  <div className="balance-sheet-meta">
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
                <div className="balance-sheet-table-container">
                  <table className="balance-sheet-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        {timePeriods.map((period) => (
                          <th key={period} className="text-right">{period}</th>
                        ))}
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
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

  return (
    <div className="right-panel">
      <div className="panel-content">
        <h2>Latest Analyses</h2>
        <div className="home-content">
          <p className="placeholder-text">
            Latest completed company analyses will be displayed here.
          </p>
        </div>
      </div>
    </div>
  )
}

export default RightPanel
