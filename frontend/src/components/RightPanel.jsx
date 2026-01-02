import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './RightPanel.css'

function RightPanel({ selectedCompany, selectedDocument }) {
  const API_BASE_URL = 'http://localhost:8000/api'
  const { isAuthenticated, token } = useAuth()
  const [balanceSheet, setBalanceSheet] = useState(null)
  const [loadingBalanceSheet, setLoadingBalanceSheet] = useState(false)
  const [processingBalanceSheet, setProcessingBalanceSheet] = useState(false)
  const [error, setError] = useState(null)

  // Check if document is eligible for balance sheet processing
  const isEligibleForBalanceSheet = selectedDocument && 
    ['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type)

  // Fetch balance sheet when document is selected
  useEffect(() => {
    if (selectedDocument && isEligibleForBalanceSheet) {
      loadBalanceSheet()
      // Poll for balance sheet updates if processing
      const interval = setInterval(() => {
        if (selectedDocument.analysis_status === 'processing') {
          loadBalanceSheet()
        }
      }, 2000)
      return () => clearInterval(interval)
    } else {
      setBalanceSheet(null)
    }
  }, [selectedDocument?.id, selectedDocument?.analysis_status])

  const loadBalanceSheet = async () => {
    if (!selectedDocument) return
    
    setLoadingBalanceSheet(true)
    setError(null)
    
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${selectedDocument.id}/balance-sheet`,
        { headers }
      )
      setBalanceSheet(response.data)
    } catch (err) {
      if (err.response?.status === 404) {
        // Balance sheet not found yet - this is okay
        setBalanceSheet(null)
      } else {
        setError(err.response?.data?.detail || 'Failed to load balance sheet')
      }
    } finally {
      setLoadingBalanceSheet(false)
    }
  }

  const handleProcessBalanceSheet = async () => {
    if (!selectedDocument) return
    
    setProcessingBalanceSheet(true)
    setError(null)
    
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      await axios.post(
        `${API_BASE_URL}/documents/${selectedDocument.id}/process-balance-sheet`,
        {},
        { headers }
      )
      // Start polling for balance sheet
      const interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `${API_BASE_URL}/documents/${selectedDocument.id}/balance-sheet`,
            { headers }
          )
          setBalanceSheet(response.data)
          if (response.data && response.data.is_valid) {
            clearInterval(interval)
            setProcessingBalanceSheet(false)
          }
        } catch (err) {
          // Still processing
        }
      }, 2000)
      
      // Stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(interval)
        setProcessingBalanceSheet(false)
      }, 300000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process balance sheet')
      setProcessingBalanceSheet(false)
    }
  }

  const formatCurrency = (value, currency = 'USD') => {
    if (value === null || value === undefined) return 'N/A'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(parseFloat(value))
  }

  if (selectedDocument) {
    const isProcessing = selectedDocument.analysis_status === 'processing' || processingBalanceSheet
    const hasBalanceSheet = balanceSheet !== null

    return (
      <div className="right-panel">
        <div className="panel-content">
          <h2>Balance Sheet</h2>
          
          {!isEligibleForBalanceSheet && (
            <div className="info-section">
              <p className="info-text">
                Balance sheet processing is only available for earnings announcements, quarterly filings, and annual reports.
              </p>
            </div>
          )}

          {isEligibleForBalanceSheet && (
            <>
              {!hasBalanceSheet && !isProcessing && (
                <div className="info-section">
                  <p className="info-text">
                    Balance sheet has not been extracted yet. Click the button below to start processing.
                  </p>
                  <button 
                    className="process-button"
                    onClick={handleProcessBalanceSheet}
                    disabled={processingBalanceSheet || selectedDocument.indexing_status !== 'indexed'}
                  >
                    {processingBalanceSheet ? 'Processing...' : 'Process Balance Sheet'}
                  </button>
                  {selectedDocument.indexing_status !== 'indexed' && (
                    <p className="info-text-small">
                      Document must be indexed before balance sheet processing can begin.
                    </p>
                  )}
                </div>
              )}

              {isProcessing && !hasBalanceSheet && (
                <div className="info-section">
                  <div className="processing-indicator">
                    <div className="spinner"></div>
                    <p>Processing balance sheet...</p>
                  </div>
                </div>
              )}

              {error && (
                <div className="error-section">
                  <p className="error-text">{error}</p>
                </div>
              )}

              {hasBalanceSheet && (
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

