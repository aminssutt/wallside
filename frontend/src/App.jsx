import { Component, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { ToastProvider } from './toast'
import './App.css'

const LandingPage = lazy(() => import('./pages/LandingPage'))
const GuidesPage = lazy(() => import('./pages/GuidesPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

function LoadingSpinner() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        width: '100%',
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: '4px solid rgba(255, 255, 255, 0.15)',
          borderTopColor: '#fff',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      const lang = (typeof window !== 'undefined' && window.localStorage.getItem('cc_lang')) || 'fr'
      const messages = {
        fr: { title: 'Une erreur est survenue', reload: 'Recharger' },
        en: { title: 'Something went wrong', reload: 'Reload' },
        ko: { title: '\uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4', reload: '\uC0C8\uB85C\uACE0\uCE68' },
      }
      const t = messages[lang] || messages.fr

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            width: '100%',
            color: '#fff',
            fontFamily: 'system-ui, sans-serif',
            textAlign: 'center',
            padding: 24,
          }}
        >
          <h1 style={{ fontSize: 24, marginBottom: 12 }}>{t.title}</h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', marginBottom: 24 }}>
            {t.title}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              padding: '10px 24px',
              fontSize: 16,
              borderRadius: 8,
              border: 'none',
              background: '#fff',
              color: '#000',
              cursor: 'pointer',
            }}
          >
            {t.reload}
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={<LoadingSpinner />}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/guides" element={<GuidesPage />} />
          <Route path="/chat/:slug" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AnimatePresence>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <ToastProvider>
          <div className="ambient-bg" />
          <AnimatedRoutes />
        </ToastProvider>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

export default App
