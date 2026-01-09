import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { useAuth } from '../../../contexts/AuthContext'

const API_BASE_URL = 'http://localhost:8000/api'

function PdfViewer({ documentId }) {
    const [pdfUrl, setPdfUrl] = useState(null)
    const pdfUrlRef = useRef(null)
    const { isAuthenticated, token } = useAuth()

    useEffect(() => {
        const loadPdfDocument = async (docId) => {
            try {
                // Revoke previous URL if exists
                if (pdfUrlRef.current) {
                    URL.revokeObjectURL(pdfUrlRef.current)
                    pdfUrlRef.current = null
                }

                // Use test endpoint if not authenticated (for development)
                const endpoint = isAuthenticated ? 'file' : 'file-test'
                const url = `${API_BASE_URL}/documents/${docId}/${endpoint}`

                // Fetch PDF as blob to include authentication headers
                const response = await axios.get(url, {
                    responseType: 'blob',
                    headers: isAuthenticated && token ? {
                        'Authorization': `Bearer ${token}`
                    } : {}
                })

                // Create object URL from blob
                const blob = new Blob([response.data], { type: 'application/pdf' })
                const objectUrl = URL.createObjectURL(blob)
                pdfUrlRef.current = objectUrl
                setPdfUrl(objectUrl)
            } catch (error) {
                console.error('Error loading PDF:', error)
                setPdfUrl(null)
                pdfUrlRef.current = null
            }
        }

        if (documentId) {
            loadPdfDocument(documentId)
        } else {
            // Revoke URL when document is deselected
            if (pdfUrlRef.current) {
                URL.revokeObjectURL(pdfUrlRef.current)
                pdfUrlRef.current = null
            }
            setPdfUrl(null)
        }

        // Cleanup: revoke object URL when component unmounts or document changes
        return () => {
            if (pdfUrlRef.current) {
                URL.revokeObjectURL(pdfUrlRef.current)
                pdfUrlRef.current = null
            }
        }
    }, [documentId, isAuthenticated, token])

    if (!pdfUrl) {
        return null
    }

    return (
        <div className="pdf-viewer-container">
            <iframe
                src={pdfUrl}
                title="Document PDF"
                className="pdf-viewer"
            />
        </div>
    )
}

export default PdfViewer
