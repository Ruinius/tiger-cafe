import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './RightPanel.css'

function RightPanel({ selectedCompany, selectedDocument }) {
  const API_BASE_URL = 'http://localhost:8000/api'
  const { isAuthenticated, token } = useAuth()
  const [balanceSheet, setBalanceSheet] = useState(null)
  const [incomeStatement, setIncomeStatement] = useState(null)
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
    if (!selectedDocument || balanceSheetLoadAttempts >= MAX_LOAD_ATTEMPTS) return
    
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
  }, [selectedDocument, isAuthenticated, token, balanceSheetLoadAttempts])

  const loadIncomeStatement = useCallback(async () => {
    if (!selectedDocument || incomeStatementLoadAttempts >= MAX_LOAD_ATTEMPTS) return
    
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
  }, [selectedDocument, isAuthenticated, token, incomeStatementLoadAttempts])

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
    }
  }, [financialStatementProgress, selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

  // Load balance sheet and income statement only when all milestones are terminal
  useEffect(() => {
    if (!selectedDocument || !isEligibleForFinancialStatements) return
    
    // Only load if all milestones are in terminal state (completed or error)
    if (areAllMilestonesTerminal() && balanceSheetLoadAttempts < MAX_LOAD_ATTEMPTS) {
      loadBalanceSheet()
    }
    
    if (areAllMilestonesTerminal() && incomeStatementLoadAttempts < MAX_LOAD_ATTEMPTS) {
      loadIncomeStatement()
    }
  }, [areAllMilestonesTerminal, selectedDocument?.id, balanceSheetLoadAttempts, incomeStatementLoadAttempts, loadBalanceSheet, loadIncomeStatement])

  const formatCurrency = (value, currency = 'USD') => {
    if (value === null || value === undefined) return 'N/A'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(parseFloat(value))
  }

  // Expose function to clear data (for re-run and delete buttons)
  useEffect(() => {
    // Listen for custom events to clear data
    const handleClearData = () => {
      setBalanceSheet(null)
      setIncomeStatement(null)
      setBalanceSheetLoadAttempts(0)
      setIncomeStatementLoadAttempts(0)
    }

    // Listen for event to reset progress to PENDING
    const handleResetProgressToPending = (event) => {
      const { documentId } = event.detail || {}
      // Only reset if it's for the current document
      if (documentId === selectedDocument?.id) {
        // Immediately set all milestones to PENDING
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
      }
    }

    // Listen for event to reload progress
    const handleReloadProgress = () => {
      if (selectedDocument && isEligibleForFinancialStatements) {
        // Immediately reload progress to start polling
        loadFinancialStatementProgress()
      }
    }

    window.addEventListener('clearFinancialStatements', handleClearData)
    window.addEventListener('resetProgressToPending', handleResetProgressToPending)
    window.addEventListener('reloadProgress', handleReloadProgress)
    return () => {
      window.removeEventListener('clearFinancialStatements', handleClearData)
      window.removeEventListener('resetProgressToPending', handleResetProgressToPending)
      window.removeEventListener('reloadProgress', handleReloadProgress)
    }
  }, [selectedDocument, isEligibleForFinancialStatements, loadFinancialStatementProgress])

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
                               status === 'in_progress' ? '⟳' : 
                               status === 'error' ? '✗' : 
                               status === 'checking' ? '⟳' :
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
                          {message && status !== 'pending' && (
                            <div style={{ 
                              marginTop: '0.25rem',
                              fontSize: '0.875rem',
                              color: 'var(--text-secondary)',
                              marginLeft: '1.75rem'
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
                                      <td className={`text-right ${isKeyTotal ? 'bold-text' : ''}`}>{formatCurrency(item.line_value, balanceSheet.currency)}</td>
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
                                  const isKeyTotal = lineNameLower.includes('gross profit') || 
                                                    lineNameLower.includes('operating income') || 
                                                    lineNameLower.includes('net income')
                                  
                                  return (
                                    <tr 
                                      key={item.id}
                                      className={isKeyTotal ? 'key-total-row' : ''}
                                    >
                                      <td className={isKeyTotal ? 'bold-text' : ''}>{item.line_name}</td>
                                      <td className={isKeyTotal ? 'bold-text' : ''}>{item.line_category || 'N/A'}</td>
                                      <td className={`text-right ${isKeyTotal ? 'bold-text' : ''}`}>{formatCurrency(item.line_value, incomeStatement.currency)}</td>
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
                                  </tr>
                                </thead>
                                <tbody>
                                  {incomeStatement.revenue_prior_year !== null && (
                                    <tr>
                                      <td>Prior Period Revenue</td>
                                      <td className="text-right">{formatCurrency(incomeStatement.revenue_prior_year, incomeStatement.currency)}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.revenue_growth_yoy !== null && (
                                    <tr>
                                      <td>YOY Revenue Growth</td>
                                      <td className="text-right">{incomeStatement.revenue_growth_yoy.toFixed(2)}%</td>
                                    </tr>
                                  )}
                                  {incomeStatement.amortization !== null && (
                                    <tr>
                                      <td>Amortization</td>
                                      <td className="text-right">{formatCurrency(incomeStatement.amortization, incomeStatement.currency)}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.basic_shares_outstanding !== null && (
                                    <tr>
                                      <td>Basic Shares Outstanding</td>
                                      <td className="text-right">{incomeStatement.basic_shares_outstanding.toLocaleString()}</td>
                                    </tr>
                                  )}
                                  {incomeStatement.diluted_shares_outstanding !== null && (
                                    <tr>
                                      <td>Diluted Shares Outstanding</td>
                                      <td className="text-right">{incomeStatement.diluted_shares_outstanding.toLocaleString()}</td>
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
                </>
              )}
            </>
          )}
        </div>
      </div>
    )
  }

  if (selectedCompany) {
    return (
      <div className="right-panel">
        <div className="panel-content">
          <h2>{selectedCompany.name} Analysis</h2>
          <div className="company-analysis">
            <p className="placeholder-text">
              Company analysis will be displayed here once financial analysis is completed.
            </p>
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
