
export const formatNumber = (value, unit = null) => {
  if (value === null || value === undefined) return 'N/A'

  // Values are stored in the reported unit (e.g., 100 if unit is "millions" means 100 million)
  // Display them as-is without conversion - the unit column shows the scale
  const displayValue = parseFloat(value)

  // Format as number with thousands separators, no currency symbol
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(displayValue)
}

export const formatPercent = (value, multiplier = 1) => {
  if (value === null || value === undefined) return 'N/A'
  const percentValue = parseFloat(value) * multiplier
  if (Number.isNaN(percentValue)) return 'N/A'
  return `${percentValue.toFixed(2)}%`
}

export const formatDecimal = (value, digits = 4) => {
  if (value === null || value === undefined) return 'N/A'
  const numericValue = parseFloat(value)
  if (Number.isNaN(numericValue)) return 'N/A'
  return numericValue.toFixed(digits)
}
