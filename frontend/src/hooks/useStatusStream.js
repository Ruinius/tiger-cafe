import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { API_BASE_URL } from '../config'

/**
 * Custom hook to connect to SSE status stream for real-time document updates.
 * Replaces polling-based status checks with Server-Sent Events.
 */
export function useStatusStream() {
    const { isAuthenticated, token } = useAuth()
    const [activeDocuments, setActiveDocuments] = useState([])
    const [isConnected, setIsConnected] = useState(false)
    const [error, setError] = useState(null)
    const eventSourceRef = useRef(null)
    const reconnectTimeoutRef = useRef(null)
    const reconnectAttempts = useRef(0)
    const previousTokenRef = useRef(token)

    const MAX_RECONNECT_ATTEMPTS = 5
    const RECONNECT_DELAY = 3000 // 3 seconds

    const disconnect = useCallback(() => {
        if (eventSourceRef.current) {
            console.log('[SSE] Disconnecting')
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        setIsConnected(false)
        setActiveDocuments([])
    }, [])

    // Helper to check if token is expired
    const isTokenExpired = useCallback((token) => {
        if (!token) return true
        try {
            const base64Url = token.split('.')[1]
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
            const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function (c) {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
            }).join(''))
            const { exp } = JSON.parse(jsonPayload)
            return exp * 1000 < Date.now()
        } catch (e) {
            return true
        }
    }, [])

    const connect = useCallback(() => {
        // Don't connect if not authenticated or token is missing/expired
        if (!isAuthenticated || !token) {
            disconnect()
            return
        }

        if (isTokenExpired(token)) {
            console.log('[SSE] Token expired, skipping connection')
            setError('Session expired')
            disconnect()
            return
        }

        // Close existing connection if any
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        try {
            // Create SSE connection
            // Note: EventSource doesn't support custom headers, so we pass token as query param
            const url = `${API_BASE_URL}/documents/status-stream?token=${encodeURIComponent(token)}`
            const eventSource = new EventSource(url)

            eventSource.onopen = () => {
                console.log('[SSE] Connection opened')
                setIsConnected(true)
                setError(null)
                reconnectAttempts.current = 0
            }

            eventSource.addEventListener('status_update', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    setActiveDocuments(data)
                } catch (err) {
                    console.error('[SSE] Error parsing status update:', err)
                }
            })

            eventSource.onerror = (err) => {
                console.error('[SSE] Connection error:', err)
                setIsConnected(false)
                eventSource.close()

                // Check if token expired before retrying
                if (isTokenExpired(token)) {
                    console.log('[SSE] Token expired, stopping reconnection')
                    setError('Session expired')
                    return
                }

                // Attempt to reconnect with exponential backoff
                if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
                    const delay = RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current)
                    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)

                    reconnectTimeoutRef.current = setTimeout(() => {
                        reconnectAttempts.current += 1
                        connect()
                    }, delay)
                } else {
                    setError('Failed to connect to status stream after multiple attempts')
                }
            }

            eventSourceRef.current = eventSource
        } catch (err) {
            console.error('[SSE] Failed to create EventSource:', err)
            setError(err.message)
        }
    }, [isAuthenticated, token, disconnect, isTokenExpired])

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        connect()

        return () => {
            disconnect()
        }
    }, [connect, disconnect])

    // Reconnect when token changes (e.g., user logs in/out or token refreshes)
    useEffect(() => {
        if (previousTokenRef.current !== token) {
            console.log('[SSE] Token changed, reconnecting...')
            previousTokenRef.current = token
            disconnect()
            if (isAuthenticated && token) {
                // Small delay to ensure clean disconnection
                setTimeout(() => {
                    connect()
                }, 100)
            }
        }
    }, [token, isAuthenticated, connect, disconnect])

    return {
        activeDocuments,
        isConnected,
        error,
        reconnect: connect,
        disconnect
    }
}
