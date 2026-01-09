import React from 'react'
import { render, screen, within } from '@testing-library/react'
import StandardizedBreakdownTable from '../components/shared/tables/StandardizedBreakdownTable'

describe('Standardized Breakdown Table', () => {
  const formatNumber = (val) => val.toString()

  it('filters total lines and shows standardized references for other assets', () => {
    const data = {
      line_items: [
        {
          line_name: 'Deferred tax assets',
          line_value: 300,
          unit: 'millions',
          is_operating: true,
          category: 'Current Assets'
        }
      ]
    }

    // Mock balance sheet with a total line
    const balanceSheet = {
        unit: 'millions',
        line_items: [
            {
                line_name: 'Other Current Assets',
                line_value: 500,
                unit: 'millions',
                category: 'Current Assets'
            }
        ]
    }

    render(
      <StandardizedBreakdownTable
        data={data}
        balanceSheet={balanceSheet}
        formatNumber={formatNumber}
        standardReferences={[
            { id: 1, label: 'Other Current Assets', category: 'Current Assets' }
        ]}
      />
    )

    // Check that we see the section header
    expect(screen.getByRole('heading', { name: 'Other Current Assets' })).toBeInTheDocument()

    // The "Total" line from balance sheet should be visible as the "Standardized Line Item"
    // Since it appears multiple times (header, list, table row), we use getAllByText and check for at least one
    expect(screen.getAllByText('Other Current Assets').length).toBeGreaterThan(0)

    // The individual item should be there
    expect(screen.getByText('Deferred tax assets')).toBeInTheDocument()

    // Ref '1' is displayed for the total row in the new component logic
    // We find the row that contains "Other Current Assets" in the table body (has class col-name)
    const totalRow = screen.getAllByText('Other Current Assets')
        .find(el => el.classList.contains('col-name'))
        .closest('tr')
    expect(within(totalRow).getByText('1')).toBeInTheDocument()
  })

  it('filters total lines and shows standardized references for other liabilities', () => {
    const data = {
      line_items: [
        {
          line_name: 'Accrued expenses',
          line_value: 200,
          unit: 'millions',
          is_operating: true,
          category: 'Current Liabilities'
        }
      ]
    }

    const balanceSheet = {
        unit: 'millions',
        line_items: [
            {
                line_name: 'Other Current Liabilities',
                line_value: 400,
                unit: 'millions',
                category: 'Current Liabilities'
            }
        ]
    }

    render(
      <StandardizedBreakdownTable
        data={data}
        balanceSheet={balanceSheet}
        formatNumber={formatNumber}
        standardReferences={[
            { id: 1, label: 'Other Current Liabilities', category: 'Current Liabilities' }
        ]}
      />
    )

    // Check that we see the section header
    expect(screen.getByRole('heading', { name: 'Other Current Liabilities' })).toBeInTheDocument()

    // The "Total" line from balance sheet
    expect(screen.getAllByText('Other Current Liabilities').length).toBeGreaterThan(0)

    // The individual item
    expect(screen.getByText('Accrued expenses')).toBeInTheDocument()

    // Ref '1' is displayed for the total row
    const totalRow = screen.getAllByText('Other Current Liabilities')
        .find(el => el.classList.contains('col-name'))
        .closest('tr')
    expect(within(totalRow).getByText('1')).toBeInTheDocument()
  })
})
