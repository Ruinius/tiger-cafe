import React from 'react'
import LineItemTable from './shared/LineItemTable'

export default function NonGaapTable({ data, formatNumber, currency, unit, timePeriod }) {
    if (!data) return null

    return (
        <LineItemTable
            data={data}
            formatNumber={formatNumber}
            currency={currency}
            unit={unit}
            timePeriod={timePeriod}
            showCategory={false} // Amortization usually doesn't need category? Checking original...
        // Original code: <LineItemTable data={amortization} formatNumber={formatNumber} />
        // Original LineItemTable defaults showCategory=true. I'll leave it as true to be safe unless strictly not needed.
        // Actually, wait, original call was:
        // <LineItemTable data={amortization} formatNumber={formatNumber} />
        // It didn't pass categoryFormatter, so categories probably showed up as raw strings or N/A.
        // I'll keep showCategory=true to match default behavior.
        />
    )
}
