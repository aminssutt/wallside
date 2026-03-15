import { useEffect, useMemo, useRef, useState } from 'react'
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

const ALL_BRANDS_VALUE = '__all__'

const buildImageUrl = (imageFilename) => `${API_URL}/images/${encodeURIComponent(imageFilename)}`

function GuidesPage() {
  const navigate = useNavigate()
  const [lang, setLang] = useAppLanguage()
  const [guides, setGuides] = useState([])
  const [brands, setBrands] = useState([])
  const [selectedBrand, setSelectedBrand] = useState(ALL_BRANDS_VALUE)
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState('')
  const [pendingGuide, setPendingGuide] = useState(null)
  const [launchingSlug, setLaunchingSlug] = useState(null)
  const [langOpen, setLangOpen] = useState(false)
  const [brandPickerOpen, setBrandPickerOpen] = useState(false)
  const langDropdownRef = useRef(null)
  const brandPopupRef = useRef(null)
  const t = UI_TEXT[lang] || UI_TEXT.fr
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]

  const filterLabel = t.guides.brandFilterLabel
  const allBrandsLabel = t.guides.allBrands
  const noBrandMatch = t.guides.noBrandMatch
  const brandUnknownLabel = t.guides.brandUnknown
  const selectedBrandLabel = selectedBrand === ALL_BRANDS_VALUE ? allBrandsLabel : selectedBrand
  const guidesSubtitle = t.guides.subtitle

  useEffect(() => {
    const fetchGuides = async () => {
      try {
        const res = await fetch(`${API_URL}/guides`)
        const data = await res.json()
        if (!data.success) {
          setErrorKey('loadError')
          return
        }

        const guidesList = (data.guides || []).map((guide) => ({
          ...guide,
          brand: (guide.brand || '').trim(),
        }))
        const sortedGuides = guidesList.sort((a, b) => a.name.localeCompare(b.name))
        const apiBrands = (data.brands || [])
          .map((value) => String(value || '').trim())
          .filter(Boolean)
        const derivedBrands = [...new Set(guidesList.map((guide) => guide.brand).filter(Boolean))]
        const sortedBrands = (apiBrands.length ? apiBrands : derivedBrands)
          .sort((a, b) => a.localeCompare(b))

        setGuides(sortedGuides)
        setBrands(sortedBrands)
      } catch {
        setErrorKey('serverError')
      } finally {
        setLoading(false)
      }
    }

    void fetchGuides()
  }, [])

  useEffect(() => {
    if (!langOpen && !brandPickerOpen) {
      return undefined
    }

    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false)
      }
      if (brandPopupRef.current && !brandPopupRef.current.contains(event.target)) {
        setBrandPickerOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setLangOpen(false)
        setBrandPickerOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [langOpen, brandPickerOpen])

  useEffect(() => {
    if (selectedBrand === ALL_BRANDS_VALUE) {
      return
    }
    if (!brands.some((brand) => brand.toLowerCase() === selectedBrand.toLowerCase())) {
      setSelectedBrand(ALL_BRANDS_VALUE)
    }
  }, [brands, selectedBrand])

  const filteredGuides = useMemo(() => {
    if (selectedBrand === ALL_BRANDS_VALUE) {
      return guides
    }
    return guides.filter(
      (guide) => (guide.brand || '').toLowerCase() === selectedBrand.toLowerCase(),
    )
  }, [guides, selectedBrand])

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

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
  }

  const handleBrandSelect = (brandValue) => {
    setSelectedBrand(brandValue)
    setBrandPickerOpen(false)
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

        <div className="guides-lang-dropdown" ref={langDropdownRef}>
          <button
            type="button"
            className="guides-lang-trigger"
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
                className="guides-lang-menu"
                initial={{ opacity: 0, y: -6, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.96 }}
                transition={{ duration: 0.16 }}
              >
                {LANGUAGES.map((entry) => (
                  <button
                    key={entry.code}
                    type="button"
                    className={`guides-lang-item${entry.code === lang ? ' guides-lang-item--active' : ''}`}
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
      </header>

      <section className="guides-content">
        <Motion.div
          className="guides-intro"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.06, duration: 0.45 }}
        >
          <h1>{t.guides.title}</h1>
          <p>{guidesSubtitle}</p>
        </Motion.div>

        {!loading && !errorKey && brands.length > 0 && (
          <div className="guides-brand-filter">
            <p>{filterLabel}</p>
            <button
              type="button"
              className="guides-brand-trigger"
              onClick={() => setBrandPickerOpen((prev) => !prev)}
              aria-expanded={brandPickerOpen}
              aria-haspopup="dialog"
            >
              <span>{selectedBrandLabel}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </div>
        )}

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

        {!loading && !errorKey && guides.length > 0 && filteredGuides.length === 0 && (
          <div className="guides-state-block">
            <p>{noBrandMatch}</p>
          </div>
        )}

        {!loading && !errorKey && guides.length > 0 && filteredGuides.length > 0 && (
          <div className="guides-rail">
            {filteredGuides.map((guide, index) => (
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
                    <img src={buildImageUrl(guide.image)} alt={guide.name} loading="lazy" />
                  ) : (
                    <div className="guide-teaser-placeholder">CC</div>
                  )}
                  <div className="guide-teaser-metal" />
                </div>

                <div className="guide-teaser-body">
                  <div className="guide-teaser-meta">
                    <h3>{guide.name}</h3>
                    <p>{guide.brand || brandUnknownLabel}</p>
                  </div>
                  <span>{t.guides.openPreview}</span>
                </div>
              </Motion.article>
            ))}
          </div>
        )}
      </section>

      <AnimatePresence>
        {brandPickerOpen && (
          <Motion.div
            className="guides-brand-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setBrandPickerOpen(false)}
          >
            <Motion.div
              className="guides-brand-popup"
              ref={brandPopupRef}
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 14, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onClick={(event) => event.stopPropagation()}
            >
              <h3>{filterLabel}</h3>
              <div className="guides-brand-options">
                <button
                  type="button"
                  className={`guides-brand-option${selectedBrand === ALL_BRANDS_VALUE ? ' guides-brand-option--active' : ''}`}
                  onClick={() => handleBrandSelect(ALL_BRANDS_VALUE)}
                >
                  {allBrandsLabel}
                </button>
                {brands.map((brand) => (
                  <button
                    key={brand}
                    type="button"
                    className={`guides-brand-option${selectedBrand.toLowerCase() === brand.toLowerCase() ? ' guides-brand-option--active' : ''}`}
                    onClick={() => handleBrandSelect(brand)}
                  >
                    {brand}
                  </button>
                ))}
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>

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
                  <img src={buildImageUrl(pendingGuide.image)} alt={pendingGuide.name} loading="lazy" />
                ) : (
                  <div className="guide-teaser-placeholder">CC</div>
                )}
                <span>{pendingGuide.name}</span>
                <small>{pendingGuide.brand || brandUnknownLabel}</small>
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

