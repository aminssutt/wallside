import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion as Motion } from 'framer-motion'
import { LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import './LandingPage.css'

const COLLISION_FRAMES = 30

const framePath = (index) => `/collision-webp/frame_${String(index).padStart(2, '0')}.webp`

const findNearestLoadedFrame = (frames, target) => {
  if (frames[target]?.complete) {
    return frames[target]
  }

  for (let distance = 1; distance < frames.length; distance += 1) {
    const previous = target - distance
    const next = target + distance

    if (previous >= 0 && frames[previous]?.complete) {
      return frames[previous]
    }

    if (next < frames.length && frames[next]?.complete) {
      return frames[next]
    }
  }

  return null
}

function LandingPage() {
  const navigate = useNavigate()
  const [launching, setLaunching] = useState(false)
  const [lang, setLang] = useAppLanguage()
  const [langOpen, setLangOpen] = useState(false)
  const langDropdownRef = useRef(null)

  const collisionCanvasRef = useRef(null)
  const collisionFramesRef = useRef(Array(COLLISION_FRAMES).fill(null))
  const t = UI_TEXT[lang] || UI_TEXT.fr

  const frameUrls = useMemo(
    () => Array.from({ length: COLLISION_FRAMES }, (_, idx) => framePath(idx + 1)),
    []
  )

  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]

  const drawCollisionFrame = useCallback((frameIndex) => {
    const canvas = collisionCanvasRef.current
    if (!canvas) {
      return false
    }

    const context = canvas.getContext('2d', { alpha: true, desynchronized: true })
    if (!context) {
      return false
    }

    const clampedFrame = Math.max(0, Math.min(COLLISION_FRAMES - 1, frameIndex))
    const image = findNearestLoadedFrame(collisionFramesRef.current, clampedFrame)
    if (!image) {
      return false
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const width = Math.max(1, Math.round(canvas.clientWidth * dpr))
    const height = Math.max(1, Math.round(canvas.clientHeight * dpr))

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width
      canvas.height = height
    }

    context.setTransform(1, 0, 0, 1, 0, 0)
    context.clearRect(0, 0, width, height)

    const scale = Math.min(width / image.width, height / image.height)
    const drawWidth = image.width * scale
    const drawHeight = image.height * scale
    const x = (width - drawWidth) / 2
    const y = (height - drawHeight) / 2

    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.drawImage(image, x, y, drawWidth, drawHeight)

    return true
  }, [])

  useEffect(() => {
    let cancelled = false

    frameUrls.forEach((url, index) => {
      const image = new Image()
      image.decoding = 'async'
      image.src = url

      image.onload = () => {
        if (cancelled) {
          return
        }

        if (index === 0) {
          drawCollisionFrame(0)
        }
      }

      collisionFramesRef.current[index] = image
    })

    return () => {
      cancelled = true
    }
  }, [drawCollisionFrame, frameUrls])

  useEffect(() => {
    let rafId = null
    let startAt = null

    const animateIntro = (timestamp) => {
      if (startAt === null) {
        startAt = timestamp
      }

      const progress = Math.min((timestamp - startAt) / 1100, 1)
      const easedProgress = 1 - ((1 - progress) ** 1.2)
      const frameIndex = Math.round(easedProgress * (COLLISION_FRAMES - 1))
      drawCollisionFrame(frameIndex)

      if (progress < 1) {
        rafId = window.requestAnimationFrame(animateIntro)
      }
    }

    rafId = window.requestAnimationFrame(animateIntro)

    return () => {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId)
      }
    }
  }, [drawCollisionFrame])

  useEffect(() => {
    if (!langOpen) {
      return undefined
    }

    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setLangOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [langOpen])

  const launchGuides = () => {
    if (launching) {
      return
    }

    setLaunching(true)
    window.setTimeout(() => {
      navigate('/guides')
    }, 680)
  }

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
  }

  return (
    <main className="saas-page">
      <section className="saas-hero">
        <div className="saas-topbar">
          <div className="saas-lang-dropdown" ref={langDropdownRef}>
            <button
              type="button"
              className="saas-lang-trigger"
              onClick={() => setLangOpen((previous) => !previous)}
              aria-expanded={langOpen}
              aria-haspopup="menu"
            >
              <span>{currentLang.flag}</span>
              {currentLang.label}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <AnimatePresence>
              {langOpen && (
                <Motion.div
                  className="saas-lang-menu"
                  initial={{ opacity: 0, y: -6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.96 }}
                  transition={{ duration: 0.16 }}
                >
                  {LANGUAGES.map((entry) => (
                    <button
                      key={entry.code}
                      type="button"
                      className={`saas-lang-item${entry.code === lang ? ' saas-lang-item--active' : ''}`}
                      onClick={() => handleLangSelect(entry.code)}
                    >
                      <span>{entry.flag}</span>
                      {entry.label}
                    </button>
                  ))}
                </Motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <Motion.div
          className="hero-collision-wrap"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <canvas ref={collisionCanvasRef} className="hero-collision-canvas" />
        </Motion.div>

        <Motion.div
          className="hero-main-content"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18, duration: 0.58 }}
        >
          <p className="saas-subtitle">{t.landing.subtitle}</p>

          <Motion.div
            className="saas-actions"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            <Motion.button
              type="button"
              className="saas-btn saas-btn--primary"
              onClick={launchGuides}
              whileHover={{ y: -2, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
            >
              {t.landing.accessChat}
            </Motion.button>
          </Motion.div>
        </Motion.div>
      </section>

      <section className="saas-overview">
        {t.landing.features.map((feat) => (
          <article className="overview-card" key={feat.title}>
            <h2>{feat.title}</h2>
            <p>{feat.desc}</p>
          </article>
        ))}
      </section>

      <footer className="saas-footer">
        <div className="saas-footer-brand">
          <img src="/logo-84.webp" alt="CC" width="36" height="36" loading="lazy" />
          <div>
            <p>Car Chat : CC</p>
            <span>{t.landing.footerTagline}</span>
          </div>
        </div>

        <div className="saas-footer-socials">
          <a
            className="social-link"
            href="https://www.linkedin.com/in/lakhdar-berache/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="LinkedIn profile"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M6.94 8.72H3.56V20h3.38V8.72Zm.22-3.49C7.14 4.17 6.34 3.4 5.28 3.4S3.4 4.17 3.4 5.23c0 1.04.8 1.83 1.86 1.83h.02c1.08 0 1.88-.79 1.88-1.83ZM20 13.55c0-3.4-1.82-4.98-4.25-4.98-1.96 0-2.84 1.08-3.33 1.85v-1.7H9.04c.04 1.12 0 11.28 0 11.28h3.38v-6.3c0-.34.02-.67.12-.91.27-.67.88-1.36 1.92-1.36 1.35 0 1.9 1.03 1.9 2.55V20H20v-6.45Z" />
            </svg>
            {t.landing.linkedin}
          </a>

          <a
            className="social-link"
            href="https://github.com/aminssutt"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub profile"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 .5A11.5 11.5 0 0 0 .5 12.24c0 5.2 3.35 9.6 8 11.16.58.1.78-.26.78-.57 0-.29-.01-1.04-.01-2.05-3.26.73-3.95-1.6-3.95-1.6-.53-1.38-1.3-1.75-1.3-1.75-1.07-.75.08-.74.08-.74 1.18.08 1.8 1.23 1.8 1.23 1.05 1.82 2.75 1.3 3.42 1 .1-.78.4-1.3.73-1.6-2.6-.3-5.34-1.33-5.34-5.9 0-1.3.45-2.36 1.2-3.2-.12-.3-.52-1.52.12-3.17 0 0 .98-.32 3.2 1.22a10.9 10.9 0 0 1 5.82 0c2.2-1.54 3.18-1.22 3.18-1.22.64 1.65.24 2.87.12 3.17.75.84 1.2 1.9 1.2 3.2 0 4.58-2.74 5.6-5.35 5.9.42.37.8 1.08.8 2.18 0 1.57-.01 2.83-.01 3.22 0 .31.2.68.79.57a11.75 11.75 0 0 0 8-11.16A11.5 11.5 0 0 0 12 .5Z" />
            </svg>
            {t.landing.github}
          </a>
        </div>

        <p className="saas-footer-copy">&copy; {new Date().getFullYear()} CC. {t.landing.rights}</p>
      </footer>

      <AnimatePresence>
        {launching && (
          <Motion.div
            className="launch-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Motion.img
              src="/logo-300.webp"
              alt="Launching"
              initial={{ scale: 0.92, opacity: 0.8 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ repeat: Infinity, repeatType: 'reverse', duration: 0.7 }}
            />
            <p>{t.landing.loadingGuides}</p>
          </Motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}

export default LandingPage
