import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Dashboard from '../pages/Dashboard'
import { AuthContext } from '../contexts/AuthContext'
import { ThemeContext } from '../contexts/ThemeContext'
import { UploadContext } from '../contexts/UploadContext'

// Mock the complex child components to isolate Dashboard testing
vi.mock('../components/LeftPanel', () => ({
    default: () => <div data-testid="left-panel">Left Panel Mock</div>
}))

vi.mock('../components/RightPanel', () => ({
    default: () => <div data-testid="right-panel">Right Panel Mock</div>
}))

vi.mock('../components/Header', () => ({
    default: ({ user }) => <div data-testid="header">Header Mock: {user?.name}</div>
}))

vi.mock('../components/SplitScreen', () => ({
    default: ({ left, right }) => (
        <div data-testid="split-screen">
            {left}
            {right}
        </div>
    )
}))

describe('Dashboard Component', () => {
    it('renders the full dashboard layout when authenticated', () => {
        const mockAuthValue = {
            isAuthenticated: true,
            user: { name: 'Test User' },
            logout: vi.fn(),
            loading: false
        }

        const mockThemeValue = {
            theme: 'light',
            toggleTheme: vi.fn()
        }

        const mockUploadValue = {
            uploadingDocuments: [],
            // Add other used functions as no-ops
            loadUploadProgress: vi.fn(),
        }

        render(
            <AuthContext.Provider value={mockAuthValue}>
                <ThemeContext.Provider value={mockThemeValue}>
                    <UploadContext.Provider value={mockUploadValue}>
                        <Dashboard />
                    </UploadContext.Provider>
                </ThemeContext.Provider>
            </AuthContext.Provider>
        )

        // Verify the main structure is present
        // 1. Header should be rendered with user data
        expect(screen.getByTestId('header')).toBeDefined()
        expect(screen.getByText(/Test User/)).toBeDefined()

        // 2. SplitScreen container should be rendered
        expect(screen.getByTestId('split-screen')).toBeDefined()

        // 3. Left and Right panels should be rendered inside
        expect(screen.getByTestId('left-panel')).toBeDefined()
        expect(screen.getByTestId('right-panel')).toBeDefined()
    })
})
