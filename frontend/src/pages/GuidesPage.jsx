import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import { useToast } from '../toast'
import './GuidesPage.css'

/* -- constants --------------------------------------------------------- */

const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
}

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.45 } },
  exit: { opacity: 0, transition: { duration: 0.28 } },
}

const TOAST_COPY = {
  fr: {
    openingAssistant: "Ouverture de l'assistant...",
    redirectingHome: 'Action validee. Redirection en cours...',
  },
  en: {
    openingAssistant: 'Opening assistant...',
    redirectingHome: 'Action confirmed. Redirecting...',
  },
  ko: {
    openingAssistant: '\uC5B4\uC2DC\uC2A4\uD134\uD2B8\uB97C \uC5EC\uB294 \uC911...',
    redirectingHome: '\uD655\uC778\uB418\uC5C8\uC2B5\uB2C8\uB2E4. \uC774\uB3D9 \uC911\uC785\uB2C8\uB2E4...',
  },
}

const BRAND_NAME_MAP = {
  bmw: 'BMW',
  citroen: 'Citro\u00ebn',
  mercedes: 'Mercedes-Benz',
  ds: 'DS',
}

const COMPACT_MENU_BREAKPOINT = 1024
const AUTO_ROTATE_INTERVAL = 3000
const DRAG_THRESHOLD = 40

const normalizeBrandName = (raw) => {
  const lower = (raw || '').trim().toLowerCase()
  return BRAND_NAME_MAP[lower] || raw.trim()
}

const toBrandSlug = (name) =>
  (name || '').trim().toLowerCase().replace(/\s+/g, '-')

/* -- component --------------------------------------------------------- */

function GuidesPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [lang, setLang] = useAppLanguage()
  const [guides, setGuides] = useState([])
  const [brands, setBrands] = useState([])
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedBrand, setSelectedBrand] = useState(null)
  const [pendingGuide, setPendingGuide] = useState(null)
  const [launchingSlug, setLaunchingSlug] = useState(null)
  const [langOpen, setLangOpen] = useState(false)
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [isCompactNav, setIsCompactNav] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= COMPACT_MENU_BREAKPOINT : false,
  )

  /* -- carousel state -------------------------------------------------- */
  const [carouselIndex, setCarouselIndex] = useState(0)
  const [isAutoRotating, setIsAutoRotating] = useState(true)
  const autoRotateTimer = useRef(null)
  const dragStartX = useRef(null)
  const carouselRef = useRef(null)

  const langDropdownRef = useRef(null)
  const searchInputRef = useRef(null)

  const t = UI_TEXT[lang] || UI_TEXT.fr
  const toastCopy = TOAST_COPY[lang] || TOAST_COPY.en
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]

  /* -- fetch guides ---------------------------------------------------- */

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
          brand: normalizeBrandName(guide.brand || ''),
          coverage_note: (guide.coverage_note || '').trim(),
        }))

        const sortedGuides = guidesList.sort((a, b) => a.name.localeCompare(b.name))

        const derivedBrands = [...new Set(sortedGuides.map((g) => g.brand).filter(Boolean))]
          .sort((a, b) => a.localeCompare(b))

        setGuides(sortedGuides)
        setBrands(derivedBrands)
      } catch {
        setErrorKey('serverError')
      } finally {
        setLoading(false)
      }
    }
    void fetchGuides()
  }, [])

  /* -- brand grouping -------------------------------------------------- */

  const brandGroups = useMemo(() => {
    const map = {}
    for (const guide of guides) {
      const brand = guide.brand || t.guides.brandUnknown || 'Unknown'
      if (!map[brand]) map[brand] = []
      map[brand].push(guide)
    }
    return map
  }, [guides, t.guides.brandUnknown])

  /* -- search filtering ------------------------------------------------ */

  const filteredBrands = useMemo(() => {
    if (!searchTerm.trim()) return brands
    const q = searchTerm.trim().toLowerCase()
    return brands.filter((brand) => {
      if (brand.toLowerCase().includes(q)) return true
      const vehicles = brandGroups[brand] || []
      return vehicles.some(
        (v) =>
          (v.name || '').toLowerCase().includes(q) ||
          (v.slug || '').toLowerCase().includes(q),
      )
    })
  }, [brands, searchTerm, brandGroups])

  const filteredVehiclesForBrand = useMemo(() => {
    if (!selectedBrand) return []
    const vehicles = brandGroups[selectedBrand] || []
    if (!searchTerm.trim()) return vehicles
    const q = searchTerm.trim().toLowerCase()
    return vehicles.filter(
      (v) =>
        (v.name || '').toLowerCase().includes(q) ||
        (v.slug || '').toLowerCase().includes(q) ||
        (v.brand || '').toLowerCase().includes(q),
    )
  }, [selectedBrand, brandGroups, searchTerm])

  /* -- carousel math --------------------------------------------------- */

  const numBrands = filteredBrands.length
  const angleStep = numBrands > 0 ? 360 / numBrands : 0
  const currentRotation = -(carouselIndex * angleStep)
  // Radius scales with number of items so they don't overlap
  const carouselRadius = Math.max(250, numBrands * 32)

  const frontBrand = numBrands > 0
    ? filteredBrands[((carouselIndex % numBrands) + numBrands) % numBrands]
    : null

  /* -- auto-rotate ------------------------------------------------------ */

  useEffect(() => {
    if (autoRotateTimer.current) clearInterval(autoRotateTimer.current)
    if (isAutoRotating && numBrands > 1 && !selectedBrand) {
      autoRotateTimer.current = setInterval(() => {
        setCarouselIndex((prev) => prev + 1)
      }, AUTO_ROTATE_INTERVAL)
    }
    return () => {
      if (autoRotateTimer.current) clearInterval(autoRotateTimer.current)
    }
  }, [isAutoRotating, numBrands, selectedBrand])

  const pauseAutoRotate = useCallback(() => {
    setIsAutoRotating(false)
  }, [])

  const resumeAutoRotateDelayed = useCallback(() => {
    setTimeout(() => setIsAutoRotating(true), 5000)
  }, [])

  /* -- carousel navigation --------------------------------------------- */

  const rotateLeft = useCallback(() => {
    pauseAutoRotate()
    setCarouselIndex((prev) => prev - 1)
    resumeAutoRotateDelayed()
  }, [pauseAutoRotate, resumeAutoRotateDelayed])

  const rotateRight = useCallback(() => {
    pauseAutoRotate()
    setCarouselIndex((prev) => prev + 1)
    resumeAutoRotateDelayed()
  }, [pauseAutoRotate, resumeAutoRotateDelayed])

  /* -- keyboard navigation --------------------------------------------- */

  useEffect(() => {
    if (selectedBrand) return undefined
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        rotateLeft()
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        rotateRight()
      } else if (e.key === 'Enter' && frontBrand) {
        e.preventDefault()
        handleBrandClick(frontBrand)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedBrand, rotateLeft, rotateRight, frontBrand, handleBrandClick])

  /* -- drag / swipe support -------------------------------------------- */

  const handlePointerDown = useCallback((e) => {
    dragStartX.current = e.clientX
  }, [])

  const handlePointerUp = useCallback((e) => {
    if (dragStartX.current === null) return
    const diff = e.clientX - dragStartX.current
    dragStartX.current = null
    if (Math.abs(diff) > DRAG_THRESHOLD) {
      if (diff > 0) rotateLeft()
      else rotateRight()
    }
  }, [rotateLeft, rotateRight])

  /* -- reset carousel index when search changes filtered brands -------- */

  useEffect(() => {
    setCarouselIndex(0)
  }, [searchTerm])

  /* -- responsive ------------------------------------------------------ */

  useEffect(() => {
    const handleResize = () => {
      const compact = window.innerWidth <= COMPACT_MENU_BREAKPOINT
      setIsCompactNav(compact)
      if (!compact) setNavMenuOpen(false)
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  /* -- outside click / escape handlers --------------------------------- */

  useEffect(() => {
    if (!langOpen) return undefined
    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false)
      }
    }
    const handleEscape = (event) => {
      if (event.key === 'Escape') setLangOpen(false)
    }
    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [langOpen])

  useEffect(() => {
    if (!navMenuOpen) return undefined
    const handleEscape = (event) => {
      if (event.key === 'Escape') setNavMenuOpen(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [navMenuOpen])

  useEffect(() => {
    if (!showExitConfirm) return undefined
    const handleEscape = (event) => {
      if (event.key === 'Escape') setShowExitConfirm(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [showExitConfirm])

  useEffect(() => {
    if (!pendingGuide) return undefined
    const handleEscape = (event) => {
      if (event.key === 'Escape') closeConfirmPopup()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [pendingGuide])

  /* -- actions --------------------------------------------------------- */

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
    setNavMenuOpen(false)
  }

  const openExitConfirm = () => {
    setLangOpen(false)
    setNavMenuOpen(false)
    setShowExitConfirm(true)
  }

  const closeExitConfirm = () => setShowExitConfirm(false)

  const confirmExitGuides = () => {
    closeExitConfirm()
    showToast({ type: 'success', message: toastCopy.redirectingHome })
    navigate('/')
  }

  const openConfirmPopup = (guide) => setPendingGuide(guide)

  const closeConfirmPopup = useCallback(() => {
    setPendingGuide(null)
  }, [])

  const launchGuideChat = (slug) => {
    if (!slug) return
    setPendingGuide(null)
    setLaunchingSlug(slug)
    showToast({
      type: 'info',
      message: t.guides.loadingAssistant || toastCopy.openingAssistant,
    })
    window.setTimeout(() => {
      navigate(`/chat/${slug}`)
    }, 520)
  }

  const handleBrandClick = useCallback((brand) => {
    setSelectedBrand(brand)
    setSearchTerm('')
  }, [])

  const handleBackToBrands = useCallback(() => {
    setSelectedBrand(null)
    setSearchTerm('')
  }, [])

  /* -- i18n shortcuts -------------------------------------------------- */

  const exitConfirmTitle = t.guides.exitConfirmTitle || 'Leave this page?'
  const exitConfirmText = t.guides.exitConfirmText || 'Are you sure you want to go back home?'
  const exitConfirmCancel = t.guides.exitConfirmCancel || 'Stay here'
  const exitConfirmAccept = t.guides.exitConfirmAccept || 'Yes, leave'
  const exitConfirmKicker =
    lang === 'fr'
      ? 'TERMINER LA LIAISON ?'
      : lang === 'ko'
        ? '\uB9C1\uD06C\uB97C \uC885\uB8CC\uD558\uC2DC\uACA0\uC2B5\uB2C8\uAE4C?'
        : 'TERMINATE NEURAL LINK?'
  const exitNodeLabel =
    lang === 'fr' ? 'NOEUD.ACTIF' : lang === 'ko' ? '\uD65C\uC131 \uB178\uB4DC' : 'ACTIVE.NODE'

  const vehicleCountLabel = (count) => {
    if (lang === 'fr') return `${count} v\u00e9hicule${count > 1 ? 's' : ''}`
    if (lang === 'ko') return `${count}\uB300 \uCC28\uB7C9`
    return `${count} vehicle${count > 1 ? 's' : ''}`
  }

  const backLabel =
    lang === 'fr' ? 'Retour aux marques' : lang === 'ko' ? '\uBE0C\uB79C\uB4DC\uB85C \uB3CC\uC544\uAC00\uAE30' : 'Back to brands'

  const startChatLabel =
    lang === 'fr' ? 'Commencer' : lang === 'ko' ? '\uCC44\uD305 \uC2DC\uC791' : 'Start'

  /* -- carousel item position helper ----------------------------------- */

  const getItemStyle = (idx) => {
    if (numBrands === 0) return {}

    // Normalize the visual index relative to front
    const normalizedCurrent = ((carouselIndex % numBrands) + numBrands) % numBrands
    let offset = idx - normalizedCurrent
    // Wrap around so items are positioned on the shorter arc
    if (offset > numBrands / 2) offset -= numBrands
    if (offset < -numBrands / 2) offset += numBrands

    const itemAngle = offset * angleStep
    const radians = (itemAngle * Math.PI) / 180

    // Project 3D onto 2D
    const x = Math.sin(radians) * carouselRadius
    const z = Math.cos(radians) * carouselRadius

    // Scale and opacity based on z-depth (front = max z = carouselRadius)
    const depthRatio = (z + carouselRadius) / (2 * carouselRadius) // 0..1, 1 = front
    const scale = 0.55 + 0.55 * depthRatio
    const opacity = 0.2 + 0.8 * depthRatio
    const zIndex = Math.round(depthRatio * 100)
    const isFront = offset === 0

    return {
      transform: `translateX(${x}px) translateZ(${z}px) scale(${isFront ? 1.3 : scale})`,
      opacity: isFront ? 1 : opacity,
      zIndex: isFront ? 200 : zIndex,
      filter: isFront ? 'none' : `brightness(${0.6 + 0.4 * depthRatio})`,
    }
  }

  /* -- render ---------------------------------------------------------- */

  return (
    <Motion.main className="guides-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <div className="guides-grid-overlay" />
      <div className="guides-light-bloom" />
      <div className="guides-bg-image" />

      <div className="guides-main-ui">
        {/* -- header -- */}
        <header className="guides-header">
          <div className="guides-header-left">
            <button type="button" className="guides-home-trigger" onClick={openExitConfirm} aria-label={t.guides.home}>
              <img src="/logo top left.png" alt="CarChat" />
            </button>
          </div>

          {isCompactNav ? (
            <button
              type="button"
              className="guides-burger-trigger"
              onClick={() => {
                setLangOpen(false)
                setNavMenuOpen((prev) => !prev)
              }}
              aria-label="Menu"
              aria-expanded={navMenuOpen}
              aria-haspopup="dialog"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          ) : (
            <div className="guides-lang-dropdown" ref={langDropdownRef}>
              <button
                type="button"
                className="guides-lang-trigger"
                onClick={() => setLangOpen((prev) => !prev)}
                aria-expanded={langOpen}
                aria-haspopup="menu"
              >
                <img
                  className="guides-lang-flag"
                  src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.en}
                  alt={`${currentLang?.label || 'EN'} flag`}
                />
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
                        <img
                          className="guides-lang-flag"
                          src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                          alt={`${entry.label} flag`}
                        />
                        {entry.label}
                      </button>
                    ))}
                  </Motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </header>

        {/* -- compact nav menu -- */}
        <AnimatePresence>
          {isCompactNav && navMenuOpen && (
            <Motion.div
              className="guides-nav-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setNavMenuOpen(false)}
            >
              <Motion.div
                className="guides-nav-menu"
                initial={{ opacity: 0, y: -10, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.98 }}
                transition={{ duration: 0.18 }}
                onClick={(event) => event.stopPropagation()}
              >
                <button type="button" className="guides-nav-home" onClick={openExitConfirm}>
                  {t.guides.home}
                </button>
                <div className="guides-nav-languages">
                  {LANGUAGES.map((entry) => (
                    <button
                      key={entry.code}
                      type="button"
                      className={`guides-nav-lang-option${entry.code === lang ? ' guides-nav-lang-option--active' : ''}`}
                      onClick={() => handleLangSelect(entry.code)}
                    >
                      <img
                        className="guides-lang-flag"
                        src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                        alt={`${entry.label} flag`}
                      />
                      <span>{entry.label}</span>
                    </button>
                  ))}
                </div>
              </Motion.div>
            </Motion.div>
          )}
        </AnimatePresence>

        {/* -- main content -- */}
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

          {/* loading / error / empty states */}
          {loading && (
            <div className="guides-state-block">
              <div className="loader-ring" />
              <p>{t.guides.loading}</p>
            </div>
          )}

          {errorKey && (
            <div className="guides-state-block guides-state-block--error">
              <p>{t.guides[errorKey] || t.guides.loadError}</p>
              <button type="button" onClick={() => window.location.reload()}>
                {t.guides.retry}
              </button>
            </div>
          )}

          {!loading && !errorKey && guides.length === 0 && (
            <div className="guides-state-block">
              <p>{t.guides.emptyTitle}</p>
              <p className="guides-state-hint">{t.guides.emptyHint}</p>
            </div>
          )}

          {/* -- loaded: carousel + vehicle cards -- */}
          {!loading && !errorKey && guides.length > 0 && (
            <>
              {/* search bar */}
              <div className="guides-search-bar">
                <svg className="guides-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  ref={searchInputRef}
                  type="text"
                  className="guides-search-input"
                  placeholder={t.guides.searchPlaceholder || 'Search...'}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  aria-label={t.guides.searchPlaceholder}
                />
                {searchTerm && (
                  <button
                    type="button"
                    className="guides-search-clear"
                    onClick={() => setSearchTerm('')}
                    aria-label="Clear"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>

              {/* -- Phase 1: 3D Brand Carousel -- */}
              <div className={`carousel-section${selectedBrand ? ' carousel-section--dimmed' : ''}`}>
                {numBrands === 0 && (
                  <div className="guides-state-block">
                    <p>{t.guides.noBrandMatch}</p>
                  </div>
                )}

                {numBrands > 0 && (
                  <>
                    <div
                      className="carousel-container"
                      ref={carouselRef}
                      onPointerDown={handlePointerDown}
                      onPointerUp={handlePointerUp}
                      onMouseEnter={pauseAutoRotate}
                      onMouseLeave={() => !selectedBrand && setIsAutoRotating(true)}
                    >
                      <div
                        className="carousel-track"
                        style={{ '--rotation': `${currentRotation}deg` }}
                      >
                        {filteredBrands.map((brand, idx) => {
                          const slug = toBrandSlug(brand)
                          const normalizedCurrent = ((carouselIndex % numBrands) + numBrands) % numBrands
                          const isFront = idx === normalizedCurrent
                          const itemStyle = getItemStyle(idx)

                          return (
                            <button
                              key={brand}
                              type="button"
                              className={`carousel-item${isFront ? ' carousel-item--active' : ''}`}
                              style={itemStyle}
                              onClick={() => {
                                if (isFront) {
                                  handleBrandClick(brand)
                                } else {
                                  // Rotate to this brand
                                  pauseAutoRotate()
                                  setCarouselIndex(idx)
                                  resumeAutoRotateDelayed()
                                }
                              }}
                              aria-label={brand}
                            >
                              <div className="carousel-item-inner">
                                <img
                                  className="carousel-item-logo"
                                  src={`/logos/${slug}.svg`}
                                  alt={brand}
                                  onError={(e) => {
                                    e.currentTarget.style.display = 'none'
                                    if (e.currentTarget.nextElementSibling) {
                                      e.currentTarget.nextElementSibling.style.display = 'flex'
                                    }
                                  }}
                                />
                                <span className="carousel-item-fallback" style={{ display: 'none' }}>
                                  {brand.charAt(0).toUpperCase()}
                                </span>
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    {/* carousel info below */}
                    <div className="carousel-info">
                      <h2 className="carousel-brand-name">{frontBrand || ''}</h2>
                      <span className="carousel-brand-count">
                        {frontBrand ? vehicleCountLabel((brandGroups[frontBrand] || []).length) : ''}
                      </span>
                    </div>

                    {/* arrow navigation */}
                    <div className="carousel-nav">
                      <button
                        type="button"
                        className="carousel-nav-btn carousel-nav-btn--left"
                        onClick={rotateLeft}
                        aria-label="Previous brand"
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                          <path d="M15 18l-6-6 6-6" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className="carousel-nav-btn carousel-nav-btn--right"
                        onClick={rotateRight}
                        aria-label="Next brand"
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                          <path d="M9 6l6 6-6 6" />
                        </svg>
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* -- Phase 2: Vehicle cards after brand selection -- */}
              <AnimatePresence>
                {selectedBrand && (
                  <Motion.div
                    key="vehicle-section"
                    className="guides-vehicle-section"
                    initial={{ opacity: 0, y: 40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 40 }}
                    transition={{ duration: 0.4, ease: 'easeOut' }}
                  >
                    <div className="guides-vehicle-header">
                      <button
                        type="button"
                        className="guides-back-btn"
                        onClick={handleBackToBrands}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                          <path d="M15 18l-6-6 6-6" />
                        </svg>
                        <span>{backLabel}</span>
                      </button>
                      <div className="guides-vehicle-brand-info">
                        <img
                          className="guides-vehicle-brand-logo"
                          src={`/logos/${toBrandSlug(selectedBrand)}.svg`}
                          alt={selectedBrand}
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                          }}
                        />
                        <h2>{selectedBrand}</h2>
                      </div>
                    </div>

                    <div className="guides-vehicle-grid">
                      {filteredVehiclesForBrand.length === 0 && (
                        <div className="guides-state-block">
                          <p>{t.guides.noBrandMatch}</p>
                        </div>
                      )}
                      {filteredVehiclesForBrand.map((guide, i) => {
                        const slug = toBrandSlug(selectedBrand)
                        return (
                          <Motion.article
                            key={guide.slug}
                            className="guides-vcard"
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: Math.min(i * 0.06, 0.36), duration: 0.35, ease: 'easeOut' }}
                            whileHover={{ y: -4, scale: 1.015 }}
                          >
                            <div className="guides-vcard-top">
                              <img
                                className="guides-vcard-brand-logo"
                                src={`/logos/${slug}.svg`}
                                alt={selectedBrand}
                                onError={(e) => { e.currentTarget.style.display = 'none' }}
                              />
                            </div>
                            <div className="guides-vcard-body">
                              <h3 className="guides-vcard-name">{guide.name}</h3>
                              {guide.coverage_note && (
                                <span className="guides-vcard-year">{guide.coverage_note}</span>
                              )}
                              <div className="guides-vcard-badges">
                                {guide.segment && (
                                  <span className={`guides-segment-badge guides-segment-badge--${guide.segment}`}>
                                    {(t.guides.segments || {})[guide.segment] || guide.segment}
                                  </span>
                                )}
                              </div>
                            </div>
                            <Motion.button
                              type="button"
                              className="guides-vcard-btn"
                              onClick={() => openConfirmPopup(guide)}
                              whileHover={{ scale: 1.03 }}
                              whileTap={{ scale: 0.96 }}
                            >
                              {startChatLabel}
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                                <path d="M5 12h14M12 5l7 7-7 7" />
                              </svg>
                            </Motion.button>
                          </Motion.article>
                        )
                      })}
                    </div>
                  </Motion.div>
                )}
              </AnimatePresence>
            </>
          )}
        </section>
      </div>

      {/* -- confirm vehicle popup -- */}
      <AnimatePresence>
        {pendingGuide && (
          <Motion.div
            className="guides-confirm-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeConfirmPopup}
          >
            <Motion.div
              className="guides-confirm-popup"
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.97 }}
              transition={{ duration: 0.24, ease: 'easeOut' }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="guides-confirm-top">
                <span className="guides-confirm-sigil" aria-hidden>{'\u25CE'}</span>
                <h2>{t.guides.confirmTitle}</h2>
                <p>{formatText(t.guides.confirmText, { vehicle: pendingGuide.name })}</p>
              </div>
              <div className="guides-confirm-actions">
                <button type="button" className="guides-confirm-cancel-btn" onClick={closeConfirmPopup}>
                  {t.guides.cancel}
                </button>
                <Motion.button
                  type="button"
                  className="guides-confirm-accept-btn"
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

      {/* -- launching overlay -- */}
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

      {/* -- exit confirmation -- */}
      <AnimatePresence>
        {showExitConfirm && (
          <Motion.div
            className="guides-exit-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeExitConfirm}
          >
            <Motion.div
              className="guides-exit-popup"
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 14, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="guides-exit-top">
                <span className="guides-exit-sigil" aria-hidden>{'\u25CE'}</span>
                <p className="guides-exit-kicker">{exitConfirmKicker}</p>
                <h2>{exitConfirmTitle}</h2>
                <p className="guides-exit-text">{exitConfirmText}</p>
              </div>
              <div className="guides-exit-actions">
                <button type="button" className="guides-exit-cancel" onClick={closeExitConfirm}>
                  {exitConfirmCancel}
                </button>
                <button type="button" className="guides-exit-accept" onClick={confirmExitGuides}>
                  {exitConfirmAccept}
                </button>
              </div>
              <div className="guides-exit-foot">
                <span>SYS.ID: AURIS-V3</span>
                <span>{exitNodeLabel}: {selectedBrand || 'HOME'}</span>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.main>
  )
}

export default GuidesPage
