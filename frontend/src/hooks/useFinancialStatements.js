import { useState, useCallback, useRef, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

export function useFinancialStatements(selectedDocument, isEligibleForFinancialStatements) {
    const { isAuthenticated, token } = useAuth()

    const [balanceSheet, setBalanceSheet] = useState(null)
    const [incomeStatement, setIncomeStatement] = useState(null)
    const [organicGrowth, setOrganicGrowth] = useState(null)
    const [amortization, setAmortization] = useState(null)
    const [otherAssets, setOtherAssets] = useState(null)
    const [otherLiabilities, setOtherLiabilities] = useState(null)
    const [nonOperatingClassification, setNonOperatingClassification] = useState(null)

    // Loading states
    const [additionalItemsLoadAttempted, setAdditionalItemsLoadAttempted] = useState(false)
    const [balanceSheetLoadAttempts, setBalanceSheetLoadAttempts] = useState(0)
    const [incomeStatementLoadAttempts, setIncomeStatementLoadAttempts] = useState(0)

    // Refs for loading status to prevent double-firing
    const balanceSheetLoadingRef = useRef(false)
    const incomeStatementLoadingRef = useRef(false)
    const balanceSheetAttemptsRef = useRef(0)
    const incomeStatementAttemptsRef = useRef(0)
    const MAX_LOAD_ATTEMPTS = 3

    const loadBalanceSheet = useCallback(async () => {
        if (!selectedDocument?.id) return
        if (balanceSheetLoadingRef.current) return
        if (balanceSheetAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return

        balanceSheetLoadingRef.current = true
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/balance-sheet`,
                { headers }
            )
            if (response.data && response.data.status === 'exists') {
                setBalanceSheet(response.data.data)
                balanceSheetAttemptsRef.current = 0
                setBalanceSheetLoadAttempts(0)
            } else {
                setBalanceSheet(null)
                balanceSheetAttemptsRef.current += 1
                setBalanceSheetLoadAttempts(prev => prev + 1)
            }
        } catch (err) {
            setBalanceSheet(null)
            balanceSheetAttemptsRef.current += 1
            setBalanceSheetLoadAttempts(prev => prev + 1)
        } finally {
            balanceSheetLoadingRef.current = false
        }
    }, [selectedDocument?.id, isAuthenticated, token])

    const loadIncomeStatement = useCallback(async () => {
        if (!selectedDocument?.id) return
        if (incomeStatementLoadingRef.current) return
        if (incomeStatementAttemptsRef.current >= MAX_LOAD_ATTEMPTS) return

        incomeStatementLoadingRef.current = true
        try {
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
            const response = await axios.get(
                `${API_BASE_URL}/documents/${selectedDocument.id}/income-statement`,
                { headers }
            )
            if (response.data && response.data.status === 'exists') {
                setIncomeStatement(response.data.data)
                incomeStatementAttemptsRef.current = 0
                setIncomeStatementLoadAttempts(0)
            } else {
                setIncomeStatement(null)
                incomeStatementAttemptsRef.current += 1
                setIncomeStatementLoadAttempts(prev => prev + 1)
            }
        } catch (err) {
            setIncomeStatement(null)
            incomeStatementAttemptsRef.current += 1
            setIncomeStatementLoadAttempts(prev => prev + 1)
        } finally {
            incomeStatementLoadingRef.current = false
        }
    }, [selectedDocument?.id, isAuthenticated, token])

    const loadAdditionalItems = useCallback(async () => {
        if (!selectedDocument?.id || !isEligibleForFinancialStatements) return
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const isEarningsAnnouncement = selectedDocument.document_type === 'earnings_announcement' ||
            selectedDocument.document_type === 'EARNINGS_ANNOUNCEMENT'

        const endpoints = {
            organicGrowth: 'organic-growth',
            amortization: 'amortization',
            ...(isEarningsAnnouncement ? {} : {
                otherAssets: 'other-assets',
                otherLiabilities: 'other-liabilities',
            }),
            nonOperatingClassification: 'non-operating-classification'
        }

        const results = await Promise.allSettled(
            Object.entries(endpoints).map(([key, endpoint]) =>
                axios.get(`${API_BASE_URL}/documents/${selectedDocument.id}/${endpoint}`, { headers })
                    .then(response => ({ key, data: response.data?.data || null }))
            )
        )

        results.forEach(result => {
            if (result.status === 'fulfilled') {
                const { key, data } = result.value
                if (key === 'organicGrowth') setOrganicGrowth(data)
                if (key === 'amortization') setAmortization(data)
                if (key === 'otherAssets') setOtherAssets(data)
                if (key === 'otherLiabilities') setOtherLiabilities(data)
                if (key === 'nonOperatingClassification') setNonOperatingClassification(data)
            }
        })
    }, [selectedDocument?.id, selectedDocument?.document_type, isEligibleForFinancialStatements, isAuthenticated, token])

    const clearFinancialStatements = useCallback(() => {
        setBalanceSheet(null)
        setIncomeStatement(null)
        setOrganicGrowth(null)
        setAmortization(null)
        setOtherAssets(null)
        setOtherLiabilities(null)
        setNonOperatingClassification(null)
        setAdditionalItemsLoadAttempted(false)
        setBalanceSheetLoadAttempts(0)
        setIncomeStatementLoadAttempts(0)
        balanceSheetLoadingRef.current = false
        incomeStatementLoadingRef.current = false
        balanceSheetAttemptsRef.current = 0
        incomeStatementAttemptsRef.current = 0
    }, [])

    return {
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
    }
}
