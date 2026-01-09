import React from 'react'
import LineItemTable from './shared/LineItemTable'

export default function BalanceSheetTable({ data, formatNumber }) {
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
            // Balance sheet usually maps 1:1 with its own metadata
            currency={data.currency}
            unit={data.unit}
            timePeriod={data.time_period}
        />
    )
}
