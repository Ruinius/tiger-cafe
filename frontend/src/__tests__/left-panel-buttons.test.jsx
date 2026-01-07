import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import LeftPanel from '../components/LeftPanel'
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
vi.mock('../components/UploadModal', () => ({
    default: () => <div>Upload Modal</div>
}))

describe('LeftPanel Buttons', () => {
    const mockSelectedCompany = { id: 1, name: 'Test Co' }
    const mockSelectedDocument = {
        id: 101,
        document_type: 'earnings_announcement',
        indexing_status: 'indexed',
        analysis_status: 'completed'
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

        // Mock URL.createObjectURL
        global.URL.createObjectURL = vi.fn(() => 'mock-url')
        global.URL.revokeObjectURL = vi.fn()
    })

    it('disables "Re-run Extraction and Classification" button after clicking it', async () => {
        render(
            <LeftPanel
                selectedCompany={mockSelectedCompany}
                selectedDocument={mockSelectedDocument}
                onBack={mockOnBack}
                onDocumentSelect={mockOnDocumentSelect}
            />
        )

        // Wait for the button to be loaded and enabled (after checkFinancialStatements finishes)
        const rerunButton = await screen.findByRole('button', { name: /Re-run Extraction and Classification/i })
        expect(rerunButton).not.toBeDisabled()

        // Click the button
        fireEvent.click(rerunButton)

        // It should be disabled immediately
        expect(rerunButton).toBeDisabled()
    })

    it('disables all re-run and delete buttons during processing state', async () => {
        // Reset mocks to ensure no interference from beforeEach
        axios.get.mockReset()

        // Modify doc to be in processing state
        const processingDoc = { ...mockSelectedDocument, analysis_status: 'processing' }

        // Define mock with processing status
        axios.get.mockImplementation((url) => {
            if (url.includes('/documents/101/status')) {
                return Promise.resolve({ data: processingDoc })
            }
            // Keep other mocks
            if (url.includes('/documents/101/balance-sheet')) return Promise.resolve({ status: 200, data: { status: 'exists' } })
            if (url.includes('/documents/101/income-statement')) return Promise.resolve({ status: 200, data: { status: 'exists' } })
            if (url.includes('/companies/')) return Promise.resolve({ data: [mockSelectedCompany] })
            return Promise.resolve({ data: [] })
        })

        render(
            <LeftPanel
                selectedCompany={mockSelectedCompany}
                selectedDocument={processingDoc}
                onBack={mockOnBack}
                onDocumentSelect={mockOnDocumentSelect}
            />
        )

        // Buttons should be disabled based on processing status
        const extractionButton = await screen.findByRole('button', { name: /Re-run Extraction and Classification/i })
        const indexingButton = await screen.findByRole('button', { name: /Re-run Indexing/i })
        const calculationsButton = await screen.findByRole('button', { name: /Re-run Historical Calculations/i })
        const deleteStatementsButton = await screen.findByRole('button', { name: /Delete Financial Statements/i })
        const deleteDocButton = await screen.findByRole('button', { name: /Delete Document/i })

        expect(extractionButton).toBeDisabled()
        expect(indexingButton).toBeDisabled()
        expect(calculationsButton).toBeDisabled()
        expect(deleteStatementsButton).toBeDisabled()
        expect(deleteDocButton).toBeDisabled()
    })

    it('disables indexing button when indexing_status is indexing', async () => {
        const indexingDoc = { ...mockSelectedDocument, indexing_status: 'indexing' }

        render(
            <LeftPanel
                selectedCompany={mockSelectedCompany}
                selectedDocument={indexingDoc}
                onBack={mockOnBack}
                onDocumentSelect={mockOnDocumentSelect}
            />
        )

        const indexingButton = await screen.findByRole('button', { name: /Re-run Indexing/i })
        expect(indexingButton).toBeDisabled()
    })
})
