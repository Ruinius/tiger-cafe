import React from 'react'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import axios from 'axios'
import RightPanel from '../components/RightPanel'

// Mock axios
vi.mock('axios')

// Mock useAuth
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    token: 'test-token'
  })
}))

// Mock all table components to avoid complex dependencies
vi.mock('../components/AmortizationTable', () => ({
  default: () => <div data-testid="amortization-table">Amortization Table</div>
}))

vi.mock('../components/NonOperatingClassificationTable', () => ({
  default: () => <div data-testid="non-operating-table">Non-Operating Table</div>
}))

vi.mock('../components/OrganicGrowthTable', () => ({
  default: () => <div data-testid="organic-growth-table">Organic Growth Table</div>
}))

vi.mock('../components/OtherAssetsTable', () => ({
  default: () => <div data-testid="other-assets-table">Other Assets Table</div>
}))

vi.mock('../components/OtherLiabilitiesTable', () => ({
  default: () => <div data-testid="other-liabilities-table">Other Liabilities Table</div>
}))

vi.mock('../components/SharesOutstandingTable', () => ({
  default: () => <div data-testid="shares-outstanding-table">Shares Outstanding Table</div>
}))

// Mock CSS import
vi.mock('../components/RightPanel.css', () => ({}))

describe('RightPanel null handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock axios.get to return empty responses
    axios.get.mockResolvedValue({ data: null })
  })

  it('renders without crashing when financial data objects are null', async () => {
    const selectedDocument = {
      id: 'test-doc-id',
      document_type: 'quarterly_filing',
      time_period: 'Q1 2024'
    }

    // This test verifies that the component doesn't throw errors when
    // organicGrowth, incomeStatement, and historicalCalculations are null
    // Specifically tests the fix for null checks in the summary table section
    const { container } = render(
      <RightPanel 
        selectedCompany={null} 
        selectedDocument={selectedDocument}
      />
    )

    // The component should render without throwing "Cannot read properties of null" errors
    expect(container).toBeInTheDocument()
  })

  it('handles null organicGrowth object without errors', () => {
    const selectedDocument = {
      id: 'test-doc-id',
      document_type: 'quarterly_filing',
      time_period: 'Q1 2024'
    }

    // Mock axios to return responses that result in null state values
    axios.get.mockImplementation((url) => {
      if (url.includes('financial-statement-progress')) {
        return Promise.resolve({
          data: {
            status: 'not_started',
            milestones: {}
          }
        })
      }
      // Return 404 for other endpoints to simulate no data
      return Promise.reject({ response: { status: 404 } })
    })

    const { container } = render(
      <RightPanel 
        selectedCompany={null} 
        selectedDocument={selectedDocument}
      />
    )

    // Component should render without errors even when data is null
    expect(container).toBeInTheDocument()
  })
})

