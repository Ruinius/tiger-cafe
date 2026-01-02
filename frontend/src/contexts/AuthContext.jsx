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

  useEffect(() => {
    // Check if user is authenticated on mount
    if (token) {
      verifyToken(token)
    } else {
      setLoading(false)
    }
  }, [])

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


