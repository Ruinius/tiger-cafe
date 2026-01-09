import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

export function usePdfViewer(selectedDocument) {
  const { isAuthenticated, token } = useAuth()
  const [documentChunks, setDocumentChunks] = useState(null)
  const [chunksLoading, setChunksLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState(new Set())
  const [isDocumentExpanded, setIsDocumentExpanded] = useState(false)

  // Track loading state to prevent duplicate calls
  const chunksLoadingRef = useRef(false)
  const chunksAbortControllerRef = useRef(null)

  const loadDocumentChunks = useCallback(async (documentId) => {
    if (!documentId) {
      setDocumentChunks(null)
      return
    }

    // Only load chunks for indexed documents
    // Note: This check relies on the caller ensuring the document is indexed,
    // or we check selectedDocument inside this hook if available.
    // Here we check selectedDocument passed to hook or just proceed if ID provided.
    if (selectedDocument && selectedDocument.id === documentId) {
        if (selectedDocument.indexing_status !== 'indexed' && selectedDocument.indexing_status !== 'INDEXED') {
            setDocumentChunks(null)
            return
        }
    }

    // Prevent duplicate calls
    if (chunksLoadingRef.current) {
      return
    }

    // Cancel any previous request
    if (chunksAbortControllerRef.current) {
      chunksAbortControllerRef.current.abort()
    }

    chunksLoadingRef.current = true
    setChunksLoading(true)

    // Create new abort controller for this request
    const abortController = new AbortController()
    chunksAbortControllerRef.current = abortController

    // Use setTimeout to ensure this runs asynchronously
    setTimeout(async () => {
      try {
        const endpoint = isAuthenticated ? 'chunks' : 'chunks-test'
        const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await axios.get(
          `${API_BASE_URL}/documents/${documentId}/${endpoint}`,
          {
            headers,
            signal: abortController.signal,
            timeout: 30000 // 30 second timeout
          }
        )

        // Only update state if request wasn't aborted
        if (!abortController.signal.aborted) {
          setDocumentChunks(response.data)
        }
      } catch (error) {
        // Ignore abort errors
        if (error.name === 'AbortError' || error.name === 'CanceledError') {
          return
        }
        console.error('Error loading document chunks:', error)
        if (!abortController.signal.aborted) {
          setDocumentChunks(null)
        }
      } finally {
        if (!abortController.signal.aborted) {
          chunksLoadingRef.current = false
          setChunksLoading(false)
        }
      }
    }, 1000)
  }, [isAuthenticated, token, selectedDocument])

  // Reset when document changes
  useEffect(() => {
    if (selectedDocument) {
      // Reset state
      setExpandedChunks(new Set())
      // Load chunks asynchronously
      loadDocumentChunks(selectedDocument.id)
    } else {
      // Cancel any pending request
      if (chunksAbortControllerRef.current) {
        chunksAbortControllerRef.current.abort()
      }
      chunksLoadingRef.current = false
      setDocumentChunks(null)
      setExpandedChunks(new Set())
      setIsDocumentExpanded(false)
    }

    return () => {
      if (chunksAbortControllerRef.current) {
        chunksAbortControllerRef.current.abort()
      }
      chunksLoadingRef.current = false
    }
  }, [selectedDocument?.id, loadDocumentChunks])

  const toggleChunk = useCallback((chunkIndex) => {
    setExpandedChunks(prev => {
      const newSet = new Set(prev)
      if (newSet.has(chunkIndex)) {
        newSet.delete(chunkIndex)
      } else {
        newSet.add(chunkIndex)
      }
      return newSet
    })
  }, [])

  const expandAllChunks = useCallback(() => {
    setIsDocumentExpanded(true)
    if (documentChunks && documentChunks.chunks) {
      setExpandedChunks(new Set(documentChunks.chunks.map(chunk => chunk.chunk_index)))
    }
  }, [documentChunks])

  const collapseAllChunks = useCallback(() => {
    setIsDocumentExpanded(false)
    setExpandedChunks(new Set())
  }, [])

  const toggleDocumentExpanded = useCallback(() => {
      setIsDocumentExpanded(prev => !prev)
  }, [])

  return {
    documentChunks,
    chunksLoading,
    expandedChunks,
    isDocumentExpanded,
    toggleChunk,
    expandAllChunks,
    collapseAllChunks,
    toggleDocumentExpanded
  }
}
