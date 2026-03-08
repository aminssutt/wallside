import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import LandingPage from './pages/LandingPage'
import './App.css'

const UploadPage = lazy(() => import('./pages/UploadPage'))
const ProcessingPage = lazy(() => import('./pages/ProcessingPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={null}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/start" element={<UploadPage />} />
          <Route path="/processing/:sessionId" element={<ProcessingPage />} />
          <Route path="/chat/:sessionId" element={<ChatPage />} />
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
