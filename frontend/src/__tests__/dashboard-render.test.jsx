import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Dashboard from '../pages/Dashboard'
import { AuthContext } from '../contexts/AuthContext'
import { ThemeContext } from '../contexts/ThemeContext'
import { UploadStateContext, UploadDispatchContext } from '../contexts/UploadContext'

// Mock the child components to isolate Dashboard testing
vi.mock('../components/layout/Header', () => ({
    default: ({ user }) => <div data-testid="header">Header Mock: {user?.name}</div>
}))

vi.mock('../components/layout/SplitScreen', () => ({
    default: ({ left, right }) => (
        <div data-testid="split-screen">
            <div data-testid="left-panel">{left}</div>
            <div data-testid="right-panel">{right}</div>
        </div>
    )
}))

// Mock View Components
vi.mock('../components/views/global/CompanyList', () => ({
    default: () => <div data-testid="company-list">Company List Mock</div>
}))

vi.mock('../components/views/global/WelcomeView', () => ({
    default: () => <div data-testid="welcome-view">Welcome View Mock</div>
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
            loadUploadProgress: vi.fn(),
            showUploadProgress: false,
            setShowUploadProgress: vi.fn()
        }

        render(
            <AuthContext.Provider value={mockAuthValue}>
                <ThemeContext.Provider value={mockThemeValue}>
                    <UploadDispatchContext.Provider value={mockUploadValue}>
                        <UploadStateContext.Provider value={mockUploadValue}>
                            <Dashboard />
                        </UploadStateContext.Provider>
                    </UploadDispatchContext.Provider>
                </ThemeContext.Provider>
            </AuthContext.Provider>
        )

        // Verify the main structure is present
        // 1. Header should be rendered with user data
        expect(screen.getByTestId('header')).toBeDefined()
        expect(screen.getByText(/Test User/)).toBeDefined()

        // 2. SplitScreen container should be rendered
        expect(screen.getByTestId('split-screen')).toBeDefined()

        // 3. Left and Right panels should be rendered inside (by SplitScreen mock)
        expect(screen.getByTestId('left-panel')).toBeDefined()
        expect(screen.getByTestId('right-panel')).toBeDefined()

        // 4. Initial state should render CompanyList and WelcomeView
        expect(screen.getByTestId('company-list')).toBeDefined()
        expect(screen.getByTestId('welcome-view')).toBeDefined()
    })
})
