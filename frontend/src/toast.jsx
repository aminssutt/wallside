/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion as Motion } from 'framer-motion'

const ToastContext = createContext({
  showToast: () => {},
})

const MIN_DURATION_MS = 1200
const DEFAULT_DURATION_MS = 2800
const MAX_VISIBLE_TOASTS = 4

const normalizePayload = (payload) => {
  if (typeof payload === 'string') {
    return { message: payload }
  }
  return payload || {}
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timeoutByIdRef = useRef(new Map())

  const dismissToast = useCallback((id) => {
    const timeoutId = timeoutByIdRef.current.get(id)
    if (timeoutId) {
      window.clearTimeout(timeoutId)
      timeoutByIdRef.current.delete(id)
    }

    setToasts((previous) => previous.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((payload) => {
    const { message, type = 'info', duration = DEFAULT_DURATION_MS } = normalizePayload(payload)
    const safeMessage = String(message || '').trim()
    if (!safeMessage) return

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

    setToasts((previous) => [...previous, { id, type, message: safeMessage }].slice(-MAX_VISIBLE_TOASTS))

    const timeoutId = window.setTimeout(
      () => dismissToast(id),
      Math.max(MIN_DURATION_MS, Number(duration) || DEFAULT_DURATION_MS),
    )

    timeoutByIdRef.current.set(id, timeoutId)
  }, [dismissToast])

  useEffect(() => {
    const timeoutById = timeoutByIdRef.current
    return () => {
      timeoutById.forEach((timeoutId) => window.clearTimeout(timeoutId))
      timeoutById.clear()
    }
  }, [])

  const contextValue = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={contextValue}>
      {children}

      <div className="app-toast-stack" aria-live="polite" aria-atomic="true">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => (
            <Motion.div
              key={toast.id}
              className={`app-toast app-toast--${toast.type}`}
              initial={{ opacity: 0, y: 20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              role="status"
            >
              <span className="app-toast-indicator" aria-hidden="true" />
              <p>{toast.message}</p>
              <button
                type="button"
                className="app-toast-close"
                onClick={() => dismissToast(toast.id)}
                aria-label="Close notification"
              >
                x
              </button>
            </Motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)



