import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './RightPanel.css'

function RightPanel({ selectedCompany, selectedDocument }) {
  const API_BASE_URL = 'http://localhost:8000/api'
  const { isAuthenticated, token } = useAuth()
  const [balanceSheet, setBalanceSheet] = useState(null)
  const [incomeStatement, setIncomeStatement] = useState(null)
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
    
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${selectedDocument.id}/balance-sheet`,
        { headers }
      )
      
      if (response.data && response.data.status === 'exists') {
        setBalanceSheet(response.data.data)
        setBalanceSheetLoadAttempts(0) // Reset attempts on success
      } else {
        setBalanceSheet(null)
        setBalanceSheetLoadAttempts(prev => prev + 1)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setBalanceSheet(null)
        setBalanceSheetLoadAttempts(prev => prev + 1)
      } else {
        setError(err.response?.data?.detail || 'Failed to load balance sheet')
        setBalanceSheetLoadAttempts(prev => prev + 1)
      }
    }
  }, [selectedDocument, isAuthenticated, token])

  const loadIncomeStatement = useCallback(async () => {
    if (!selectedDocument) return
    
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${selectedDocument.id}/income-statement`,
        { headers }
      )
      
      if (response.data && response.data.status === 'exists') {
        setIncomeStatement(response.data.data)
        setIncomeStatementLoadAttempts(0) // Reset attempts on success
      } else {
        setIncomeStatement(null)
        setIncomeStatementLoadAttempts(prev => prev + 1)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setIncomeStatement(null)
        setIncomeStatementLoadAttempts(prev => prev + 1)
      } else {
        setError(err.response?.data?.detail || 'Failed to load income statement')
        setIncomeStatementLoadAttempts(prev => prev + 1)
      }
    }
  }, [selectedDocument, isAuthenticated, token])

  // Load progress tracker first when document is selected
  useEffect(() => {
    // Reset state when document changes
    setFinancialStatementProgress(null)
    setBalanceSheet(null)
    setIncomeStatement(null)
    setError(null)
    setBalanceSheetLoadAttempts(0)
    setIncomeStatementLoadAttempts(0)
    
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
    
    // Only load if attempts haven't exceeded max and data isn't already loaded
    if (balanceSheetLoadAttempts < MAX_LOAD_ATTEMPTS && !balanceSheet) {
      loadBalanceSheet()
    }
    
    if (incomeStatementLoadAttempts < MAX_LOAD_ATTEMPTS && !incomeStatement) {
      loadIncomeStatement()
    }
  }, [areAllMilestonesTerminal, selectedDocument?.id, balanceSheetLoadAttempts, incomeStatementLoadAttempts, balanceSheet, incomeStatement, loadBalanceSheet, loadIncomeStatement])

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
      setHistoricalCalculations(null)
      setHistoricalCalculationsLoadAttempted(false)
      setBalanceSheetLoadAttempts(0)
      setIncomeStatementLoadAttempts(0)
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
            extracting_balance_sheet: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            classifying_balance_sheet: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            extracting_income_statement: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            extracting_additional_items: {
              status: 'pending',
              message: 'Waiting to start...',
              updated_at: new Date().toISOString()
            },
            classifying_income_statement: {
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
              <p className="info-text">
                Financial statement processing is only available for earnings announcements, quarterly filings, and annual reports.
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
                      { key: 'extracting_balance_sheet', label: 'Extracting Balance Sheet' },
                      { key: 'classifying_balance_sheet', label: 'Classifying Balance Sheet' },
                      { key: 'extracting_income_statement', label: 'Extracting Income Statement' },
                      { key: 'extracting_additional_items', label: 'Extracting Additional Items' },
                      { key: 'classifying_income_statement', label: 'Classifying Income Statement' }
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
                                <th>Type</th>
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
                                      <td>
                                        <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                          {item.is_operating ? 'Operating' : 'Non-Operating'}
                                        </span>
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
                                <th>Type</th>
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
                                      <td>
                                        {item.line_category ? (
                                          <span className={`type-badge ${item.line_category.toLowerCase() === 'one-time' ? 'non-operating' : 'operating'}`}>
                                            {item.line_category}
                                          </span>
                                        ) : (
                                          'N/A'
                                        )}
                                      </td>
                                      <td className={`text-right ${isKeyTotal ? 'bold-text' : ''}`}>{formatNumber(item.line_value, incomeStatement.unit)}</td>
                                      <td>
                                        <span className={`type-badge ${item.is_operating ? 'operating' : 'non-operating'}`}>
                                          {item.is_operating ? 'Operating' : 'Non-Operating'}
                                        </span>
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

                        {/* Additional Items Table */}
                        {(incomeStatement.revenue_prior_year !== null || 
                           incomeStatement.revenue_growth_yoy !== null || 
                           incomeStatement.amortization !== null || 
                           incomeStatement.basic_shares_outstanding !== null || 
                           incomeStatement.diluted_shares_outstanding !== null) && (
                          <div style={{ marginTop: '2rem' }}>
                            <h4>Additional Items</h4>
                            <div className="balance-sheet-table-container">
                              <table className="balance-sheet-table">
                                <thead>
                                  <tr>
                                    <th>Item</th>
                                    <th className="text-right">Value</th>
                                    <th>Unit</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {incomeStatement.revenue_prior_year !== null && (
                                    <tr>
                                      <td>Prior Period Revenue</td>
                                      <td className="text-right">{formatNumber(incomeStatement.revenue_prior_year, incomeStatement.revenue_prior_year_unit)}</td>
                                      <td>{incomeStatement.revenue_prior_year_unit ? incomeStatement.revenue_prior_year_unit.replace('_', ' ') : 'N/A'}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.revenue_growth_yoy !== null && (
                                    <tr>
                                      <td>YOY Revenue Growth</td>
                                      <td className="text-right">{incomeStatement.revenue_growth_yoy.toFixed(2)}%</td>
                                      <td>—</td>
                                    </tr>
                                  )}
                                  {incomeStatement.amortization !== null && (
                                    <tr>
                                      <td>Amortization</td>
                                      <td className="text-right">{formatNumber(incomeStatement.amortization, incomeStatement.amortization_unit)}</td>
                                      <td>{incomeStatement.amortization_unit ? incomeStatement.amortization_unit.replace('_', ' ') : 'N/A'}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.basic_shares_outstanding !== null && (
                                    <tr>
                                      <td>Basic Shares Outstanding</td>
                                      <td className="text-right">{incomeStatement.basic_shares_outstanding.toLocaleString()}</td>
                                      <td>{incomeStatement.basic_shares_outstanding_unit ? incomeStatement.basic_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.diluted_shares_outstanding !== null && (
                                    <tr>
                                      <td>Diluted Shares Outstanding</td>
                                      <td className="text-right">{incomeStatement.diluted_shares_outstanding.toLocaleString()}</td>
                                      <td>{incomeStatement.diluted_shares_outstanding_unit ? incomeStatement.diluted_shares_outstanding_unit.replace('_', ' ') : 'N/A'}</td>
                                    </tr>
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Historical Calculations Section */}
                  {historicalCalculations && (
                    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '2rem' }}>
                      <h3>Historical Calculations</h3>
                      <div className="balance-sheet-container">
                        <div className="balance-sheet-table-container">
                          <table className="balance-sheet-table">
                            <thead>
                              <tr>
                                <th>Metric</th>
                                <th className="text-right">Value</th>
                                <th>Unit</th>
                              </tr>
                            </thead>
                            <tbody>
                              {historicalCalculations.net_working_capital !== null && (
                                <tr>
                                  <td>Net Working Capital</td>
                                  <td className="text-right">{formatNumber(historicalCalculations.net_working_capital, historicalCalculations.unit)}</td>
                                  <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                </tr>
                              )}
                              {historicalCalculations.net_long_term_operating_assets !== null && (
                                <tr>
                                  <td>Net Long Term Operating Assets</td>
                                  <td className="text-right">{formatNumber(historicalCalculations.net_long_term_operating_assets, historicalCalculations.unit)}</td>
                                  <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                </tr>
                              )}
                              {historicalCalculations.invested_capital !== null && (
                                <tr>
                                  <td>Invested Capital</td>
                                  <td className="text-right">{formatNumber(historicalCalculations.invested_capital, historicalCalculations.unit)}</td>
                                  <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                </tr>
                              )}
                              {historicalCalculations.capital_turnover !== null && (
                                <tr>
                                  <td>Capital Turnover, Annualized</td>
                                  <td className="text-right">{parseFloat(historicalCalculations.capital_turnover).toFixed(4)}</td>
                                  <td>—</td>
                                </tr>
                              )}
                              {historicalCalculations.ebita !== null && (
                                <tr>
                                  <td>EBITA</td>
                                  <td className="text-right">{formatNumber(historicalCalculations.ebita, historicalCalculations.unit)}</td>
                                  <td>{historicalCalculations.unit ? historicalCalculations.unit.replace('_', ' ') : 'N/A'}</td>
                                </tr>
                              )}
                              {historicalCalculations.ebita_margin !== null && (
                                <tr>
                                  <td>EBITA Margin</td>
                                  <td className="text-right">{(parseFloat(historicalCalculations.ebita_margin) * 100).toFixed(2)}%</td>
                                  <td>—</td>
                                </tr>
                              )}
                              {historicalCalculations.effective_tax_rate !== null && (
                                <tr>
                                  <td>Effective Tax Rate</td>
                                  <td className="text-right">{(parseFloat(historicalCalculations.effective_tax_rate) * 100).toFixed(2)}%</td>
                                  <td>—</td>
                                </tr>
                              )}
                              {historicalCalculations.adjusted_tax_rate !== null && (
                                <tr>
                                  <td>Adjusted Tax Rate</td>
                                  <td className="text-right">{(parseFloat(historicalCalculations.adjusted_tax_rate) * 100).toFixed(2)}%</td>
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
