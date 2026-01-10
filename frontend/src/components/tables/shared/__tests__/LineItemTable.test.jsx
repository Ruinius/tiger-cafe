import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import LineItemTable from '../LineItemTable'

describe('LineItemTable', () => {
    const mockData = {
        line_items: [
            { line_name: 'Revenue', line_value: 1000, unit: 'millions', category: 'Sales Category', is_operating: true },
            { line_name: 'Cost of Sales', line_value: 500, unit: 'millions', category: 'Cost', is_operating: true },
            { line_name: 'Other Expense', line_value: 50, unit: 'millions', category: 'Other', is_operating: false }
        ],
        currency: 'USD',
        unit: 'millions',
        time_period: 'FY2023'
    }

    const mockFormatNumber = (val) => val.toString()

    it('renders without crashing', () => {
        const { container } = render(<LineItemTable data={mockData} formatNumber={mockFormatNumber} />)
        expect(container).toBeTruthy()
    })

    it('renders correct header information', () => {
        render(<LineItemTable data={mockData} formatNumber={mockFormatNumber} />)
        expect(screen.getByText(/Currency:/)).toBeInTheDocument()
        expect(screen.getByText('USD')).toBeInTheDocument()
        expect(screen.getByText(/Time Period:/)).toBeInTheDocument()
        expect(screen.getByText('FY2023')).toBeInTheDocument()
    })

    it('renders line items correctly', () => {
        render(<LineItemTable data={mockData} formatNumber={mockFormatNumber} />)
        expect(screen.getByText('Revenue')).toBeInTheDocument()
        expect(screen.getByText('Cost of Sales')).toBeInTheDocument()
        expect(screen.getByText('1000')).toBeInTheDocument()
        expect(screen.getByText('500')).toBeInTheDocument()
    })

    it('renders operating/non-operating badges', () => {
        render(<LineItemTable data={mockData} formatNumber={mockFormatNumber} />)
        const operatingBadges = screen.getAllByText('Operating')
        expect(operatingBadges.length).toBeGreaterThan(0)
        expect(screen.getByText('Non-Operating')).toBeInTheDocument()
    })
})
