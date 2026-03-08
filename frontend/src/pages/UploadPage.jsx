import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion as Motion } from 'framer-motion'
import './UploadPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002/api'

const steps = [
  {
    id: 'vehicle',
    title: 'Which vehicle are we preparing?',
    helper: 'Enter your exact model to personalize answers and maintenance context.',
  },
  {
    id: 'manual',
    title: "Upload your owner's manual",
    helper: 'PDF only. You can upload one or multiple files for richer answers.',
  },
  {
    id: 'generate',
    title: 'Ready to generate your AI assistant?',
    helper: 'We will process your files, index content and prepare your chat workspace.',
  },
]

function TypewriterLine({ text }) {
  const [rendered, setRendered] = useState('')

  useEffect(() => {
    let cursor = 0
    const timer = window.setInterval(() => {
      cursor += 1
      setRendered(text.slice(0, cursor))
      if (cursor >= text.length) {
        window.clearInterval(timer)
      }
    }, 26)

    return () => {
      window.clearInterval(timer)
    }
  }, [text])

  return <h1 className="wizard-title">{rendered}</h1>
}

function UploadPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [vehicleName, setVehicleName] = useState('')
  const [files, setFiles] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const currentStep = useMemo(() => steps[stepIndex], [stepIndex])

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

  const addFiles = (incomingFiles) => {
    const pdfFiles = incomingFiles.filter((file) => file.type === 'application/pdf')
    if (pdfFiles.length !== incomingFiles.length) {
      setError('Only PDF files are accepted.')
    } else {
      setError('')
    }

    setFiles((prev) => {
      const merged = [...prev, ...pdfFiles]
      const uniqueByNameSize = merged.filter((file, index, array) => {
        const firstIndex = array.findIndex((candidate) => candidate.name === file.name && candidate.size === file.size)
        return firstIndex === index
      })
      return uniqueByNameSize
    })
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const canGoNext =
    (stepIndex === 0 && vehicleName.trim().length > 1) ||
    (stepIndex === 1 && files.length > 0) ||
    stepIndex === 2

  const handleGenerate = async () => {
    if (vehicleName.trim().length <= 1 || files.length === 0 || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const sessionRes = await fetch(`${API_URL}/session/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_name: vehicleName.trim() }),
      })

      const sessionData = await sessionRes.json()
      if (!sessionData.success) {
        throw new Error(sessionData.error || 'Unable to create session')
      }

      const sessionId = sessionData.session.id

      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)

        const uploadRes = await fetch(`${API_URL}/session/${sessionId}/upload`, {
          method: 'POST',
          body: formData,
        })
        const uploadData = await uploadRes.json()

        if (!uploadData.success) {
          throw new Error(uploadData.error || `Upload failed for ${file.name}`)
        }
      }

      const processRes = await fetch(`${API_URL}/session/${sessionId}/process`, { method: 'POST' })
      const processData = await processRes.json()
      if (!processData.success) {
        throw new Error(processData.error || 'Processing could not start')
      }

      navigate(`/processing/${sessionId}`)
    } catch (submissionError) {
      setError(submissionError.message || 'Unexpected error while generating your assistant')
      setIsSubmitting(false)
    }
  }

  return (
    <main className="wizard-page">
      <div className="wizard-shell">
        <img className="wizard-logo" src="/logo-260.webp" alt="CC logo" loading="eager" width="260" height="260" />

        <div className="wizard-stepper" aria-label="Wizard progress">
          {steps.map((step, index) => {
            const stateClass = index < stepIndex ? 'is-done' : index === stepIndex ? 'is-active' : ''
            return (
              <div className={`wizard-step ${stateClass}`} key={step.id}>
                <span>{index + 1}</span>
                <p>{step.id}</p>
              </div>
            )
          })}
        </div>

        <AnimatePresence mode="wait">
          <Motion.section
            key={currentStep.id}
            className="wizard-card"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 }}
            transition={{ duration: 0.35 }}
          >
            <TypewriterLine key={currentStep.id} text={currentStep.title} />
            <p className="wizard-helper">{currentStep.helper}</p>

            {stepIndex === 0 && (
              <div className="wizard-content">
                <input
                  className="wizard-input"
                  value={vehicleName}
                  onChange={(event) => setVehicleName(event.target.value)}
                  placeholder="Ex: Toyota Auris Hybrid 2015"
                  autoFocus
                />
              </div>
            )}

            {stepIndex === 1 && (
              <div className="wizard-content">
                <div
                  className={`wizard-dropzone ${isDragging ? 'is-dragging' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(event) => {
                    event.preventDefault()
                    setIsDragging(true)
                  }}
                  onDragLeave={(event) => {
                    event.preventDefault()
                    setIsDragging(false)
                  }}
                  onDrop={(event) => {
                    event.preventDefault()
                    setIsDragging(false)
                    addFiles(Array.from(event.dataTransfer.files))
                  }}
                >
                  <p>Drop PDF files here or click to browse</p>
                  <span>PDF files only</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={(event) => addFiles(Array.from(event.target.files || []))}
                    style={{ display: 'none' }}
                  />
                </div>

                {files.length > 0 && (
                  <div className="wizard-file-list">
                    {files.map((file, index) => (
                      <div className="wizard-file" key={`${file.name}-${file.size}`}>
                        <div>
                          <p>{file.name}</p>
                          <span>{Math.round(file.size / 1024)} KB</span>
                        </div>
                        <button type="button" onClick={() => removeFile(index)}>
                          remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {stepIndex === 2 && (
              <div className="wizard-content wizard-content--summary">
                <div className="summary-item">
                  <span>Vehicle</span>
                  <p>{vehicleName}</p>
                </div>
                <div className="summary-item">
                  <span>PDF files</span>
                  <p>{files.length}</p>
                </div>
              </div>
            )}

            {error && <p className="wizard-error">{error}</p>}

            <div className="wizard-actions">
              <button
                type="button"
                className="wizard-btn wizard-btn--ghost"
                onClick={() => (stepIndex === 0 ? navigate('/') : setStepIndex((prev) => prev - 1))}
                disabled={isSubmitting}
              >
                {stepIndex === 0 ? 'Back to home' : 'Back'}
              </button>

              {stepIndex < steps.length - 1 ? (
                <button
                  type="button"
                  className="wizard-btn wizard-btn--primary"
                  onClick={() => setStepIndex((prev) => prev + 1)}
                  disabled={!canGoNext || isSubmitting}
                >
                  Next
                </button>
              ) : (
                <Motion.button
                  type="button"
                  className="wizard-btn wizard-btn--primary"
                  onClick={handleGenerate}
                  disabled={isSubmitting}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {isSubmitting ? 'Generating...' : 'Generate assistant'}
                </Motion.button>
              )}
            </div>
          </Motion.section>
        </AnimatePresence>
      </div>
    </main>
  )
}

export default UploadPage
