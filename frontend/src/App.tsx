import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { HomePage } from './pages/HomePage'
import { UploadPage } from './pages/UploadPage'
import { TranslatePage } from './pages/TranslatePage'
import { PreviewPage } from './pages/PreviewPage'
import { SettingsPage } from './pages/SettingsPage'
import { PromptManagementPage } from './pages/PromptManagementPage'
import { ProjectLayout } from './pages/workflow/ProjectLayout'
import { AnalysisPage } from './pages/workflow/AnalysisPage'
import { TranslateWorkflowPage } from './pages/workflow/TranslateWorkflowPage'
import { ProofreadPage } from './pages/workflow/ProofreadPage'
import { ExportPage } from './pages/workflow/ExportPage'
import { useSettingsStore } from './stores/settingsStore'

function App() {
  const loadConfigs = useSettingsStore((state) => state.loadConfigs)
  const isHydrated = useSettingsStore((state) => state._isHydrated)

  // Load LLM configurations on app start
  useEffect(() => {
    if (!isHydrated) {
      loadConfigs()
    }
  }, [isHydrated, loadConfigs])
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />

          {/* New 4-step workflow */}
          <Route path="/project/:projectId" element={<ProjectLayout />}>
            <Route index element={<Navigate to="analysis" replace />} />
            <Route path="analysis" element={<AnalysisPage />} />
            <Route path="translate" element={<TranslateWorkflowPage />} />
            <Route path="proofread" element={<ProofreadPage />} />
            <Route path="export" element={<ExportPage />} />
          </Route>

          {/* Legacy routes (keep for backwards compatibility) */}
          <Route path="/translate/:projectId" element={<TranslatePage />} />
          <Route path="/preview/:projectId" element={<PreviewPage />} />
          <Route path="/prompts" element={<PromptManagementPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
