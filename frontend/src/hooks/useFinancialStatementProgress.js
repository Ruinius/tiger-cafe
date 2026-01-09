import { useState, useCallback, useRef, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

export function useFinancialStatementProgress(selectedDocument, isEligibleForFinancialStatements) {
    const { isAuthenticated, token } = useAuth()
    const [financialStatementProgress, setFinancialStatementProgress] = useState(null)
    const progressPollingIntervalRef = useRef(null)

    const areAllMilestonesTerminal = useCallback(() => {
        if (!financialStatementProgress) return false
        if (financialStatementProgress.status === 'not_started') return false
        if (!financialStatementProgress.milestones) return false
        const allMilestones = Object.values(financialStatementProgress.milestones)
        if (allMilestones.length === 0) return false

        return allMilestones.every((milestone) =>
            milestone.status === 'completed' || milestone.status === 'error' || milestone.status === 'not_found'
        )
    }, [financialStatementProgress])

    const loadFinancialStatementProgress = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        try {
            const endpoint = isAuthenticated ? 'financial-statement-progress' : 'financial-statement-progress-test'
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                { headers }
            )
            setFinancialStatementProgress(response.data)
        } catch (err) {
            setFinancialStatementProgress(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, isAuthenticated, token])

    // Polling Logic
    useEffect(() => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return

        const hasActiveMilestones = financialStatementProgress &&
            financialStatementProgress.milestones &&
            Object.values(financialStatementProgress.milestones).some((milestone) =>
                milestone.status === 'in_progress' || milestone.status === 'pending'
            )

        if (hasActiveMilestones) {
            const interval = setInterval(() => {
                loadFinancialStatementProgress()
            }, 3000)
            progressPollingIntervalRef.current = interval
            return () => {
                clearInterval(interval)
                progressPollingIntervalRef.current = null
            }
        } else {
            if (progressPollingIntervalRef.current) {
                clearInterval(progressPollingIntervalRef.current)
                progressPollingIntervalRef.current = null
            }
        }
    }, [financialStatementProgress, selectedDocument?.id, isEligibleForFinancialStatements, loadFinancialStatementProgress])

    // Initial Load
    useEffect(() => {
        if (progressPollingIntervalRef.current) {
            clearInterval(progressPollingIntervalRef.current)
            progressPollingIntervalRef.current = null
        }

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
