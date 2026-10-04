import { Component, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { ToastProvider } from './toast'
import './App.css'

const LandingPage = lazy(() => import('./pages/LandingPage'))
const GuidesPage = lazy(() => import('./pages/GuidesPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const AskPage = lazy(() => import('./pages/AskPage'))
const ResultsPage = lazy(() => import('./research/ResultsPage'))
const LegalPage = lazy(() => import('./pages/LegalPage'))

function GarageComingSoon() {
  const lang = (typeof window !== 'undefined' && window.localStorage.getItem('cc_lang')) || 'fr'
  const copy = {
    fr: {
      badge: 'Wallside · Garage',
      title: 'Bientôt disponible',
      desc: "L'espace garagistes est en cours de finalisation. Revenez très bientôt.",
      back: "Retour à l'accueil",
    },
    en: {
      badge: 'Wallside · Garage',
      title: 'Coming soon',
      desc: 'The workshop dashboard is being finalized. Check back shortly.',
      back: 'Back to home',
    },
    ko: {
      badge: 'Wallside · Garage',
      title: '\uACE7 \uACF5\uAC1C',
      desc: '\uC815\uBE44\uC18C \uD3EC\uD138\uC744 \uC900\uBE44 \uC911\uC785\uB2C8\uB2E4.',
      back: '\uD648\uC73C\uB85C',
    },
  }
  const t = copy[lang] || copy.fr
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: 24,
        color: '#fff',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        background: 'linear-gradient(180deg, #0a0a0a 0%, #121418 100%)',
      }}
    >
      <span
        style={{
          textTransform: 'uppercase',
          letterSpacing: '0.2em',
          fontSize: 12,
          opacity: 0.55,
          marginBottom: 18,
        }}
      >
        {t.badge}
      </span>
      <h1 style={{ fontSize: 36, fontWeight: 600, margin: 0, marginBottom: 12 }}>{t.title}</h1>
      <p style={{ maxWidth: 480, color: 'rgba(255,255,255,0.65)', lineHeight: 1.5, margin: 0, marginBottom: 28 }}>
        {t.desc}
      </p>
      <a
        href="/"
        style={{
          padding: '10px 22px',
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,0.2)',
          color: '#fff',
          textDecoration: 'none',
          fontSize: 14,
        }}
      >
        {t.back}
      </a>
    </div>
  )
}

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
        fr: { title: 'Une erreur est survenue', desc: 'Veuillez recharger la page pour continuer.', reload: 'Recharger' },
        en: { title: 'Something went wrong', desc: 'Please reload the page to continue.', reload: 'Reload' },
        ko: { title: '\uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4', desc: '\uD398\uC774\uC9C0\uB97C \uC0C8\uB85C\uACE0\uCE68\uD574\uC8FC\uC138\uC694.', reload: '\uC0C8\uB85C\uACE0\uCE68' },
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
            {t.desc}
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
          <Route path="/" element={<ResultsPage />} />
          <Route path="/produit" element={<LandingPage />} />
          <Route path="/guides" element={<GuidesPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/chat/:slug" element={<ChatPage />} />
          <Route path="/legal" element={<LegalPage />} />
          <Route path="/garage" element={<GarageComingSoon />} />
          <Route path="/garage/beta" element={<GarageComingSoon />} />
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
