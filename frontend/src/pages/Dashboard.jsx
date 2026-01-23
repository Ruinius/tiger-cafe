import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { useUploadManager } from '../hooks/useUploadManager'
import SplitScreen from '../components/layout/SplitScreen'
import Header from '../components/layout/Header'
import UploadModal from '../components/modals/UploadModal'

// Views
import CompanyList from '../components/views/global/CompanyList'
import WelcomeView from '../components/views/global/WelcomeView'
import DocumentList from '../components/views/company/DocumentList'
import CompanyAnalysisView from '../components/views/company/CompanyAnalysisView'
import DocumentView from '../components/views/document/DocumentView'
import DocumentExtractionView from '../components/views/document/DocumentExtractionView'
import CheckUpdatesView from '../components/views/global/CheckUpdatesView'

import '../styles/layout.css'
import '../styles/components.css'

function Dashboard() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [viewState, setViewState] = useState({
    type: 'GLOBAL', // 'GLOBAL' | 'COMPANY' | 'DOCUMENT' | 'CHECK_UPDATES'
    data: { company: null, document: null }
  })

  const [refreshKey, setRefreshKey] = useState(0)

  // Modal Management
  const {
    isUploadModalOpen,
    openUploadModal,
    closeUploadModal,
    handleUploadSuccess,
    handleReplaceAndIndex,
    handleCancelDuplicate,
    handleCancelUpload,
    uploadingDocuments
  } = useUploadManager(() => setRefreshKey(prev => prev + 1))

  // Default split ratios per view type
  const DEFAULT_RATIOS = {
    GLOBAL: 0.5,
    COMPANY: 0.5,
    DOCUMENT: 0.5,
    CHECK_UPDATES: 1.0, // Full width for check updates
  }

  // Manage split ratios per view type
  const [splitRatios, setSplitRatios] = useState(() => {
    const getRatio = (type) => {
      const saved = localStorage.getItem(`tiger-cafe-split-ratio-${type}`)
      return saved ? parseFloat(saved) : DEFAULT_RATIOS[type]
    }
    return {
      GLOBAL: getRatio('GLOBAL'),
      COMPANY: getRatio('COMPANY'),
      DOCUMENT: getRatio('DOCUMENT'),
      CHECK_UPDATES: getRatio('CHECK_UPDATES')
    }
  })

  const currentSplitRatio = splitRatios[viewState.type] || 0.5

  const handleSplitChange = useCallback((newRatio) => {
    setSplitRatios(prev => ({
      ...prev,
      [viewState.type]: newRatio
    }))
    localStorage.setItem(`tiger-cafe-split-ratio-${viewState.type}`, newRatio.toString())
  }, [viewState.type])

  // Navigation Handlers
  const handleCompanySelect = useCallback((company) => {
    setViewState({
      type: 'COMPANY',
      data: { company, document: null }
    })
  }, [])

  const handleDocumentSelect = useCallback((document) => {
    setViewState(prev => ({
      type: 'DOCUMENT',
      data: { ...prev.data, document }
    }))
  }, [])

  const handleBackToGlobal = useCallback(() => {
    setViewState({
      type: 'GLOBAL',
      data: { company: null, document: null }
    })
  }, [])

  const handleBackToCompany = useCallback(() => {
    setViewState(prev => ({
      type: 'COMPANY',
      data: { company: prev.data.company, document: null }
    }))
  }, [])

  // View Content Resolution
  let leftPanelContent
  let rightPanelContent

  switch (viewState.type) {
    case 'GLOBAL':
      leftPanelContent = (
        <CompanyList
          key={`company-list-${refreshKey}`} // Force remount on refresh
          onCompanySelect={handleCompanySelect}
          onOpenUploadModal={openUploadModal}
          onShowUploadProgress={() => setViewState({ type: 'CHECK_UPDATES', data: { company: null, document: null } })}
        />
      )
      rightPanelContent = <WelcomeView />
      break

    case 'COMPANY':
      leftPanelContent = (
        <DocumentList
          key={`doc-list-${viewState.data.company?.id}-${refreshKey}`}
          selectedCompany={viewState.data.company}
          onDocumentSelect={handleDocumentSelect}
          onBack={handleBackToGlobal}
          onOpenUploadModal={openUploadModal}
          onShowUploadProgress={() => setViewState({ type: 'CHECK_UPDATES', data: { company: null, document: null } })}
        />
      )
      rightPanelContent = (
        <CompanyAnalysisView
          selectedCompany={viewState.data.company}
        />
      )
      break

    case 'DOCUMENT':
      leftPanelContent = (
        <DocumentView
          selectedDocument={viewState.data.document}
          selectedCompany={viewState.data.company}
          onBack={handleBackToCompany}
        />
      )
      rightPanelContent = (
        <DocumentExtractionView
          selectedDocument={viewState.data.document}
        />
      )
      break

    case 'CHECK_UPDATES':
      leftPanelContent = (
        <CheckUpdatesView
          onBack={handleBackToGlobal}
        />
      )
      rightPanelContent = <WelcomeView />
      break

    default:
      leftPanelContent = <div>Unknown State</div>
      rightPanelContent = <div>Unknown State</div>
  }

  return (
    <div className="dashboard">
      <Header
        user={user}
        onLogout={logout}
        theme={theme}
        onThemeToggle={toggleTheme}
      />

      <SplitScreen
        left={leftPanelContent}
        right={rightPanelContent}
        splitRatio={currentSplitRatio}
        onSplitChange={handleSplitChange}
      />

      {/* Global Modals */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={closeUploadModal}
        onUploadSuccess={handleUploadSuccess}
      />

    </div>
  )
}

export default Dashboard
