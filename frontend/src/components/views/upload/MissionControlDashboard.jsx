import React, { useEffect, useState, useRef } from 'react'
import { useUpload } from '../../../contexts/UploadContext'
import './MissionControl.css'

function MissionControlDashboard({ onBack, focusedDocumentId, setFocusedDocumentId }) {
    const {
        uploadingDocuments,
        isConnected,
    } = useUpload()

    const [allDocuments, setAllDocuments] = useState([])
    const completedDocumentsRef = useRef(new Map())

    // Merge active and recently completed documents
    useEffect(() => {
        const now = Date.now()
        const RETENTION_TIME = 600000 // Keep completed docs for 10 minutes (600 seconds)

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

        // Set initial focus if none set
        if (!focusedDocumentId && merged.length > 0) {
            setFocusedDocumentId(merged[0].id)
        }
    }, [uploadingDocuments, focusedDocumentId, setFocusedDocumentId])

    const getMilestoneStatus = (doc, milestoneKey) => {
        const progress = doc.financial_statement_progress
        if (progress && progress.milestones && progress.milestones[milestoneKey]) {
            return progress.milestones[milestoneKey].status?.toLowerCase() || 'pending'
        }

        const indexingStatus = doc.indexing_status?.toLowerCase()
        const analysisStatus = doc.analysis_status?.toLowerCase()

        if (milestoneKey === 'upload') return indexingStatus ? 'completed' : 'pending'
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

        if (['processing'].includes(analysisStatus)) return 'in_progress'
        if (analysisStatus === 'processed') return 'completed'
        if (analysisStatus === 'error') return 'error'

        return 'pending'
    }

    const milestoneKeys = [
        'upload', 'classification', 'index', 'balance_sheet',
        'income_statement', 'shares_outstanding', 'organic_growth', 'gaap_reconciliation',
        'amortization', 'other_assets', 'other_liabilities', 'classifying_non_operating_items',
        'calculate_value_metrics', 'update_historical_data', 'update_assumptions', 'calculate_intrinsic_value'
    ]

    const getStatusIcon = (status) => {
        switch (status) {
            case 'completed': return '✓'
            case 'in_progress': return <span className="milestone-pulse" />
            case 'error': return '✗'
            case 'warning': return '⚠'
            case 'skipped': return '—'
            default: return ''
        }
    }

    const getCompletionPercentage = (doc) => {
        const terminalStatuses = ['completed', 'error', 'warning', 'skipped']
        const completed = milestoneKeys.filter(k => terminalStatuses.includes(getMilestoneStatus(doc, k))).length
        return Math.round((completed / milestoneKeys.length) * 100)
    }

    return (
        <div className="panel-content mission-control-dashboard">
            <div className="panel-header">
                <div className="breadcrumb">
                    <button className="breadcrumb-link" onClick={onBack}>
                        Companies
                    </button>
                    <span className="breadcrumb-separator">›</span>
                    <span className="breadcrumb-current">Check Updates</span>
                </div>
                {isConnected && (
                    <div className="sse-status connected">
                        <span className="status-dot pulsing"></span>
                        <span className="status-label">Mission Control Live</span>
                    </div>
                )}
            </div>

            <div className="document-grid">
                {allDocuments.length === 0 ? (
                    <div className="empty-state">
                        <p>No active processing missions.</p>
                    </div>
                ) : (
                    allDocuments.map(doc => {
                        const isFocused = focusedDocumentId === doc.id
                        const progress = getCompletionPercentage(doc)

                        return (
                            <div
                                key={doc.id}
                                className={`document-mission-card ${isFocused ? 'focused' : ''}`}
                                onClick={() => setFocusedDocumentId(doc.id)}
                            >
                                <div className="card-header">
                                    <h4 className="doc-filename" title={doc.filename}>{doc.filename}</h4>
                                </div>

                                <div className="milestone-matrix">
                                    {milestoneKeys.map(key => {
                                        const status = getMilestoneStatus(doc, key)
                                        const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                                        return (
                                            <div
                                                key={key}
                                                className={`matrix-tile ${status} tooltip-container`}
                                            >
                                                {getStatusIcon(status)}
                                                <span className="tooltip-text">
                                                    <strong>{label}</strong><br />
                                                    Status: {status.replace('_', ' ')}
                                                </span>
                                            </div>
                                        )
                                    })}
                                </div>

                                <div className="mission-progress-container">
                                    <div className="mission-progress-track">
                                        <div
                                            className="mission-progress-fill"
                                            style={{ width: `${progress}%` }}
                                        />
                                    </div>
                                    <span className="mission-progress-text">{progress}%</span>
                                </div>
                            </div>
                        )
                    })
                )}
            </div>
        </div>
    )
}

export default MissionControlDashboard
