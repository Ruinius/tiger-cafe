import React, { useEffect, useState } from 'react'
import { useUploadManager } from '../../../hooks/useUploadManager'
import './CheckUpdates.css'

function CheckUpdatesView({ onBack }) {
    const {
        uploadingDocuments,
        hasActiveUploads,
    } = useUploadManager()

    const [documentProgress, setDocumentProgress] = useState({})

    // Group milestones into phases for visual organization
    const phases = [
        {
            name: 'Ingestion',
            milestones: ['upload', 'classification', 'index']
        },
        {
            name: 'Core Extraction',
            milestones: ['balance_sheet', 'income_statement']
        },
        {
            name: 'Deep Analysis',
            milestones: ['shares_outstanding', 'organic_growth', 'gaap_reconciliation', 'amortization', 'other_assets', 'other_liabilities', 'classifying_non_operating_items']
        }
    ]

    const milestoneLabels = {
        upload: 'Upload',
        classification: 'Classification',
        index: 'Indexing',
        balance_sheet: 'Balance Sheet',
        income_statement: 'Income Statement',
        shares_outstanding: 'Shares Outstanding',
        organic_growth: 'Organic Growth',
        gaap_reconciliation: 'GAAP Reconciliation',
        amortization: 'Amortization',
        other_assets: 'Other Assets',
        other_liabilities: 'Other Liabilities',
        classifying_non_operating_items: 'Non-Operating Classification'
    }

    const getMilestoneStatus = (doc, milestoneKey) => {
        // For now, map from existing indexing_status and analysis_status
        // This will be replaced with actual milestone tracking from SSE
        const indexingStatus = doc.indexing_status?.toLowerCase()
        const analysisStatus = doc.analysis_status?.toLowerCase()

        // Phase 1: Ingestion
        if (milestoneKey === 'upload') {
            return indexingStatus ? 'completed' : 'pending'
        }
        if (milestoneKey === 'classification') {
            if (['indexed', 'indexing', 'processing', 'processed'].includes(indexingStatus)) return 'completed'
            if (indexingStatus === 'classifying') return 'in_progress'
            return 'pending'
        }
        if (milestoneKey === 'index') {
            if (['indexed', 'processing', 'processed'].includes(indexingStatus)) return 'completed'
            if (indexingStatus === 'indexing') return 'in_progress'
            return 'pending'
        }

        // Phase 2 & 3: Analysis (simplified for now)
        if (['processing'].includes(analysisStatus)) {
            return 'in_progress'
        }
        if (analysisStatus === 'processed') {
            return 'completed'
        }
        if (analysisStatus === 'error') {
            return 'error'
        }

        return 'pending'
    }

    const getStatusIcon = (status) => {
        switch (status) {
            case 'completed':
                return '✓'
            case 'in_progress':
                return <span className="status-spinner" aria-hidden="true" />
            case 'error':
                return '✗'
            case 'warning':
                return '⚠'
            default:
                return '○'
        }
    }

    return (
        <div className="panel-content">
            <div className="panel-header">
                <div className="breadcrumb">
                    <button className="breadcrumb-link" onClick={onBack}>
                        Companies
                    </button>
                    <span className="breadcrumb-separator">›</span>
                    <span className="breadcrumb-current">Check Updates</span>
                </div>
            </div>

            {uploadingDocuments.length === 0 ? (
                <div className="empty-state">
                    <p>All uploads have completed.</p>
                    <button className="button-primary" onClick={onBack}>
                        Back to Companies
                    </button>
                </div>
            ) : (
                <div className="check-updates-container">
                    {uploadingDocuments.map(document => (
                        <div key={document.id} className="document-progress-card">
                            <div className="document-progress-header">
                                <h3 className="document-filename">{document.filename}</h3>
                                {document.duplicate_detected && (
                                    <span className="duplicate-badge">⚠️ Duplicate</span>
                                )}
                            </div>

                            {/* Phase-based milestone display */}
                            {phases.map((phase, phaseIdx) => (
                                <div key={phaseIdx} className="phase-section">
                                    <h4 className="phase-title">
                                        Phase {phaseIdx + 1}: {phase.name}
                                    </h4>
                                    <div className="milestones-list">
                                        {phase.milestones.map(milestoneKey => {
                                            const status = getMilestoneStatus(document, milestoneKey)
                                            const label = milestoneLabels[milestoneKey]

                                            return (
                                                <div key={milestoneKey} className={`milestone-item ${status}`}>
                                                    <div className="milestone-header">
                                                        <span className={`milestone-icon ${status}`}>
                                                            {getStatusIcon(status)}
                                                        </span>
                                                        <span className="milestone-label">{label}</span>
                                                        <span className={`milestone-status ${status}`}>
                                                            {status.replace('_', ' ')}
                                                        </span>
                                                    </div>
                                                    {/* Expandable logs will go here in future iteration */}
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default CheckUpdatesView
