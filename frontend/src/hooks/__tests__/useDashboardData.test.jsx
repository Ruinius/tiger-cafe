import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useDashboardData } from '../useDashboardData'
import axios from 'axios'
import { API_BASE_URL } from '../../config'

// Mock axios
vi.mock('axios')

describe('useDashboardData', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with default state', async () => {
    // Mock the axios get call to return an empty list immediately or delay
    axios.get.mockResolvedValue({ data: [] })

    const { result } = renderHook(() => useDashboardData())

    expect(result.current.companies).toEqual([])
    expect(result.current.filteredCompanies).toEqual([])
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBe(null)
    expect(result.current.searchQuery).toBe('')

    // Wait for the effect to finish
    await waitFor(() => {
        expect(result.current.loading).toBe(false)
    })
  })

  it('fetches companies successfully', async () => {
    const mockCompanies = [
      { id: 1, name: 'Apple', ticker: 'AAPL' },
      { id: 2, name: 'Microsoft', ticker: 'MSFT' }
    ]
    axios.get.mockResolvedValue({ data: mockCompanies })

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.companies).toEqual(mockCompanies)
    expect(result.current.filteredCompanies).toEqual(mockCompanies)
    expect(result.current.error).toBe(null)
    expect(axios.get).toHaveBeenCalledWith(`${API_BASE_URL}/companies/`)
  })

  it('handles fetch error', async () => {
    const error = new Error('Network error')
    axios.get.mockRejectedValue(error)

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.companies).toEqual([])
    expect(result.current.error).toEqual(error)
  })

  it('filters companies by search query', async () => {
    const mockCompanies = [
      { id: 1, name: 'Apple', ticker: 'AAPL' },
      { id: 2, name: 'Microsoft', ticker: 'MSFT' },
      { id: 3, name: 'Google', ticker: 'GOOGL' }
    ]
    axios.get.mockResolvedValue({ data: mockCompanies })

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Search by name
    await waitFor(() => {
        result.current.setSearchQuery('Apple')
    })

    expect(result.current.filteredCompanies).toHaveLength(1)
    expect(result.current.filteredCompanies[0].name).toBe('Apple')

    // Search by ticker (case insensitive)
    await waitFor(() => {
        result.current.setSearchQuery('msft')
    })
    expect(result.current.filteredCompanies).toHaveLength(1)
    expect(result.current.filteredCompanies[0].ticker).toBe('MSFT')
  })
})
