// Common config
// In Vite, environment variables are accessed via import.meta.env
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

// Constants
export const ELIGIBLE_DOCUMENT_TYPES = [
    'earnings_announcement',
    'quarterly_filing',
    'annual_filing'
]
