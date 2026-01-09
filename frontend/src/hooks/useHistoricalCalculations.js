import { useState, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

export function useHistoricalCalculations(selectedDocument, isEligibleForFinancialStatements) {
    const { isAuthenticated, token } = useAuth()
    const [historicalCalculations, setHistoricalCalculations] = useState(null)
    const [historicalCalculationsLoadAttempted, setHistoricalCalculationsLoadAttempted] = useState(false)

    const loadHistoricalCalculations = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        try {
            const endpoint = isAuthenticated ? 'historical-calculations' : 'historical-calculations/test'
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`,
                { headers }
            )
            setHistoricalCalculations(response.data)
        } catch (err) {
            setHistoricalCalculations(null)
        }
    }, [selectedDocument?.id, isEligibleForFinancialStatements, isAuthenticated, token])

    const clearHistoricalCalculations = useCallback(() => {
        setHistoricalCalculations(null)
        setHistoricalCalculationsLoadAttempted(false)
    }, [])

    return {
        historicalCalculations,
        historicalCalculationsLoadAttempted,
        setHistoricalCalculationsLoadAttempted,
        loadHistoricalCalculations,
        clearHistoricalCalculations,
        setHistoricalCalculations // Exposed for direct updates if needed
    }
}
