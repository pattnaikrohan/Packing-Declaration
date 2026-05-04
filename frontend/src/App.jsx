import { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
// ── MSAL disabled temporarily ──
// import { AuthenticatedTemplate, UnauthenticatedTemplate } from "@azure/msal-react"
import UploadPage from './pages/UploadPage'
import SendPage from './pages/SendPage'
import TrainingPage from './pages/TrainingPage'
// import LoginPage from './pages/LoginPage'
import './index.css'
import './App.css'

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark')
  const location = useLocation()

  useEffect(() => {
    document.body.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark')

  const isTerminalMode = location.pathname === '/send' || location.pathname === '/training'
  const isUploadPage   = location.pathname === '/' || location.pathname === '/upload'

  return (
    <>
      {/* AuthenticatedTemplate removed — re-enable when redirect URI is configured */}
        <div className={`app-container ${isTerminalMode ? 'terminal-mode' : ''}`}>
          <Toaster position="bottom-right" />
          
          <main className={isTerminalMode ? 'full-terminal' : ''}>
            <Routes>
              <Route path="/" element={<UploadPage />} />
              <Route path="/send" element={<SendPage />} />
              <Route path="/training" element={<TrainingPage />} />
            </Routes>
          </main>

          {!isTerminalMode && (
            <footer className="terms-mini" style={{ textAlign: 'center', marginTop: '2rem', padding: '1rem', fontSize: '0.75rem', color: 'var(--text-3)' }}>
              © 2026 PKD Converter • Proprietary Extraction Engine v2.4 • Confidential Industry Use Only
            </footer>
          )}
        </div>
    </>
  )
}

