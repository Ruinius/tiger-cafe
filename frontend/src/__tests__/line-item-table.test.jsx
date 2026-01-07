import React from 'react'
import { render, screen } from '@testing-library/react'
import LineItemTable from '../components/LineItemTable'

describe('LineItemTable', () => {
  const formatNumber = (val) => val.toString()

  it('renders line items correctly', () => {
    const data = {
      currency: 'USD',
      unit: 'millions',
      line_items: [
        {
          line_name: 'Test Item',
          line_value: 100,
          unit: 'millions',
          is_operating: true,
          category: 'Test Category'
        }
      ]
    }

    render(<LineItemTable data={data} formatNumber={formatNumber} />)

    expect(screen.getByText('Test Item')).toBeInTheDocument()
    expect(screen.getByText('Test Category')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('Operating')).toBeInTheDocument()
  })

  it('supports type override', () => {
    const data = {
      line_items: [
        {
          line_name: 'Test Item',
          line_value: 100,
          unit: 'millions',
          is_operating: true,
          category: 'Test Category'
        }
      ]
    }

    render(
        <LineItemTable
            data={data}
            formatNumber={formatNumber}
            typeOverride={<span>Overridden Type</span>}
        />
    )

    expect(screen.getByText('Overridden Type')).toBeInTheDocument()
    expect(screen.queryByText('Operating')).not.toBeInTheDocument()
  })

  it('supports category formatter', () => {
    const data = {
      line_items: [
        {
          line_name: 'Test Item',
          line_value: 100,
          unit: 'millions',
          category: 'raw_category_name'
        }
      ]
    }

    const categoryFormatter = (cat) => cat.replace(/_/g, ' ').toUpperCase()

    render(
        <LineItemTable
            data={data}
            formatNumber={formatNumber}
            categoryFormatter={categoryFormatter}
        />
    )

    expect(screen.getByText('RAW CATEGORY NAME')).toBeInTheDocument()
  })
})
