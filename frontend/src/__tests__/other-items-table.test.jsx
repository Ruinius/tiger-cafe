import React from 'react'
import { render, screen, within } from '@testing-library/react'
import OtherAssetsTable from '../components/OtherAssetsTable'
import OtherLiabilitiesTable from '../components/OtherLiabilitiesTable'

describe('Other assets/liabilities tables', () => {
  const formatNumber = () => '100'

  it('filters total lines and shows standardized references for other assets', () => {
    const data = {
      line_items: [
        {
          line_name: 'Other Current Assets',
          line_value: 500,
          unit: 'millions',
          is_operating: true,
          category: 'Current Assets'
        },
        {
          line_name: 'Deferred tax assets',
          line_value: 300,
          unit: 'millions',
          is_operating: true,
          category: 'Current Assets'
        }
      ]
    }

    render(<OtherAssetsTable data={data} formatNumber={formatNumber} />)

    const assetsTable = screen.getByRole('table')
    expect(within(assetsTable).queryByText('Other Current Assets')).not.toBeInTheDocument()
    const row = screen.getByText('Deferred tax assets').closest('tr')
    expect(within(row).getByText('1')).toBeInTheDocument()
  })

  it('filters total lines and shows standardized references for other liabilities', () => {
    const data = {
      line_items: [
        {
          line_name: 'Other Current Liabilities',
          line_value: 400,
          unit: 'millions',
          is_operating: false,
          category: 'Current Liabilities'
        },
        {
          line_name: 'Accrued expenses',
          line_value: 200,
          unit: 'millions',
          is_operating: true,
          category: 'Current Liabilities'
        }
      ]
    }

    render(<OtherLiabilitiesTable data={data} formatNumber={formatNumber} />)

    const liabilitiesTable = screen.getByRole('table')
    expect(within(liabilitiesTable).queryByText('Other Current Liabilities')).not.toBeInTheDocument()
    const row = screen.getByText('Accrued expenses').closest('tr')
    expect(within(row).getByText('1')).toBeInTheDocument()
  })
})
