import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion as Motion } from 'framer-motion'
import './ProcessingPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002/api'

const steps = [
  { key: 'create', label: 'Session' },
  { key: 'extract', label: 'Extract' },
  { key: 'index', label: 'Index' },
  { key: 'ready', label: 'Ready' },
]

function ProcessingPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const previousBodyOverflow = document.body.style.overflow
    const previousHtmlOverflow = document.documentElement.style.overflow
    document.body.style.overflow = 'hidden'
    document.documentElement.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousBodyOverflow
      document.documentElement.style.overflow = previousHtmlOverflow
    }
  }, [])

  useEffect(() => {
    let intervalId = null

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/session/${sessionId}/status`)
        if (res.status === 404) {
          setError('Session not found. It may have expired or the backend restarted.')
          stopPolling()
          return
        }

        const data = await res.json()
        if (!data.success) {
          setError(data.error || 'Failed to retrieve session status')
          stopPolling()
          return
        }

        setSession(data.session)

        if (data.session.status === 'error') {
          setError(data.session.error || 'An error happened during processing')
          stopPolling()
        }

        if (data.session.status === 'ready') {
          stopPolling()
        }
      } catch {
        setError('Unable to contact backend server')
        stopPolling()
      }
    }

    void checkStatus()
    intervalId = setInterval(() => {
      void checkStatus()
    }, 1000)

    return () => {
      stopPolling()
    }
  }, [sessionId])

  const progress = session?.progress || 0
  const isReady = session?.status === 'ready'

  const activeStepIndex = useMemo(() => {
    if (progress >= 100) return 3
    if (progress >= 65) return 2
    if (progress >= 25) return 1
    return 0
  }, [progress])

  if (error) {
    return (
      <main className="processing-page">
        <section className="processing-card processing-card--error">
          <img src="/logo-260.webp" alt="CC" className="processing-logo" />
          <h2>Processing error</h2>
          <p>{error}</p>
          <button type="button" className="processing-btn" onClick={() => navigate('/start')}>
            Back to upload
          </button>
        </section>
      </main>
    )
  }

  if (!session) {
    return (
      <main className="processing-page">
        <section className="processing-card">
          <img src="/logo-260.webp" alt="CC" className="processing-logo" />
          <div className="orbital-loader" aria-hidden="true">
            <div className="orbit orbit-a" />
            <div className="orbit orbit-b" />
            <div className="orbit orbit-c" />
            <div className="orbit-core" />
          </div>
          <h2>Connecting to your workspace</h2>
        </section>
      </main>
    )
  }

  return (
    <main className="processing-page">
      <section className="processing-card">
        <img src="/logo-260.webp" alt="CC" className="processing-logo" />

        {!isReady ? (
          <>
            <div className="orbital-loader" aria-hidden="true">
              <div className="orbit orbit-a" />
              <div className="orbit orbit-b" />
              <div className="orbit orbit-c" />
              <div className="orbit-core">{progress}%</div>
            </div>

            <h2>Generating your assistant</h2>
            <p className="processing-copy">{session.message}</p>

            <div className="processing-bar">
              <Motion.div
                className="processing-bar-fill"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>

            <div className="processing-steps">
              {steps.map((step, index) => (
                <div
                  key={step.key}
                  className={`processing-step ${index <= activeStepIndex ? 'is-active' : ''} ${index < activeStepIndex ? 'is-done' : ''}`}
                >
                  <span>{index + 1}</span>
                  <p>{step.label}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <Motion.div
            className="ready-state"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
          >
            <div className="ready-icon">&#10003;</div>
            <h2>Your assistant is ready</h2>
            <p>
              Everything is processed for <strong>{session.vehicle_name}</strong>. You can now access the chat.
            </p>
            <button type="button" className="processing-btn" onClick={() => navigate(`/chat/${sessionId}`)}>
              Access chat now
            </button>
          </Motion.div>
        )}
      </section>
    </main>
  )
}

export default ProcessingPage

