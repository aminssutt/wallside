import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion as Motion } from 'framer-motion'
import './LandingPage.css'

const COLLISION_FRAMES = 30

const plans = [
  {
    key: 'free',
    name: 'Free Version',
    price: '0€',
    period: '/month',
    status: 'Available now',
    points: [
      'Access to chat',
      'Up to 5 prompts',
      "Manual-based answers",
    ],
    cta: 'Start free version',
    highlight: true,
  },
  {
    key: 'starter',
    name: 'Starter',
    price: '5,99€',
    period: '/month',
    status: 'Coming soon',
    points: [
      'Higher prompt quota',
      'Faster response queue',
      'Extended memory scope',
    ],
    cta: 'Coming soon',
    highlight: false,
  },
  {
    key: 'pro',
    name: 'Pro',
    price: '19,99€',
    period: '/month',
    status: 'Coming soon',
    points: [
      'Large prompt capacity',
      'Multi-manual support',
      'Advanced assistance layer',
    ],
    cta: 'Coming soon',
    highlight: false,
  },
]

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

  const collisionCanvasRef = useRef(null)
  const collisionFramesRef = useRef(Array(COLLISION_FRAMES).fill(null))

  const frameUrls = useMemo(
    () => Array.from({ length: COLLISION_FRAMES }, (_, idx) => framePath(idx + 1)),
    []
  )

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

  const launchFree = () => {
    if (launching) {
      return
    }

    setLaunching(true)
    window.setTimeout(() => {
      navigate('/start')
    }, 680)
  }

  return (
    <main className="saas-page">
      <section className="saas-hero">
        <Motion.div
          className="hero-collision-wrap"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <canvas ref={collisionCanvasRef} className="hero-collision-canvas" />
        </Motion.div>

        <Motion.p
          className="saas-subtitle"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.6 }}
        >
          Your car assistant that answers your questions based on your owner&apos;s manual.
        </Motion.p>

        <Motion.div
          className="saas-actions"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.55 }}
        >
          <Motion.button
            type="button"
            className="saas-btn saas-btn--primary"
            onClick={launchFree}
            whileHover={{ y: -2, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
          >
            Access to Chat
          </Motion.button>
          <Motion.a
            className="saas-btn saas-btn--secondary"
            href="#pricing"
            whileHover={{ y: -2 }}
          >
            View plans
          </Motion.a>
        </Motion.div>
      </section>

      <section className="saas-overview">
        <article className="overview-card">
          <h2>1. Upload your manual</h2>
          <p>
            Start by uploading your owner&apos;s manual in PDF. The platform organizes your vehicle content for smart retrieval.
          </p>
        </article>
        <article className="overview-card">
          <h2>2. Ask your questions</h2>
          <p>
            Use the chat to get direct answers on maintenance, usage, warnings and specifications from your own documentation.
          </p>
        </article>
      </section>

      <section id="pricing" className="pricing-section">
        <h2>Freemium Pricing</h2>
        <p>Start for free, upgrade when you need more capacity.</p>

        <div className="pricing-grid">
          {plans.map((plan) => (
            <article className={`pricing-card ${plan.highlight ? 'pricing-card--highlight' : ''}`} key={plan.key}>
              <div className="pricing-head">
                <h3>{plan.name}</h3>
                <span className={`pricing-badge ${plan.status === 'Coming soon' ? 'pricing-badge--soon' : ''}`}>
                  {plan.status}
                </span>
              </div>
              <p className="pricing-price">
                <strong>{plan.price}</strong> {plan.period}
              </p>
              <ul className="pricing-points">
                {plan.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
              <button
                type="button"
                className={`pricing-cta ${plan.highlight ? 'pricing-cta--active' : ''}`}
                onClick={plan.highlight ? launchFree : undefined}
                disabled={!plan.highlight}
              >
                {plan.cta}
              </button>
            </article>
          ))}
        </div>
      </section>

      <footer className="saas-footer">
        <div>
          <img src="/logo-84.webp" alt="CC" width="36" height="36" loading="lazy" />
          <p>Car Chat : CC</p>
        </div>
        <p>Freemium AI assistant for owner&apos;s manuals.</p>
        <p>© {new Date().getFullYear()} CC. All rights reserved.</p>
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
            <p>Opening your workspace...</p>
          </Motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}

export default LandingPage
