import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import LeftPanel from '../components/LeftPanel'
import { UploadContext } from '../contexts/UploadContext'
import axios from 'axios'

// Mock axios
vi.mock('axios')

// Mock AuthContext
vi.mock('../contexts/AuthContext', () => ({
    useAuth: () => ({
        isAuthenticated: true,
        token: 'test-token'
    })
}))

// Mock UploadModal
vi.mock('../components/modals/UploadModal', () => ({
    default: () => <div>Upload Modal</div>
}))

// Mock UploadProgress
vi.mock('../components/modals/UploadProgressModal', () => ({
    default: () => <div>Upload Progress Modal</div>
}))

describe('LeftPanel Button Debouncing', () => {
    const mockSelectedCompany = { id: 1, name: 'Test Co' }
    const mockSelectedDocument = {
        id: 101,
        document_type: 'earnings_announcement',
        indexing_status: 'indexed',
        analysis_status: 'completed',
        filename: 'test.pdf'
    }
    const mockOnBack = vi.fn()
    const mockOnDocumentSelect = vi.fn()

    beforeEach(() => {
        vi.clearAllMocks()

        axios.get.mockImplementation((url) => {
            if (url.includes('/documents/101/status')) {
                return Promise.resolve({ data: mockSelectedDocument })
            }
            if (url.includes('/documents/101/balance-sheet')) {
                return Promise.resolve({ status: 200, data: { status: 'exists' } })
            }
            if (url.includes('/documents/101/income-statement')) {
                return Promise.resolve({ status: 200, data: { status: 'exists' } })
            }
            if (url.includes('/documents/101/file')) {
                return Promise.resolve({
                    status: 200,
                    data: new Blob(['test pdf'], { type: 'application/pdf' })
                })
            }
            if (url.includes('/companies/')) {
                return Promise.resolve({ data: [mockSelectedCompany] })
            }
            return Promise.resolve({ data: [] })
        })
        axios.post.mockResolvedValue({ data: {} })
        axios.delete.mockResolvedValue({ data: {} })

        // Mock URL.createObjectURL
        global.URL.createObjectURL = vi.fn(() => 'mock-url')
        global.URL.revokeObjectURL = vi.fn()

        // Mock window.confirm
        global.confirm = vi.fn(() => true)
    })

    it('prevents duplicate clicks on Re-run Indexing button', async () => {
        const mockUploadValue = {
            uploadingDocuments: [],
            loadUploadProgress: vi.fn(),
            showUploadProgress: false,
            setShowUploadProgress: vi.fn(),
        }

        render(
            <UploadContext.Provider value={mockUploadValue}>
                <LeftPanel
                    selectedCompany={mockSelectedCompany}
                    selectedDocument={mockSelectedDocument}
                    onBack={mockOnBack}
                    onDocumentSelect={mockOnDocumentSelect}
                />
            </UploadContext.Provider>
        )

        // Wait for button to be enabled
        const rerunButton = await screen.findByRole('button', { name: /Re-run Indexing/i })

        await waitFor(() => {
            expect(rerunButton).not.toBeDisabled()
        })

        // Click the button three times rapidly
        fireEvent.click(rerunButton)
        fireEvent.click(rerunButton)
        fireEvent.click(rerunButton)

        // Wait a bit for any async operations
        await new Promise(resolve => setTimeout(resolve, 100))

        // Only one API call should be made despite three clicks
        expect(axios.post).toHaveBeenCalledTimes(1)
        expect(axios.post).toHaveBeenCalledWith(
            expect.stringContaining('rerun-indexing'),
            {},
            expect.any(Object)
        )
    })

    it('prevents duplicate clicks on Re-run Extraction button', async () => {
        const mockUploadValue = {
            uploadingDocuments: [],
            loadUploadProgress: vi.fn(),
            showUploadProgress: false,
            setShowUploadProgress: vi.fn(),
        }

        render(
            <UploadContext.Provider value={mockUploadValue}>
                <LeftPanel
                    selectedCompany={mockSelectedCompany}
                    selectedDocument={mockSelectedDocument}
                    onBack={mockOnBack}
                    onDocumentSelect={mockOnDocumentSelect}
                />
            </UploadContext.Provider>
        )

        const extractionButton = await screen.findByRole('button', { name: /Re-run Extraction and Classification/i })

        await waitFor(() => {
            expect(extractionButton).not.toBeDisabled()
        })

        // Click multiple times rapidly
        fireEvent.click(extractionButton)
        fireEvent.click(extractionButton)

        await new Promise(resolve => setTimeout(resolve, 100))

        // Only one API call should be made
        expect(axios.post).toHaveBeenCalledTimes(1)
    })

    it('prevents duplicate clicks on Delete Financial Statements button', async () => {
        const mockUploadValue = {
            uploadingDocuments: [],
            loadUploadProgress: vi.fn(),
            showUploadProgress: false,
            setShowUploadProgress: vi.fn(),
        }

        render(
            <UploadContext.Provider value={mockUploadValue}>
                <LeftPanel
                    selectedCompany={mockSelectedCompany}
                    selectedDocument={mockSelectedDocument}
                    onBack={mockOnBack}
                    onDocumentSelect={mockOnDocumentSelect}
                />
            </UploadContext.Provider>
        )

        const deleteButton = await screen.findByRole('button', { name: /Delete Financial Statements/i })

        await waitFor(() => {
            expect(deleteButton).not.toBeDisabled()
        })

        // Click twice
        fireEvent.click(deleteButton)
        fireEvent.click(deleteButton)

        await new Promise(resolve => setTimeout(resolve, 100))

        // Only one API call should be made
        expect(axios.delete).toHaveBeenCalledTimes(1)
    })

    it('button is disabled during debounce period', async () => {
        const mockUploadValue = {
            uploadingDocuments: [],
            loadUploadProgress: vi.fn(),
            showUploadProgress: false,
            setShowUploadProgress: vi.fn(),
        }

        render(
            <UploadContext.Provider value={mockUploadValue}>
                <LeftPanel
                    selectedCompany={mockSelectedCompany}
                    selectedDocument={mockSelectedDocument}
                    onBack={mockOnBack}
                    onDocumentSelect={mockOnDocumentSelect}
                />
            </UploadContext.Provider>
        )

        const rerunButton = await screen.findByRole('button', { name: /Re-run Indexing/i })

        await waitFor(() => {
            expect(rerunButton).not.toBeDisabled()
        })

        // Click the button
        fireEvent.click(rerunButton)

        // Button should be disabled immediately after click
        await waitFor(() => {
            expect(rerunButton).toBeDisabled()
        })
    })
})
