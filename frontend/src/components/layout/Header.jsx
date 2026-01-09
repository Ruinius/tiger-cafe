import React from 'react'
import './Header.css'

function Header({ user, onLogout, theme, onThemeToggle }) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">Tiger-Cafe</h1>
      </div>
      <div className="header-right">
        <button 
          className="theme-toggle"
          onClick={onThemeToggle}
          aria-label="Toggle theme"
          aria-pressed={theme === 'dark'}
        >
          <span className="theme-toggle-indicator" />
          <span className="theme-toggle-label">{theme === 'light' ? 'Light' : 'Dark'}</span>
        </button>
        {user && (
          <div className="user-info">
            <span className="user-name">{user.name || user.email}</span>
            <button className="logout-button" onClick={onLogout}>
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header
