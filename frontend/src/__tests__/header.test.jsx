import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import Header from '../components/Header'

describe('Header', () => {
  it('shows user details and triggers logout', async () => {
    const onLogout = vi.fn()
    const onThemeToggle = vi.fn()

    render(
      <Header
        user={{ name: 'Pat Lee', email: 'pat@example.com' }}
        onLogout={onLogout}
        theme="light"
        onThemeToggle={onThemeToggle}
      />
    )

    expect(screen.getByText('Tiger-Cafe')).toBeInTheDocument()
    expect(screen.getByText('Pat Lee')).toBeInTheDocument()
    const logoutButton = screen.getByRole('button', { name: 'Sign out' })
    await userEvent.click(logoutButton)

    expect(onLogout).toHaveBeenCalledTimes(1)
    expect(onThemeToggle).not.toHaveBeenCalled()
  })

  it('toggles theme button state', async () => {
    const onLogout = vi.fn()
    const onThemeToggle = vi.fn()

    render(
      <Header
        user={null}
        onLogout={onLogout}
        theme="dark"
        onThemeToggle={onThemeToggle}
      />
    )

    const toggleButton = screen.getByRole('button', { name: 'Toggle theme' })
    expect(toggleButton).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Dark')).toBeInTheDocument()

    await userEvent.click(toggleButton)

    expect(onThemeToggle).toHaveBeenCalledTimes(1)
    expect(onLogout).not.toHaveBeenCalled()
  })
})
