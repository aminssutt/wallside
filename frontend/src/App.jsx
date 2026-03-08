import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import LandingPage from './pages/LandingPage'
import './App.css'

const GuidesPage = lazy(() => import('./pages/GuidesPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={null}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/guides" element={<GuidesPage />} />
          <Route path="/chat/:slug" element={<ChatPage />} />
        </Routes>
      </Suspense>
    </AnimatePresence>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="ambient-bg" />
      <AnimatedRoutes />
    </BrowserRouter>
  )
}

export default App
