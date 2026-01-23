import React, { useEffect } from 'react'
import { useAuth } from '../../../contexts/AuthContext'
import { useAnalysisEvents } from '../../../hooks/useAnalysisEvents'
import { useFinancialStatements } from '../../../hooks/useFinancialStatements'
import { useHistoricalCalculations } from '../../../hooks/useHistoricalCalculations'
import { useFinancialStatementProgress } from '../../../hooks/useFinancialStatementProgress'

import { formatNumber } from '../../../utils/formatting'
import './Document.css'
import BalanceSheetTable from '../../tables/BalanceSheetTable'
import IncomeStatementTable from '../../tables/IncomeStatementTable'
import OrganicGrowthTable from '../../tables/OrganicGrowthTable'
import SharesOutstandingTable from '../../tables/SharesOutstandingTable'
import InvestedCapitalTable from '../../tables/InvestedCapitalTable'
import EBITATable from '../../tables/EBITATable'
import AdjustedTaxTable from '../../tables/AdjustedTaxTable'
import NopatRoicTable from '../../tables/NopatRoicTable'
import SummaryTable from '../../tables/SummaryTable'
import NonGaapTable from '../../tables/NonGaapTable'
import NonOperatingClassificationTable from '../../tables/NonOperatingClassificationTable'

function DocumentExtractionView({ selectedDocument }) {
    const { isAuthenticated } = useAuth() // Used for entitlement checks if needed, tokens handled in hooks

    const isEligibleForFinancialStatements = selectedDocument &&
        ['earnings_announcement', 'quarterly_filing', 'annual_filing'].includes(selectedDocument.document_type?.toLowerCase())

    // Hooks
    const {
        financialStatementProgress,
        areAllMilestonesTerminal,
        loadFinancialStatementProgress,
        resetProgress,
        setProgress
    } = useFinancialStatementProgress(selectedDocument, isEligibleForFinancialStatements)

    const {
        balanceSheet,
        incomeStatement,
        organicGrowth,
        amortization,
        otherAssets,
        otherLiabilities,
        nonOperatingClassification,
        balanceSheetLoadAttempts,
        incomeStatementLoadAttempts,
        additionalItemsLoadAttempted,
        setAdditionalItemsLoadAttempted,
        loadBalanceSheet,
        loadIncomeStatement,
        loadAdditionalItems,
        clearFinancialStatements,
        MAX_LOAD_ATTEMPTS
    } = useFinancialStatements(selectedDocument, isEligibleForFinancialStatements)

    const {
        historicalCalculations,
        historicalCalculationsLoadAttempted,
        setHistoricalCalculationsLoadAttempted,
        loadHistoricalCalculations,
        clearHistoricalCalculations
    } = useHistoricalCalculations(selectedDocument, isEligibleForFinancialStatements)

    // Event Listeners
    const eventHandlers = React.useMemo(() => ({
        onProcessingComplete: () => {
            // Handled by polling effect in useFinancialStatementProgress
        },
        onClearData: () => {
            clearFinancialStatements()
            clearHistoricalCalculations()
            resetProgress() // Local state reset
        },
        onReloadHistorical: () => {
            if (selectedDocument && isEligibleForFinancialStatements) {
                clearHistoricalCalculations()
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
                setProgress({
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
    }), [
        selectedDocument?.id,
        isEligibleForFinancialStatements,
        clearFinancialStatements,
        clearHistoricalCalculations,
        resetProgress,
        loadHistoricalCalculations,
        setHistoricalCalculationsLoadAttempted,
        loadFinancialStatementProgress,
        setProgress
    ])

    useAnalysisEvents(eventHandlers)

    // Coordination: Data Loading when milestones complete
    useEffect(() => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        if (!areAllMilestonesTerminal()) return

        const bsStatus = financialStatementProgress?.milestones?.balance_sheet?.status
        if (balanceSheetLoadAttempts < MAX_LOAD_ATTEMPTS && !balanceSheet) {
            if (bsStatus === 'completed' || bsStatus === 'error') {
                loadBalanceSheet()
            }
        }

        const isStatus = financialStatementProgress?.milestones?.income_statement?.status
        if (incomeStatementLoadAttempts < MAX_LOAD_ATTEMPTS && !incomeStatement) {
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
        financialStatementProgress,
        balanceSheet,
        incomeStatement,
        additionalItemsLoadAttempted,
        balanceSheetLoadAttempts,
        incomeStatementLoadAttempts,
        loadBalanceSheet,
        loadIncomeStatement,
        loadAdditionalItems,
        setAdditionalItemsLoadAttempted,
        MAX_LOAD_ATTEMPTS,
        isEligibleForFinancialStatements
    ])

    // Coordination: Historical Calculations Loading
    useEffect(() => {
        if (!selectedDocument || !isEligibleForFinancialStatements) return
        if (areAllMilestonesTerminal() && balanceSheet && incomeStatement && !historicalCalculationsLoadAttempted) {
            setHistoricalCalculationsLoadAttempted(true)
            loadHistoricalCalculations()
        }
    }, [
        areAllMilestonesTerminal,
        selectedDocument,
        isEligibleForFinancialStatements,
        balanceSheet,
        incomeStatement,
        historicalCalculationsLoadAttempted,
        loadHistoricalCalculations,
        setHistoricalCalculationsLoadAttempted
    ])

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
                        {/* Validation Banner */}
                        {financialStatementProgress && areAllMilestonesTerminal() && (
                            <div className="info-section">
                                {(() => {
                                    const milestones = financialStatementProgress.milestones || {}
                                    const errors = []
                                    const warnings = []

                                    // Collect errors and warnings from milestones
                                    Object.entries(milestones).forEach(([key, milestone]) => {
                                        if (milestone.status === 'error') {
                                            errors.push({
                                                milestone: key.replace(/_/g, ' '),
                                                message: milestone.message || 'Processing failed'
                                            })
                                        }
                                        // Check for warning messages in logs
                                        if (milestone.logs) {
                                            milestone.logs.forEach(log => {
                                                if (log.message && log.message.toLowerCase().includes('(warning)')) {
                                                    warnings.push({
                                                        milestone: key.replace(/_/g, ' '),
                                                        message: log.message.replace(' (Warning)', '')
                                                    })
                                                }
                                            })
                                        }
                                    })

                                    if (errors.length > 0) {
                                        return (
                                            <div className="validation-banner error">
                                                <div className="banner-header">
                                                    <span className="banner-icon">✗</span>
                                                    <h4>Processing Errors</h4>
                                                </div>
                                                <ul className="banner-list">
                                                    {errors.map((error, idx) => (
                                                        <li key={idx}>
                                                            <strong>{error.milestone}:</strong> {error.message}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )
                                    }

                                    if (warnings.length > 0) {
                                        return (
                                            <div className="validation-banner warning">
                                                <div className="banner-header">
                                                    <span className="banner-icon">⚠</span>
                                                    <h4>Processing Warnings</h4>
                                                </div>
                                                <ul className="banner-list">
                                                    {warnings.map((warning, idx) => (
                                                        <li key={idx}>
                                                            <strong>{warning.milestone}:</strong> {warning.message}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )
                                    }

                                    return null
                                })()}
                            </div>
                        )}

                        {showNothingMessage && (
                            <div className="info-section">
                                <p className="info-text">
                                    Document processing complete, but no financial tables could be extracted.
                                </p>
                            </div>
                        )}

                        {/* Extractions */}
                        {balanceSheet && (
                            <div className="extraction-section">
                                <h3>Balance Sheet</h3>
                                <BalanceSheetTable
                                    data={balanceSheet}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}

                        {incomeStatement && (
                            <div className="extraction-section">
                                <h3>Income Statement</h3>
                                <IncomeStatementTable
                                    data={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}

                        {/* Additional Tables */}
                        {organicGrowth && (
                            <div className="extraction-section">
                                <h3>Organic Revenue Growth</h3>
                                <OrganicGrowthTable
                                    data={organicGrowth}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}

                        {amortization && (
                            <div className="extraction-section">
                                <h3>Non-GAAP Reconciliation</h3>
                                <NonGaapTable
                                    data={amortization}
                                    formatNumber={formatNumber}
                                    currency={balanceSheet?.currency || incomeStatement?.currency}
                                    unit={balanceSheet?.unit || incomeStatement?.unit}
                                />
                            </div>
                        )}

                        {incomeStatement && (
                            <div className="extraction-section">
                                <h3>Shares Outstanding</h3>
                                <SharesOutstandingTable
                                    incomeStatement={incomeStatement}
                                />
                            </div>
                        )}

                        {nonOperatingClassification && (
                            <div className="extraction-section">
                                <h3>Non-Operating Items Classification</h3>
                                <NonOperatingClassificationTable
                                    data={nonOperatingClassification}
                                    formatNumber={formatNumber}
                                    currency={balanceSheet?.currency}
                                    unit={balanceSheet?.unit}
                                />
                            </div>
                        )}

                        {/* Historical Calculations Section */}
                        {historicalCalculations && (
                            <div style={{
                                marginTop: '3rem',
                                borderTop: '2px solid var(--border)',
                                paddingTop: '3rem',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '2rem'
                            }}>
                                <InvestedCapitalTable
                                    historicalCalculations={historicalCalculations}
                                    balanceSheet={balanceSheet}
                                    formatNumber={formatNumber}
                                />
                                <hr className="calc-section-divider" />
                                <EBITATable
                                    historicalCalculations={historicalCalculations}
                                    incomeStatement={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                                <AdjustedTaxTable
                                    historicalCalculations={historicalCalculations}
                                    incomeStatement={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                                <NopatRoicTable
                                    historicalCalculations={historicalCalculations}
                                    incomeStatement={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                                <hr className="calc-section-divider" />
                                <SummaryTable
                                    historicalCalculations={historicalCalculations}
                                    organicGrowth={organicGrowth}
                                    incomeStatement={incomeStatement}
                                    formatNumber={formatNumber}
                                />
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

export default DocumentExtractionView
