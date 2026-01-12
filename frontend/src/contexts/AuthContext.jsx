import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'

export const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState(() => {
    return localStorage.getItem('tiger-cafe-token')
  })
  const isInitialLoad = React.useRef(true)

  // Helper to process successful auth response
  const handleAuthSuccess = async (accessToken) => {
    try {
      // Set token
      setToken(accessToken)
      localStorage.setItem('tiger-cafe-token', accessToken)
      axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`

      // Fetch User Profile
      const response = await axios.get(`${API_BASE_URL}/auth/me`)
      setUser(response.data)
      setIsAuthenticated(true)
      return true
    } catch (error) {
      console.error("Failed to initialize session:", error)
      logout()
      return false
    }
  }

  const verifyToken = async (existingToken) => {
    try {
      await handleAuthSuccess(existingToken)
    } catch (error) {
      logout()
    } finally {
      setLoading(false)
    }
  }

  // --- Auth Actions ---

  const loginLocal = async (email, password) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/login`, { email, password })
      return await handleAuthSuccess(response.data.access_token)
    } catch (error) {
      console.error('Local login error:', error)
      throw error
    }
  }

  const signup = async (userData) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/signup`, userData)
      return await handleAuthSuccess(response.data.access_token)
    } catch (error) {
      console.error('Signup error:', error)
      throw error
    }
  }

  const loginGoogle = async (googleToken) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/google-exchange`, { token: googleToken })
      return await handleAuthSuccess(response.data.access_token)
    } catch (error) {
      console.error('Google exchange error:', error)
      throw error
    }
  }

  const logout = () => {
    localStorage.removeItem('tiger-cafe-token')
    delete axios.defaults.headers.common['Authorization']
    setIsAuthenticated(false)
    setUser(null)
    setToken(null)
  }

  // --- Effects ---

  // Interceptor for 401s
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          const isAuthEndpoint = error.config?.url?.includes('/auth/') && !error.config?.url?.includes('/auth/me')

          if (!isAuthEndpoint && !isInitialLoad.current) {
            const currentToken = localStorage.getItem('tiger-cafe-token')
            if (currentToken && isAuthenticated) {
              console.log('Session expired. Logging out...')
              logout()
              setTimeout(() => window.location.href = '/login', 100)
            }
          }
        }
        return Promise.reject(error)
      }
    )
    return () => axios.interceptors.response.eject(interceptor)
  }, [isAuthenticated])

  // Initial Load
  useEffect(() => {
    if (token) {
      verifyToken(token)
    } else {
      setLoading(false)
    }

    const timer = setTimeout(() => {
      isInitialLoad.current = false
    }, 2000)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      user,
      loading,
      token,
      loginLocal,
      signup,
      loginGoogle,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
