import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'

export function useDashboardData() {
  const [companies, setCompanies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  const loadCompanies = useCallback(async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/companies/`)
      setCompanies(response.data)
      setError(null)
    } catch (err) {
      console.error('Error loading companies:', err)
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Poll for companies periodically (optional, but good for multi-user or background updates)
  // For now, we'll stick to load on mount and manual refresh as needed.

  useEffect(() => {
    loadCompanies()
  }, [loadCompanies])

  const filteredCompanies = companies.filter(company =>
    company.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (company.ticker && company.ticker.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return {
    companies,
    filteredCompanies,
    loading,
    error,
    searchQuery,
    setSearchQuery,
    loadCompanies,
  }
}
