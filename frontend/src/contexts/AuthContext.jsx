import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'

const AuthContext = createContext()

const API_BASE_URL = 'http://localhost:8000/api'

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState(() => {
    return localStorage.getItem('tiger-cafe-token')
  })
  const isInitialLoad = React.useRef(true)

  const verifyToken = async (idToken) => {
    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${idToken}`
      const response = await axios.get(`${API_BASE_URL}/auth/me`)
      setUser(response.data)
      setIsAuthenticated(true)
      setToken(idToken)
      localStorage.setItem('tiger-cafe-token', idToken)
    } catch (error) {
      // Token invalid, clear it
      localStorage.removeItem('tiger-cafe-token')
      delete axios.defaults.headers.common['Authorization']
      setIsAuthenticated(false)
      setUser(null)
      setToken(null)
    } finally {
      setLoading(false)
    }
  }

  // Set up axios response interceptor to handle authentication failures
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        // If we get a 401 Unauthorized, the token has expired
        if (error.response && error.response.status === 401) {
          // Skip if this is from the auth/me endpoint (initial verification)
          // or if we're still in the initial load phase
          const isAuthEndpoint = error.config?.url?.includes('/auth/me')
          
          if (!isAuthEndpoint && !isInitialLoad.current) {
            // Only log out if we were previously authenticated (avoid loops)
            const currentToken = localStorage.getItem('tiger-cafe-token')
            if (currentToken && isAuthenticated) {
              console.log('Authentication expired. Logging out...')
              // Clear token and state
              localStorage.removeItem('tiger-cafe-token')
              delete axios.defaults.headers.common['Authorization']
              setIsAuthenticated(false)
              setUser(null)
              setToken(null)
              // Use window.location to ensure full redirect (prevents stale state)
              setTimeout(() => {
                window.location.href = '/login'
              }, 100)
            }
          }
        }
        return Promise.reject(error)
      }
    )

    // Cleanup interceptor on unmount
    return () => {
      axios.interceptors.response.eject(interceptor)
    }
  }, [isAuthenticated])

  useEffect(() => {
    // Check if user is authenticated on mount
    if (token) {
      verifyToken(token).catch((error) => {
        // Error already handled in verifyToken, but ensure loading is set
        console.error('Token verification error:', error)
      })
    } else {
      setLoading(false)
    }
    
    // Mark initial load as complete after a short delay
    const timer = setTimeout(() => {
      isInitialLoad.current = false
    }, 3000) // Allow 3 seconds for initial token verification
    
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = async (idToken) => {
    try {
      await verifyToken(idToken)
      return true
    } catch (error) {
      console.error('Login error:', error)
      return false
    }
  }

  const logout = () => {
    localStorage.removeItem('tiger-cafe-token')
    delete axios.defaults.headers.common['Authorization']
    setIsAuthenticated(false)
    setUser(null)
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ 
      isAuthenticated, 
      user, 
      loading, 
      login, 
      logout,
      token 
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


