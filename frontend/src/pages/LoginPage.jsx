import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import './LoginPage.css'

function LoginPage() {
  const { loginLocal, signup, loginGoogle } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState('login') // 'login' or 'signup'
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: ''
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const buttonRef = useRef(null)

  // --- Google Sign-In Initialization ---
  useEffect(() => {
    const loadGoogleSignIn = async () => {
      try {
        // Load Google Sign-In script if not already loaded
        if (!window.google) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script')
            script.src = 'https://accounts.google.com/gsi/client'
            script.async = true
            script.defer = true
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
          })
        }

        // Get Google OAuth client ID
        const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '356203245307-p36c44gejskle2kg60r47u2344gv9r94.apps.googleusercontent.com'

        // Initialize Google Identity Services
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleResponse,
        })

        // Render the sign-in button
        if (buttonRef.current) {
          window.google.accounts.id.renderButton(
            buttonRef.current,
            {
              theme: 'outline',
              size: 'large',
              width: 240,
              text: 'signin_with', // or 'signup_with'
            }
          )
        }
      } catch (err) {
        console.error('Google Sign-In initialization error:', err)
        setError('Failed to initialize Google Sign-In. Please use email login.')
      }
    }

    loadGoogleSignIn()
  }, []) // Initialize once

  const handleGoogleResponse = async (response) => {
    setLoading(true)
    setError(null)
    try {
      const success = await loginGoogle(response.credential)
      if (success) {
        navigate('/dashboard')
      } else {
        setError('Authentication failed. Please try again.')
      }
    } catch (err) {
      console.error('Login error:', err)
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // --- Form Handlers ---

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      let success;
      if (mode === 'signup') {
        if (!formData.first_name || !formData.last_name) {
          setError("Please enter your name.")
          setLoading(false)
          return
        }
        success = await signup(formData)
      } else {
        success = await loginLocal(formData.email, formData.password)
      }

      if (success) {
        navigate('/dashboard')
      } else {
        setError('Authentication failed.')
      }
    } catch (err) {
      console.error('Auth submit error:', err)
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-card">
          <h1 className="login-title">Tiger-Cafe</h1>
          <p className="login-subtitle">AI agents for equity investment analysis</p>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {/* Email/Password Form */}
          <form onSubmit={handleSubmit}>
            {mode === 'signup' && (
              <div className="row">
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">First Name</label>
                  <input
                    type="text"
                    className="form-input"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    placeholder="First"
                    required={mode === 'signup'}
                  />
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">Last Name</label>
                  <input
                    type="text"
                    className="form-input"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    placeholder="Last"
                    required={mode === 'signup'}
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email Address</label>
              <input
                type="email"
                className="form-input"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="name@example.com"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-input"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                placeholder={mode === 'signup' ? "Create a password" : "Enter your password"}
                required
                minLength={6}
              />
            </div>

            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? 'Processing...' : (mode === 'login' ? 'Sign In' : 'Create Account')}
            </button>
          </form>

          <div className="divider"><span>Or continue with</span></div>

          <div className="google-signin-container">
            <div ref={buttonRef} id="google-signin-button"></div>
          </div>

          <div className="toggle-mode">
            {mode === 'login' ? "Don't have an account? " : "Already have an account? "}
            <button
              type="button"
              className="toggle-link"
              onClick={() => {
                setMode(mode === 'login' ? 'signup' : 'login')
                setError(null)
                setFormData({ ...formData, email: '', password: '', first_name: '', last_name: '' })
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}

export default LoginPage
