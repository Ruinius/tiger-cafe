import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import SplitScreen from '../components/layout/SplitScreen'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import Header from '../components/layout/Header'
import './Dashboard.css'

function Dashboard() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [splitRatio, setSplitRatio] = useState(() => {
    const saved = localStorage.getItem('tiger-cafe-split-ratio')
    return saved ? parseFloat(saved) : 0.5
  })

  useEffect(() => {
    localStorage.setItem('tiger-cafe-split-ratio', splitRatio.toString())
  }, [splitRatio])

  const handleSplitChange = useCallback((newRatio) => {
    setSplitRatio(newRatio)
  }, [])

  const handleCompanySelect = useCallback((company) => {
    setSelectedCompany(company)
    setSelectedDocument(null)
  }, [])

  const handleDocumentSelect = useCallback((document) => {
    setSelectedDocument(document)
  }, [])

  const handleBack = useCallback(() => {
    if (selectedDocument) {
      setSelectedDocument(null)
    } else if (selectedCompany) {
      setSelectedCompany(null)
    }
  }, [selectedDocument, selectedCompany])

  const handleUploadSuccess = useCallback((newDocument) => {
    // Refresh the view - could trigger a reload of companies/documents
    // This will be handled by LeftPanel's refresh
  }, [])

  return (
    <div className="dashboard">
      <Header
        user={user}
        onLogout={logout}
        theme={theme}
        onThemeToggle={toggleTheme}
      />
      <SplitScreen
        left={
          <LeftPanel
            selectedCompany={selectedCompany}
            selectedDocument={selectedDocument}
            onCompanySelect={handleCompanySelect}
            onDocumentSelect={handleDocumentSelect}
            onBack={handleBack}
          />
        }
        right={
          <RightPanel
            selectedCompany={selectedCompany}
            selectedDocument={selectedDocument}
          />
        }
        splitRatio={splitRatio}
        onSplitChange={handleSplitChange}
      />
    </div>
  )
}

export default Dashboard

