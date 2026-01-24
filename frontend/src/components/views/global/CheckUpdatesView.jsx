import React, { useEffect, useState, useRef } from 'react'
import { useUpload } from '../../../contexts/UploadContext'
import './CheckUpdates.css'

function CheckUpdatesView({ onBack }) {
    const {
        uploadingDocuments,
        isConnected,
    } = useUpload()

    const [allDocuments, setAllDocuments] = useState([])
    const [expandedMilestones, setExpandedMilestones] = useState({})
    const completedDocumentsRef = useRef(new Map())

    // Group milestones into phases for visual organization
    const phases = [
        {
            name: 'Ingestion',
            milestones: ['upload', 'classification', 'index']
        },
        {
            name: 'Core Extraction',
            milestones: ['balance_sheet', 'income_statement', 'shares_outstanding', 'organic_growth', 'gaap_reconciliation']
        },
        {
            name: 'Additional Extraction',
            milestones: ['amortization', 'other_assets', 'other_liabilities', 'classifying_non_operating_items']
        },
        {
            name: 'Analysis',
            milestones: ['calculate_value_metrics', 'update_historical_data', 'update_assumptions', 'calculate_intrinsic_value']
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
        classifying_non_operating_items: 'Non-Operating Classification',
        calculate_value_metrics: 'Calculate Value Metrics',
        update_historical_data: 'Update Historical Data',
        update_assumptions: 'Update Assumptions',
        calculate_intrinsic_value: 'Calculate Intrinsic Value'
    }

    // Merge active and recently completed documents
    useEffect(() => {
        const now = Date.now()
        const RETENTION_TIME = 60000 // Keep completed docs for 60 seconds (matches backend)

        // Add/update active documents
        uploadingDocuments.forEach(doc => {
            completedDocumentsRef.current.set(doc.id, {
                ...doc,
                lastSeen: now
            })
        })

        // Remove old completed documents
        for (const [id, doc] of completedDocumentsRef.current.entries()) {
            const isActive = uploadingDocuments.some(d => d.id === id)
            if (!isActive && (now - doc.lastSeen) > RETENTION_TIME) {
                completedDocumentsRef.current.delete(id)
            }
        }

        // Convert to array and sort by last seen (most recent first)
        const merged = Array.from(completedDocumentsRef.current.values())
            .sort((a, b) => b.lastSeen - a.lastSeen)

        setAllDocuments(merged)
    }, [uploadingDocuments])

    const getMilestoneStatus = (doc, milestoneKey) => {
        // Check for granular progress from SSE first
        const progress = doc.financial_statement_progress
        if (progress && progress.milestones && progress.milestones[milestoneKey]) {
            return progress.milestones[milestoneKey].status
        }

        // Fallback map from existing indexing_status and analysis_status
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

    const getMilestoneLogs = (doc, milestoneKey) => {
        const progress = doc.financial_statement_progress
        if (progress && progress.milestones && progress.milestones[milestoneKey]) {
            return progress.milestones[milestoneKey].logs || []
        }
        return []
    }

    const getMilestoneMessage = (doc, milestoneKey) => {
        const progress = doc.financial_statement_progress
        if (progress && progress.milestones && progress.milestones[milestoneKey]) {
            return progress.milestones[milestoneKey].message
        }
        return null
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
            case 'skipped':
                return '—'
            default:
                return '○'
        }
    }

    const toggleMilestone = (docId, milestoneKey) => {
        const key = `${docId}-${milestoneKey}`
        setExpandedMilestones(prev => ({
            ...prev,
            [key]: !prev[key]
        }))
    }

    const isExpanded = (docId, milestoneKey) => {
        const key = `${docId}-${milestoneKey}`
        return expandedMilestones[key] || false
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
                {isConnected && (
                    <span className="sse-status connected" title="Real-time updates active">
                        ● Live
                    </span>
                )}
            </div>

            {allDocuments.length === 0 ? (
                <div className="empty-state">
                    <p>No recent uploads or processing activity.</p>
                    <button className="button-primary" onClick={onBack}>
                        Back to Companies
                    </button>
                </div>
            ) : (
                <div className="check-updates-container">
                    {allDocuments.map(document => (
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
                                            const message = getMilestoneMessage(document, milestoneKey)
                                            const logs = getMilestoneLogs(document, milestoneKey)
                                            const expanded = isExpanded(document.id, milestoneKey)
                                            const hasLogs = logs.length > 0

                                            return (
                                                <div key={milestoneKey} className={`milestone-item ${status}`}>
                                                    <div
                                                        className="milestone-header"
                                                        onClick={() => hasLogs && toggleMilestone(document.id, milestoneKey)}
                                                        style={{ cursor: hasLogs ? 'pointer' : 'default' }}
                                                    >
                                                        <span className={`milestone-icon ${status}`}>
                                                            {getStatusIcon(status)}
                                                        </span>
                                                        <span className="milestone-label">{label}</span>
                                                        <span className={`milestone-status ${status}`}>
                                                            {status.replace('_', ' ')}
                                                        </span>
                                                        {hasLogs && (
                                                            <span className="milestone-expand-icon">
                                                                {expanded ? '▼' : '▶'}
                                                            </span>
                                                        )}
                                                    </div>
                                                    {message && (
                                                        <div className="milestone-message">{message}</div>
                                                    )}
                                                    {expanded && hasLogs && (
                                                        <div className="milestone-logs">
                                                            {logs.map((log, idx) => (
                                                                <div key={idx} className="log-entry">
                                                                    {typeof log === 'string' ? log : log.message}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
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
