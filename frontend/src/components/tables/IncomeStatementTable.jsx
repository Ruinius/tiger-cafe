import React from 'react'
import LineItemTable from './shared/LineItemTable'

export default function IncomeStatementTable({ data, formatNumber }) {
    if (!data) return null

    const formatCategoryLabel = (category) => {
        if (!category) return 'N/A'
        return category.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }

    return (
        <LineItemTable
            data={data}
            formatNumber={formatNumber}
            categoryFormatter={formatCategoryLabel}
            currency={data.currency}
            unit={data.unit}
            timePeriod={data.time_period}
        />
    )
}
