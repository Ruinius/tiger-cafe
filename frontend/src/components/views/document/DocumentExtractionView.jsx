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
