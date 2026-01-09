import { useEffect } from 'react'

export function useAnalysisEvents({
  onProcessingComplete,
  onClearData,
  onReloadHistorical,
  onReloadProgress,
  onResetProgress
}) {
  useEffect(() => {
    // Handler for processing complete
    const handleProcessingComplete = () => {
      if (onProcessingComplete) onProcessingComplete()
    }

    // Handler for clearing data
    const handleClearData = () => {
      if (onClearData) onClearData()
    }

    // Handler for reloading historical calculations
    const handleReloadHistorical = () => {
      if (onReloadHistorical) onReloadHistorical()
    }

    // Handler for reloading progress
    const handleReloadProgress = () => {
      if (onReloadProgress) onReloadProgress()
    }

    // Handler for resetting progress
    const handleResetProgress = (event) => {
      if (onResetProgress) onResetProgress(event.detail)
    }

    window.addEventListener('financialStatementsProcessingComplete', handleProcessingComplete)
    window.addEventListener('clearFinancialStatements', handleClearData)
    window.addEventListener('reloadHistoricalCalculations', handleReloadHistorical)
    window.addEventListener('reloadProgress', handleReloadProgress)
    window.addEventListener('resetProgressToPending', handleResetProgress)

    return () => {
      window.removeEventListener('financialStatementsProcessingComplete', handleProcessingComplete)
      window.removeEventListener('clearFinancialStatements', handleClearData)
      window.removeEventListener('reloadHistoricalCalculations', handleReloadHistorical)
      window.removeEventListener('reloadProgress', handleReloadProgress)
      window.removeEventListener('resetProgressToPending', handleResetProgress)
    }
  }, [onProcessingComplete, onClearData, onReloadHistorical, onReloadProgress, onResetProgress])
}
