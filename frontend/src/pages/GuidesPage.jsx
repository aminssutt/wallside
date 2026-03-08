import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import './GuidesPage.css'

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.45 } },
  exit: { opacity: 0, transition: { duration: 0.28 } },
}

const cardVariants = {
  initial: { opacity: 0, y: 24, scale: 0.98 },
  animate: (i) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { delay: 0.14 + i * 0.08, duration: 0.45, ease: 'easeOut' },
  }),
}

function GuidesPage() {
  const navigate = useNavigate()
  const [lang, setLang] = useAppLanguage()
  const [guides, setGuides] = useState([])
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState('')
  const [pendingGuide, setPendingGuide] = useState(null)
  const [launchingSlug, setLaunchingSlug] = useState(null)
  const t = UI_TEXT[lang] || UI_TEXT.fr

  useEffect(() => {
    const fetchGuides = async () => {
      try {
        const res = await fetch(`${API_URL}/guides`)
        const data = await res.json()
        if (!data.success) {
          setErrorKey('loadError')
          return
        }

        const sortedGuides = (data.guides || []).sort((a, b) => a.name.localeCompare(b.name))
        setGuides(sortedGuides)
      } catch {
        setErrorKey('serverError')
      } finally {
        setLoading(false)
      }
    }

    void fetchGuides()
  }, [])

  const openConfirmPopup = (guide) => {
    setPendingGuide(guide)
  }

  const closeConfirmPopup = () => {
    setPendingGuide(null)
  }

  const launchGuideChat = (slug) => {
    if (!slug) return
    setLaunchingSlug(slug)
    window.setTimeout(() => {
      navigate(`/chat/${slug}`)
    }, 520)
  }

  return (
    <Motion.main
      className="guides-page"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="guides-grid-overlay" />
      <div className="guides-light-bloom" />

      <header className="guides-header">
        <Motion.button
          className="guides-back-btn"
          onClick={() => navigate('/')}
          whileHover={{ x: -3 }}
          whileTap={{ scale: 0.96 }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          {t.guides.home}
        </Motion.button>

        <div className="guides-lang-switcher" role="group" aria-label="Language selector">
          {LANGUAGES.map((entry) => (
            <button
              key={entry.code}
              type="button"
              className={`guides-lang-btn${entry.code === lang ? ' guides-lang-btn--active' : ''}`}
              onClick={() => setLang(entry.code)}
            >
              {entry.label}
            </button>
          ))}
        </div>
      </header>

      <section className="guides-content">
        <Motion.div
          className="guides-intro"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06, duration: 0.45 }}
        >
          <h1>{t.guides.title}</h1>
          <p>{t.guides.subtitle}</p>
        </Motion.div>

        {loading && (
          <div className="guides-state-block">
            <div className="loader-ring" />
            <p>{t.guides.loading}</p>
          </div>
        )}

        {errorKey && (
          <div className="guides-state-block guides-state-block--error">
            <p>{t.guides[errorKey] || t.guides.loadError}</p>
            <button type="button" onClick={() => window.location.reload()}>{t.guides.retry}</button>
          </div>
        )}

        {!loading && !errorKey && guides.length === 0 && (
          <div className="guides-state-block">
            <p>{t.guides.emptyTitle}</p>
            <p className="guides-state-hint">{t.guides.emptyHint}</p>
          </div>
        )}

        {!loading && !errorKey && guides.length > 0 && (
          <div className="guides-rail">
            {guides.map((guide, index) => (
              <Motion.article
                key={guide.slug}
                className="guide-teaser"
                custom={index}
                variants={cardVariants}
                initial="initial"
                animate="animate"
                whileHover={{ y: -6, scale: 1.02 }}
                whileTap={{ scale: 0.985 }}
                onClick={() => openConfirmPopup(guide)}
              >
                <div className="guide-teaser-image">
                  {guide.image ? (
                    <img src={`${API_URL}/images/${guide.image}`} alt={guide.name} loading="lazy" />
                  ) : (
                    <div className="guide-teaser-placeholder">CC</div>
                  )}
                  <div className="guide-teaser-metal" />
                </div>

                <div className="guide-teaser-body">
                  <h3>{guide.name}</h3>
                  <span>{t.guides.openPreview}</span>
                </div>
              </Motion.article>
            ))}
          </div>
        )}
      </section>

      <AnimatePresence>
        {pendingGuide && (
          <Motion.div
            className="guide-confirm-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeConfirmPopup}
          >
            <Motion.div
              className="guide-confirm-popup"
              initial={{ opacity: 0, y: 26, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.98 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="guide-confirm-top">
                <h2>{t.guides.confirmTitle}</h2>
                <p>{formatText(t.guides.confirmText, { vehicle: pendingGuide.name })}</p>
              </div>

              <div className="guide-confirm-card">
                {pendingGuide.image ? (
                  <img src={`${API_URL}/images/${pendingGuide.image}`} alt={pendingGuide.name} loading="lazy" />
                ) : (
                  <div className="guide-teaser-placeholder">CC</div>
                )}
                <span>{pendingGuide.name}</span>
              </div>

              <div className="guide-confirm-actions">
                <button type="button" className="guide-confirm-cancel" onClick={closeConfirmPopup}>
                  {t.guides.cancel}
                </button>
                <Motion.button
                  type="button"
                  className="guide-confirm-accept"
                  onClick={() => launchGuideChat(pendingGuide.slug)}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.97 }}
                >
                  {t.guides.confirm}
                </Motion.button>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {launchingSlug && (
          <Motion.div
            className="guides-transition-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="loader-ring" />
            <p>{t.guides.loadingAssistant}</p>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.main>
  )
}

export default GuidesPage
