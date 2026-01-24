import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL, ELIGIBLE_DOCUMENT_TYPES } from '../config'

export function useDocumentData(selectedCompany, selectedDocument) {
  const { isAuthenticated, token } = useAuth()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Document specific state
  const [isProcessing, setIsProcessing] = useState(false)
  const [isCheckingProcessingStatus, setIsCheckingProcessingStatus] = useState(false)
  const [hasFinancialStatements, setHasFinancialStatements] = useState(false)
  const [currentDocument, setCurrentDocument] = useState(selectedDocument)

  // Polling refs
  const lastStatusRef = useRef({ indexingStatus: null, analysisStatus: null })
  const processingTriggeredRef = useRef(false)
  const processingActionRef = useRef(null)

  // Load documents for a company
  const loadCompanyDocuments = useCallback(async (companyId) => {
    if (!companyId) {
      setDocuments([])
      return
    }
    setLoading(true)
    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(`${API_BASE_URL}/documents/?company_id=${companyId}`, { headers })
      const sortedDocs = response.data.sort((a, b) => {
        // Primary sort: Period End Date (descending)
        // We prioritize documents with a parsed period end date
        const dateA = a.period_end_date ? new Date(a.period_end_date).getTime() : -1
        const dateB = b.period_end_date ? new Date(b.period_end_date).getTime() : -1

        if (dateA !== dateB) {
          // If only one has a date, it comes first (if we consider it "higher quality")
          // OR, if neither has date, we go to fallback.
          // Actually, if a document doesn't have a period date (yet), it might be very new (just uploaded).
          // Maybe fallback to uploaded_at is better for everything.
          // Let's rely on dateA/dateB logic: valid dates > invalid (-1).
          // So valid dates will float to top.
          if (dateA === -1 && dateB !== -1) return 1 // B has date, A doesn't -> B first
          if (dateA !== -1 && dateB === -1) return -1 // A has date, B doesn't -> A first
          return dateB - dateA
        }

        // Secondary sort: Uploaded At (descending)
        const uploadA = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0
        const uploadB = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0
        return uploadB - uploadA
      })
      setDocuments(sortedDocs)
      setError(null)
    } catch (err) {
      console.error('Error loading documents:', err)
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, token])

  // Check financial statements existence
  const checkFinancialStatements = useCallback(async (documentId) => {
    if (!documentId) {
      setHasFinancialStatements(false)
      return
    }

    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const [balanceSheetResponse, incomeStatementResponse] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/documents/${documentId}/balance-sheet`, { headers }),
        axios.get(`${API_BASE_URL}/documents/${documentId}/income-statement`, { headers })
      ])

      let hasBalanceSheet = false
      if (balanceSheetResponse.status === 'fulfilled') {
        const response = balanceSheetResponse.value
        hasBalanceSheet = response.status === 200 && response.data?.status === 'exists'
      }

      let hasIncomeStatement = false
      if (incomeStatementResponse.status === 'fulfilled') {
        const response = incomeStatementResponse.value
        hasIncomeStatement = response.status === 200 && response.data?.status === 'exists'
      }

      setHasFinancialStatements(hasBalanceSheet || hasIncomeStatement)
    } catch (error) {
      console.error('Error checking financial statements:', error)
      setHasFinancialStatements(false)
    }
  }, [isAuthenticated, token])

  // Fetch latest status for a single document
  const fetchLatestStatus = useCallback(async (documentId) => {
    if (!documentId) return null

    try {
      const endpoint = isAuthenticated ? 'status' : 'status-test'
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      const response = await axios.get(
        `${API_BASE_URL}/documents/${documentId}/${endpoint}`,
        { headers }
      )
      return response.data
    } catch (error) {
      console.error('Error fetching latest document status:', error)
      return null
    }
  }, [isAuthenticated, token])

  // Initial load when company changes
  useEffect(() => {
    if (selectedCompany) {
      loadCompanyDocuments(selectedCompany.id)
    } else {
      setDocuments([])
    }
  }, [selectedCompany, loadCompanyDocuments])

  // Document selection side effects (status check, financial statements check)
  useEffect(() => {
    let isMounted = true

    // Update local currentDocument when prop changes
    if (selectedDocument) {
      setCurrentDocument(selectedDocument)
    }

    if (!selectedDocument) {
      if (isMounted) {
        setIsProcessing(false)
        setIsCheckingProcessingStatus(false)
        setHasFinancialStatements(false)
      }
      return
    }

    if (isMounted) {
      setIsCheckingProcessingStatus(true)
      setHasFinancialStatements(false)
    }

    const initDocument = async () => {
      const latestDoc = await fetchLatestStatus(selectedDocument.id)

      if (isMounted && latestDoc) {
        setCurrentDocument(latestDoc) // Update local state
        setIsCheckingProcessingStatus(false)

        // Check financial statements if eligible
        if (latestDoc.document_type && ELIGIBLE_DOCUMENT_TYPES.includes(latestDoc.document_type)) {
          await checkFinancialStatements(latestDoc.id)
        }
      } else if (isMounted) {
        setIsCheckingProcessingStatus(false)
      }
    }

    initDocument()

    if (selectedDocument.analysis_status !== 'processing') {
      setIsProcessing(false)
    }

    return () => {
      isMounted = false
    }
  }, [selectedDocument, fetchLatestStatus, checkFinancialStatements])

  // Polling for indexing status (list view)
  useEffect(() => {
    if (!selectedCompany || documents.length === 0) return

    const indexingDocuments = documents.filter(
      doc => doc.indexing_status === 'indexing' || doc.indexing_status === 'INDEXING'
    )

    if (indexingDocuments.length === 0) return

    const pollInterval = setInterval(async () => {
      if (!isAuthenticated) return

      for (const doc of indexingDocuments) {
        try {
          const endpoint = isAuthenticated ? 'status' : 'status-test'
          // Note: using status endpoint which is standardized
          const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
          const response = await axios.get(`${API_BASE_URL}/documents/${doc.id}/${endpoint}`, { headers })

          setDocuments(prevDocs =>
            prevDocs.map(d =>
              d.id === doc.id ? response.data : d
            )
          )
        } catch (error) {
          console.error(`Error polling status for document ${doc.id}:`, error)
        }
      }
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [documents, selectedCompany, isAuthenticated, token])

  // Polling for selected document status
  useEffect(() => {
    if (!currentDocument) return

    const isIndexing = currentDocument.indexing_status === 'indexing' || currentDocument.indexing_status === 'INDEXING'
    const isProcessingAnalysis = currentDocument.analysis_status === 'processing'

    if (!isIndexing && !isProcessingAnalysis) {
      lastStatusRef.current = { indexingStatus: null, analysisStatus: null }
      return
    }

    lastStatusRef.current = {
      indexingStatus: currentDocument.indexing_status,
      analysisStatus: currentDocument.analysis_status
    }

    let isMounted = true

    const pollInterval = setInterval(async () => {
      const latestDoc = await fetchLatestStatus(currentDocument.id)

      if (!isMounted) return
      if (!latestDoc) return

      const newIndexingStatus = latestDoc.indexing_status
      const newAnalysisStatus = latestDoc.analysis_status

      if (newIndexingStatus !== lastStatusRef.current.indexingStatus ||
        newAnalysisStatus !== lastStatusRef.current.analysisStatus) {

        lastStatusRef.current.indexingStatus = newIndexingStatus
        lastStatusRef.current.analysisStatus = newAnalysisStatus
        setCurrentDocument(latestDoc)

        // If processing completed
        if (lastStatusRef.current.analysisStatus === 'processing' && newAnalysisStatus !== 'processing') {
          setIsProcessing(false)
          processingTriggeredRef.current = false
          if (latestDoc.document_type && ELIGIBLE_DOCUMENT_TYPES.includes(latestDoc.document_type)) {
            await checkFinancialStatements(latestDoc.id)
          }
        }
      }

    }, 3000)

    return () => {
      isMounted = false
      clearInterval(pollInterval)
    }
  }, [currentDocument, fetchLatestStatus, checkFinancialStatements])

  // Logic for re-run / delete actions
  const performAction = useCallback(async (actionType, documentId) => {
    setIsProcessing(true)
    processingTriggeredRef.current = true
    processingActionRef.current = actionType

    try {
      const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
      let endpoint = ''
      let method = 'post'

      switch (actionType) {
        case 'rerun-indexing':
          // Phase 1: Ingestion
          endpoint = `processing/documents/${documentId}/ingest`
          break
        case 'rerun-extraction':
          // Phase 2-3: Extraction
          console.log('[performAction] Starting rerun-extraction for document:', documentId)
          endpoint = `processing/documents/${documentId}/rerun`
          // Trigger UI events
          window.dispatchEvent(new CustomEvent('resetProgressToPending', { detail: { documentId } }))
          window.dispatchEvent(new CustomEvent('clearFinancialStatements'))
          console.log('[performAction] Dispatched UI events for rerun-extraction')
          break
        case 'rerun-historical':
          // Phase 4: Analysis
          endpoint = `processing/documents/${documentId}/analyze`
          break
        case 'delete-statements':
          // Legacy balance_sheet router (mounted at /api/documents)
          endpoint = `documents/${documentId}/financial-statements`
          method = 'delete'
          break
        case 'delete-document':
          // Legacy documents router (permanent delete)
          endpoint = isAuthenticated ? `documents/${documentId}/permanent` : `documents/${documentId}/permanent/test`
          method = 'delete'
          break
        default:
          throw new Error('Unknown action')
      }

      if (method === 'delete') {
        await axios.delete(`${API_BASE_URL}/${endpoint}`, { headers })
      } else {
        console.log(`[performAction] Calling POST ${API_BASE_URL}/${endpoint}`)
        await axios.post(`${API_BASE_URL}/${endpoint}`, {}, { headers })
        console.log('[performAction] POST request completed successfully')
      }

      // Post-action logic
      if (actionType === 'delete-statements') {
        window.dispatchEvent(new CustomEvent('clearFinancialStatements'))
        setHasFinancialStatements(false)
        const status = await fetchLatestStatus(documentId)
        if (status) setCurrentDocument(status)
      } else if (actionType === 'delete-document') {
        // Caller handles navigation
        loadCompanyDocuments(selectedCompany?.id)
      } else if (actionType === 'rerun-historical') {
        window.dispatchEvent(new CustomEvent('reloadHistoricalCalculations'))
        setIsProcessing(false) // Historical usually quick, or handled by separate loading state in UI
      } else {
        // For long running processes (indexing, extraction), we rely on polling
        const status = await fetchLatestStatus(documentId)
        if (status) setCurrentDocument(status)
      }

    } catch (err) {
      console.error(`Error performing ${actionType}:`, err)
      setIsProcessing(false)
      throw err
    }
  }, [isAuthenticated, token, fetchLatestStatus, selectedCompany?.id, loadCompanyDocuments])

  return {
    documents,
    loading,
    error,
    loadCompanyDocuments,
    currentDocument, // The up-to-date document object
    isProcessing,
    isCheckingProcessingStatus,
    hasFinancialStatements,
    performAction,
    setIsProcessing
  }
}
