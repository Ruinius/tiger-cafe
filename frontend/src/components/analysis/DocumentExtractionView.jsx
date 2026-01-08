import React from 'react'
import LineItemTable from '../common/LineItemTable'
import OrganicGrowthTable from '../common/OrganicGrowthTable'
import StandardizedBreakdownTable from '../common/StandardizedBreakdownTable'
import SharesOutstandingTable from '../common/SharesOutstandingTable'

function DocumentExtractionView({
    selectedDocument,
    balanceSheet,
    incomeStatement,
    organicGrowth,
    amortization,
    otherAssets,
    otherLiabilities,
    nonOperatingClassification,
    financialStatementProgress,
    formatNumber
}) {
    const formatLabel = (value) => {
        if (!value) return 'Unknown'
        return value
            .replace(/_/g, ' ')
            .split(' ')
            .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
            .join(' ')
    }

    const formatCategoryLabel = (category) => {
        if (!category) return 'N/A'
        return formatLabel(category)
    }

    return (
        <div className="right-panel">
            <div className="panel-content">
                <h2>Document Analysis</h2>
                <div className="document-extractions">
                    {/* Balance Sheet Section */}
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

                    {/* Income Statement Section */}
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

                    {/* Organic Growth Section */}
                    {organicGrowth && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Organic Revenue Growth</h3>
                            <OrganicGrowthTable
                                data={organicGrowth}
                                formatNumber={formatNumber}
                                balanceSheet={balanceSheet}
                                incomeStatement={incomeStatement}
                            />
                        </div>
                    )}

                    {/* Amortization Section */}
                    {amortization && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Amortization of Intangibles</h3>
                            <LineItemTable
                                data={amortization}
                                formatNumber={formatNumber}
                                balanceSheet={balanceSheet}
                                incomeStatement={incomeStatement}
                                typeOverride={<span className="type-badge operating">Operating</span>}
                                showCategory={false}
                            />
                        </div>
                    )}

                    {/* Other Assets Section */}
                    {otherAssets && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Other Assets Breakdown</h3>
                            <StandardizedBreakdownTable
                                data={otherAssets}
                                formatNumber={formatNumber}
                                balanceSheet={balanceSheet}
                                incomeStatement={incomeStatement}
                            />
                        </div>
                    )}

                    {/* Other Liabilities Section */}
                    {otherLiabilities && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Other Liabilities Breakdown</h3>
                            <StandardizedBreakdownTable
                                data={otherLiabilities}
                                formatNumber={formatNumber}
                                balanceSheet={balanceSheet}
                                incomeStatement={incomeStatement}
                            />
                        </div>
                    )}

                    {/* Shares Outstanding Section */}
                    {balanceSheet && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Shares Outstanding</h3>
                            <SharesOutstandingTable
                                balanceSheet={balanceSheet}
                                formatNumber={formatNumber}
                            />
                        </div>
                    )}

                    {/* Non-Operating Classification Section */}
                    {nonOperatingClassification && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h3>Non-Operating Items Classification</h3>
                            <LineItemTable
                                data={nonOperatingClassification}
                                formatNumber={formatNumber}
                                balanceSheet={balanceSheet}
                                incomeStatement={incomeStatement}
                                categoryFormatter={formatCategoryLabel}
                            />
                        </div>
                    )}

                    {/* Placeholder if no data */}
                    {!balanceSheet && !incomeStatement && (
                        <p className="placeholder-text">
                            Financial statement extractions will be displayed here once processing is complete.
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}

export default DocumentExtractionView
