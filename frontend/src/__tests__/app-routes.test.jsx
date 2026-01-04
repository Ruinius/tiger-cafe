import React from 'react'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import App from '../App'

let authState = {
  isAuthenticated: false,
  loading: false
}

vi.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => <div>{children}</div>,
  useAuth: () => authState
}))

vi.mock('../pages/LoginPage', () => ({
  default: () => <div>Login Page</div>
}))

vi.mock('../pages/Dashboard', () => ({
  default: () => <div>Dashboard Page</div>
}))

describe('App routing', () => {
  it('redirects unauthenticated users to login', () => {
    authState = { isAuthenticated: false, loading: false }
    window.history.pushState({}, 'Login', '/dashboard')

    render(<App />)

    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('redirects authenticated users to dashboard', () => {
    authState = { isAuthenticated: true, loading: false }
    window.history.pushState({}, 'Dashboard', '/login')

    render(<App />)

    expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
  })
})
