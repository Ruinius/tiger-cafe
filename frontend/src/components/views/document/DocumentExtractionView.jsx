import React, { useEffect, useRef } from 'react'
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
        shares,
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

        // DEBUG: Log all milestone statuses
        console.log('[DocumentExtractionView] DEBUG - Milestone Statuses:', {
            balance_sheet: financialStatementProgress?.milestones?.balance_sheet?.status,
            income_statement: financialStatementProgress?.milestones?.income_statement?.status,
            shares_outstanding: financialStatementProgress?.milestones?.shares_outstanding?.status,
            overall_status: financialStatementProgress?.status
        })
        console.log('[DocumentExtractionView] DEBUG - Current State:', {
            balanceSheet: balanceSheet ? 'LOADED' : 'NULL',
            incomeStatement: incomeStatement ? 'LOADED' : 'NULL',
            balanceSheetLoadAttempts,
            incomeStatementLoadAttempts,
            MAX_LOAD_ATTEMPTS
        })

        const bsStatus = financialStatementProgress?.milestones?.balance_sheet?.status
        if (balanceSheetLoadAttempts < MAX_LOAD_ATTEMPTS && !balanceSheet) {
            console.log('[DocumentExtractionView] DEBUG - BS Check:', {
                bsStatus,
                shouldLoad: bsStatus === 'completed' || bsStatus === 'error' || bsStatus === 'warning'
            })
            if (bsStatus === 'completed' || bsStatus === 'error' || bsStatus === 'warning') {
                console.log('[DocumentExtractionView] Calling loadBalanceSheet()')
                loadBalanceSheet()
            }
        }

        const isStatus = financialStatementProgress?.milestones?.income_statement?.status
        if (incomeStatementLoadAttempts < MAX_LOAD_ATTEMPTS && !incomeStatement) {
            console.log('[DocumentExtractionView] DEBUG - IS Check:', {
                isStatus,
                shouldLoad: isStatus === 'completed' || isStatus === 'error' || isStatus === 'warning'
            })
            if (isStatus === 'completed' || isStatus === 'error' || isStatus === 'warning') {
                console.log('[DocumentExtractionView] Calling loadIncomeStatement()')
                loadIncomeStatement()
            }
        }

        const sharesStatus = financialStatementProgress?.milestones?.shares_outstanding?.status
        // Also check if overall status is completed as a fallback
        const isOverallComplete = financialStatementProgress?.status === 'completed'

        if (!additionalItemsLoadAttempted && (sharesStatus === 'completed' || sharesStatus === 'error' || sharesStatus === 'warning' || sharesStatus === 'skipped' || isOverallComplete)) {
            console.log('[DocumentExtractionView] Condition met, calling loadAdditionalItems')
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

    // Coordination: Auto-refresh when processing completes
    const prevAnalysisStatusRef = useRef(selectedDocument?.analysis_status)

    useEffect(() => {
        const currentStatus = selectedDocument?.analysis_status
        const prevStatus = prevAnalysisStatusRef.current

        if (prevStatus === 'processing' && currentStatus !== 'processing') {
            console.log('[DocumentExtractionView] Analysis pipeline finished, refreshing data...')

            if (selectedDocument && isEligibleForFinancialStatements) {
                // 1. Refresh progress first
                loadFinancialStatementProgress()

                // 2. Clear and reload historical calculations only
                // DO NOT clear financial statements (balance sheet, income statement)
                // Those should only be cleared when explicitly rerunning extraction
                clearHistoricalCalculations()

                // 3. Reset historical calculations load flag to allow re-fetching
                setHistoricalCalculationsLoadAttempted(false)
            }
        }

        prevAnalysisStatusRef.current = currentStatus
    }, [
        selectedDocument?.analysis_status,
        selectedDocument,
        isEligibleForFinancialStatements,
        loadFinancialStatementProgress,
        clearHistoricalCalculations,
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
                        {/* Validation Banner & Processing Status */}
                        {(() => {
                            const milestones = financialStatementProgress?.milestones || {};
                            const errors = [];
                            const warnings = [];
                            const overallStatus = financialStatementProgress?.status || 'not_started';

                            // 1. Collect errors and warnings from milestones
                            Object.entries(milestones).forEach(([key, milestone]) => {
                                if (milestone.status === 'error') {
                                    errors.push({
                                        milestone: key.replace(/_/g, ' '),
                                        message: milestone.message || 'Processing failed'
                                    });
                                }
                                if (milestone.status === 'warning') {
                                    warnings.push({
                                        milestone: key.replace(/_/g, ' '),
                                        message: milestone.message || 'Warning'
                                    });
                                }
                            });

                            // 2. Add specific validation errors from the statements themselves
                            // Only add if not already present in milestone warnings
                            const processStatementErrors = (statement, label, milestoneKey) => {
                                if (statement && statement.is_valid === false) {
                                    // Check if milestone already has a warning with validation errors
                                    const milestoneWarning = milestones[milestoneKey];
                                    const milestoneHasValidationWarnings = milestoneWarning?.status === 'warning' &&
                                        milestoneWarning?.message?.includes('Validation warnings:');

                                    // Skip if milestone already reported validation warnings
                                    if (milestoneHasValidationWarnings) {
                                        return;
                                    }

                                    const errorDetails = statement.validation_errors;
                                    if (errorDetails) {
                                        try {
                                            const parsed = JSON.parse(errorDetails);
                                            if (Array.isArray(parsed)) {
                                                parsed.forEach(err => {
                                                    if (!warnings.find(w => w.milestone === label && w.message === err)) {
                                                        warnings.push({ milestone: label, message: err });
                                                    }
                                                });
                                            } else {
                                                if (!warnings.find(w => w.milestone === label && w.message === errorDetails)) {
                                                    warnings.push({ milestone: label, message: errorDetails });
                                                }
                                            }
                                        } catch (e) {
                                            if (!warnings.find(w => w.milestone === label && w.message === errorDetails)) {
                                                warnings.push({ milestone: label, message: errorDetails });
                                            }
                                        }
                                    }
                                }
                            };

                            processStatementErrors(balanceSheet, 'Balance Sheet', 'balance_sheet');
                            processStatementErrors(incomeStatement, 'Income Statement', 'income_statement');

                            // 3. Data Integrity & Health Checks
                            // Only show "missing" errors if we've actually tried to load the data and failed
                            const isDone = areAllMilestonesTerminal() || overallStatus === 'completed' || overallStatus === 'error';
                            const isStillProcessing = overallStatus === 'processing' || overallStatus === 'not_started';
                            const primaryDataMissing = !balanceSheet || !incomeStatement;
                            const attemptsExhausted = balanceSheetLoadAttempts >= MAX_LOAD_ATTEMPTS && incomeStatementLoadAttempts >= MAX_LOAD_ATTEMPTS;

                            // Only show critical data errors if:
                            // 1. We've exhausted all load attempts (data truly missing), OR
                            // 2. Processing is done AND we have at least one failed load attempt
                            const shouldShowMissingErrors = attemptsExhausted || (isDone && !isStillProcessing && (balanceSheetLoadAttempts > 0 || incomeStatementLoadAttempts > 0));

                            if (shouldShowMissingErrors) {
                                // Critical Path Errors (Red)
                                if (!balanceSheet) {
                                    errors.push({ milestone: 'Critical Data', message: 'Balance Sheet is missing' });
                                }

                                if (!incomeStatement) {
                                    errors.push({ milestone: 'Critical Data', message: 'Income Statement is missing' });
                                }

                                const hasShares = shares && ((shares.basic_shares_outstanding !== null && shares.basic_shares_outstanding !== undefined) ||
                                    (shares.diluted_shares_outstanding !== null && shares.diluted_shares_outstanding !== undefined));
                                if (!hasShares && isDone) {
                                    errors.push({ milestone: 'Critical Data', message: 'Shares Outstanding data is missing' });
                                }

                                if (!organicGrowth && isDone) {
                                    warnings.push({ milestone: 'Analytical Data', message: 'Organic Growth / Prior Period Revenue is missing' });
                                }

                                if (!nonOperatingClassification && isDone) {
                                    warnings.push({ milestone: 'Analytical Data', message: 'Non-Operating Classification is missing' });
                                }

                                // Warnings (Yellow)
                                const isEA = selectedDocument?.document_type?.toLowerCase() === 'earnings_announcement';
                                if (!amortization && !isEA && isDone) {
                                    warnings.push({ milestone: 'Data Integrity', message: 'GAAP Reconciliation data is missing' });
                                }
                            }

                            // 4. Render Banners
                            const showProcessingBanner = (overallStatus === 'processing' || overallStatus === 'not_started') &&
                                primaryDataMissing &&
                                !attemptsExhausted &&
                                errors.length === 0;

                            return (
                                <div className="validation-banner-container">
                                    {showProcessingBanner && (
                                        <div className="validation-banner warning" style={{ background: 'rgba(10, 132, 255, 0.05)', borderColor: 'rgba(10, 132, 255, 0.2)' }}>
                                            <div className="banner-header">
                                                <div className="status-spinner" style={{ color: 'var(--primary)', width: '18px', height: '18px' }} />
                                                <h4 style={{ color: 'var(--primary)' }}>Processing Document...</h4>
                                            </div>
                                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginLeft: '2.75rem' }}>
                                                Extraction is currently in progress. Tables will appear as they are completed.
                                            </p>
                                        </div>
                                    )}

                                    {errors.length > 0 && (
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
                                    )}

                                    {warnings.length > 0 && (
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
                                    )}
                                </div>
                            );
                        })()}



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
                                    currency={incomeStatement?.currency}
                                    unit={incomeStatement?.unit}
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

                        {shares && (
                            <div className="extraction-section">
                                <h3>Shares Outstanding</h3>
                                <SharesOutstandingTable
                                    shares={shares}
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
