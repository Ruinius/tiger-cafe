import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import SummaryTable from '../SummaryTable'

describe('SummaryTable', () => {
    const mockFormatNumber = (val) => val.toString()

    const mockHistoricalCalculations = {
        time_period: 'FY2023',
        ebita: 200,
        nopat: 150,
        invested_capital: 1000,
        roic: 0.18,
        calculation_notes: null
    }

    const mockIncomeStatement = {
        total_revenue: 1000,
        currency: 'USD',
        unit: 'millions',
        basic_shares_outstanding: 50,
        diluted_shares_outstanding: 55
    }

    const mockOrganicGrowth = {
        organic_revenue_growth: 5.5,
        current_period_revenue: 1000
    }

    it('renders without crashing', () => {
        const { container } = render(
            <SummaryTable
                historicalCalculations={mockHistoricalCalculations}
                incomeStatement={mockIncomeStatement}
                organicGrowth={mockOrganicGrowth}
                formatNumber={mockFormatNumber}
            />
        )
        expect(container).toBeTruthy()
    })

    it('calculates and renders margins correctly', () => {
        render(
            <SummaryTable
                historicalCalculations={mockHistoricalCalculations}
                incomeStatement={mockIncomeStatement}
                organicGrowth={mockOrganicGrowth}
                formatNumber={mockFormatNumber}
            />
        )

        // Revenue 1000, EBITA 200 -> Margin 20%
        expect(screen.getByText('EBITA Margin')).toBeInTheDocument()
        expect(screen.getByText('20.00%')).toBeInTheDocument()
    })

    it('renders shares outstanding', () => {
        render(
            <SummaryTable
                historicalCalculations={mockHistoricalCalculations}
                incomeStatement={mockIncomeStatement}
                organicGrowth={mockOrganicGrowth}
                formatNumber={mockFormatNumber}
            />
        )
        expect(screen.getByText('Diluted Shares Outstanding')).toBeInTheDocument()
        expect(screen.getByText('55')).toBeInTheDocument()
    })
})
