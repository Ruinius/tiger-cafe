import React from 'react'
import LineItemTable from './shared/LineItemTable'

export default function NonOperatingClassificationTable({ data, formatNumber, currency, unit, timePeriod }) {
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
            typeOverride={<span className="type-badge non-operating">Non-Operating</span>}
            currency={currency}
            unit={unit}
            timePeriod={timePeriod}
        />
    )
}
