import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import './LoginPage.css'

function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const buttonRef = useRef(null)

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
          callback: handleCredentialResponse,
        })

        // Render the sign-in button
        if (buttonRef.current) {
          window.google.accounts.id.renderButton(
            buttonRef.current,
            {
              theme: 'outline',
              size: 'large',
              width: 240,
              text: 'signin_with',
            }
          )
        }
      } catch (err) {
        console.error('Google Sign-In initialization error:', err)
        setError('Failed to initialize Google Sign-In. Please refresh the page.')
      }
    }

    loadGoogleSignIn()
  }, [])

  const handleCredentialResponse = async (response) => {
    setLoading(true)
    setError(null)

    try {
      const success = await login(response.credential)
      if (success) {
        navigate('/dashboard')
      } else {
        setError('Authentication failed. Please try again.')
      }
    } catch (err) {
      console.error('Login error:', err)
      setError('Authentication failed. Please try again.')
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

          <div className="google-signin-container">
            <div ref={buttonRef} id="google-signin-button"></div>
            {loading && <div className="loading-spinner">Signing in...</div>}
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage

