import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { useStatusStream } from './useStatusStream'
import { API_BASE_URL } from '../config'

export function useFinancialStatementProgress(selectedDocument, isEligibleForFinancialStatements) {
    const { isAuthenticated, token } = useAuth()
    const [financialStatementProgress, setFinancialStatementProgress] = useState(null)

    // Use SSE to detect status changes instead of polling
    const { activeDocuments } = useStatusStream()

    const areAllMilestonesTerminal = useCallback(() => {
        if (!financialStatementProgress) return false
        if (financialStatementProgress.status === 'not_started') return false
        if (!financialStatementProgress.milestones) return false
        const allMilestones = Object.values(financialStatementProgress.milestones)
        if (allMilestones.length === 0) return false

        return allMilestones.every((milestone) =>
            milestone.status === 'completed' || milestone.status === 'error' || milestone.status === 'not_found' || milestone.status === 'skipped' || milestone.status === 'warning'
        )
    }, [financialStatementProgress])

    const loadFinancialStatementProgress = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            // Use standardized processing status endpoint
            const response = await axios.get(
                `${API_BASE_URL}/processing/documents/${selectedDocument.id}/status`,
                { headers }
            )
            setFinancialStatementProgress(response.data)
        } catch (err) {
            setFinancialStatementProgress(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, isAuthenticated, token])

    // SSE-triggered updates: Load progress ONLY when document is actively being processed
    useEffect(() => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return

        // Find this document in the SSE stream
        const currentDoc = activeDocuments.find(doc => doc.document_id === selectedDocument.id)

        // Only fetch if document is in the active stream (being processed)
        if (currentDoc) {
            console.log(`[FinancialProgress] Document ${selectedDocument.id} is active, fetching progress`)
            loadFinancialStatementProgress()
        }
        // If document is NOT in stream, don't fetch - it's either:
        // - Not started yet (initial load will handle it)
        // - Already completed (initial load got final state)
    }, [activeDocuments, selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

    // Initial Load when document changes
    useEffect(() => {
        if (selectedDocument?.id && isEligibleForFinancialStatements) {
            loadFinancialStatementProgress()
        }

        // Reset on doc change
        return () => {
            setFinancialStatementProgress(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

    // Explicit reset function
    const resetProgress = useCallback(() => {
        setFinancialStatementProgress(null)
    }, [])

    // Setter for optimistic updates
    const setProgress = useCallback((newProgress) => {
        setFinancialStatementProgress(newProgress)
    }, [])

    return {
        financialStatementProgress,
        areAllMilestonesTerminal,
        loadFinancialStatementProgress,
        resetProgress,
        setProgress
    }
}
