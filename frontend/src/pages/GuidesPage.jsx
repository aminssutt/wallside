import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import { useToast } from '../toast'
import './GuidesPage.css'

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
    openingAssistant: '어시스턴트를 여는 중...',
    redirectingHome: '확인되었습니다. 이동 중입니다...',
  },
}

const ALL_BRANDS_VALUE = '__all__'
const CAROUSEL_OFFSETS = [-3, -2, -1, 0, 1, 2, 3]
const COMPACT_CAROUSEL_OFFSETS = [-2, -1, 0, 1, 2]
const COMPACT_MENU_BREAKPOINT = 1024

const IMAGE_CACHE_BUSTER = '2026-03-16-vehicle-fix-2'
const buildImageUrl = (imageFilename) =>
  `${API_URL}/images/${encodeURIComponent(imageFilename)}?v=${IMAGE_CACHE_BUSTER}`

const wrapIndex = (value, total) => ((value % total) + total) % total

const getShortestOffset = (targetIndex, currentIndex, total) => {
  if (total <= 1) return 0
  let offset = targetIndex - currentIndex
  if (offset > total / 2) offset -= total
  if (offset < -total / 2) offset += total
  return offset
}

function GuidesPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [lang, setLang] = useAppLanguage()
  const [guides, setGuides] = useState([])
  const [brands, setBrands] = useState([])
  const [selectedBrand, setSelectedBrand] = useState(ALL_BRANDS_VALUE)
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState('')
  const [pendingGuide, setPendingGuide] = useState(null)
  const [confirmPhase, setConfirmPhase] = useState('focus')
  const [launchingSlug, setLaunchingSlug] = useState(null)
  const [langOpen, setLangOpen] = useState(false)
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const [brandPickerOpen, setBrandPickerOpen] = useState(false)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [activeGuideSlug, setActiveGuideSlug] = useState('')
  const [carouselWidth, setCarouselWidth] = useState(0)
  const [isCompactNav, setIsCompactNav] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= COMPACT_MENU_BREAKPOINT : false,
  )
  const langDropdownRef = useRef(null)
  const brandPopupRef = useRef(null)
  const modelPopupRef = useRef(null)
  const carouselViewportRef = useRef(null)
  const draggingCarouselRef = useRef(false)
  const confirmRevealTimerRef = useRef(null)
  const confirmCloseTimerRef = useRef(null)
  const t = UI_TEXT[lang] || UI_TEXT.fr
  const toastCopy = TOAST_COPY[lang] || TOAST_COPY.en
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]

  const filterLabel = t.guides.brandFilterLabel
  const allBrandsLabel = t.guides.allBrands
  const noBrandMatch = t.guides.noBrandMatch
  const brandUnknownLabel = t.guides.brandUnknown
  const coverageLabel = t.guides.coverageLabel || '{coverage}'
  const selectedBrandLabel = selectedBrand === ALL_BRANDS_VALUE ? allBrandsLabel : selectedBrand
  const modelFilterLabel = t.guides.modelFilterLabel || 'Choose model'
  const modelFilterPlaceholder = t.guides.modelFilterPlaceholder || 'Select a model'
  const swipeHintLabel = t.guides.swipeHint || 'Swipe on mobile or use arrows on tablet and desktop.'
  const previousModelLabel = t.guides.previousModel || 'Previous model'
  const nextModelLabel = t.guides.nextModel || 'Next model'
  const guidesSubtitle = t.guides.subtitle
  const exitConfirmTitle = t.guides.exitConfirmTitle || 'Leave this page?'
  const exitConfirmText = t.guides.exitConfirmText || 'Are you sure you want to go back home?'
  const exitConfirmCancel = t.guides.exitConfirmCancel || 'Stay here'
  const exitConfirmAccept = t.guides.exitConfirmAccept || 'Yes, leave'
  const isGuideFocusActive = Boolean(pendingGuide)

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
          coverage_note: (guide.coverage_note || '').trim(),
          manual_count: Number(guide.manual_count || 1),
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
    if (!langOpen && !brandPickerOpen && !modelPickerOpen) {
      return undefined
    }

    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false)
      }
      if (brandPopupRef.current && !brandPopupRef.current.contains(event.target)) {
        setBrandPickerOpen(false)
      }
      if (modelPopupRef.current && !modelPopupRef.current.contains(event.target)) {
        setModelPickerOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setLangOpen(false)
        setBrandPickerOpen(false)
        setModelPickerOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [langOpen, brandPickerOpen, modelPickerOpen])

  useEffect(() => {
    const handleResize = () => {
      const compact = window.innerWidth <= COMPACT_MENU_BREAKPOINT
      setIsCompactNav(compact)
      if (!compact) {
        setNavMenuOpen(false)
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    if (!navMenuOpen) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setNavMenuOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [navMenuOpen])

  useEffect(() => {
    if (selectedBrand === ALL_BRANDS_VALUE) {
      return
    }
    if (!brands.some((brand) => brand.toLowerCase() === selectedBrand.toLowerCase())) {
      setSelectedBrand(ALL_BRANDS_VALUE)
    }
  }, [brands, selectedBrand])

  useEffect(() => {
    if (!showExitConfirm) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setShowExitConfirm(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [showExitConfirm])

  useEffect(() => {
    if (!pendingGuide) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        closeConfirmPopup()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [pendingGuide, confirmPhase])

  const filteredGuides = useMemo(() => {
    if (selectedBrand === ALL_BRANDS_VALUE) {
      return guides
    }
    return guides.filter(
      (guide) => (guide.brand || '').toLowerCase() === selectedBrand.toLowerCase(),
    )
  }, [guides, selectedBrand])

  useEffect(() => {
    if (filteredGuides.length === 0) {
      setActiveGuideSlug('')
      return
    }
    if (!filteredGuides.some((guide) => guide.slug === activeGuideSlug)) {
      setActiveGuideSlug(filteredGuides[0].slug)
    }
  }, [filteredGuides, activeGuideSlug])

  useEffect(() => {
    const viewport = carouselViewportRef.current
    if (!viewport) return undefined

    const updateCarouselWidth = () => {
      setCarouselWidth(viewport.clientWidth)
    }

    updateCarouselWidth()

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => updateCarouselWidth())
      observer.observe(viewport)
      return () => observer.disconnect()
    }

    window.addEventListener('resize', updateCarouselWidth)
    return () => window.removeEventListener('resize', updateCarouselWidth)
  }, [])

  const activeGuideIndex = useMemo(() => {
    if (filteredGuides.length === 0) return -1
    return filteredGuides.findIndex((guide) => guide.slug === activeGuideSlug)
  }, [filteredGuides, activeGuideSlug])

  const safeActiveIndex = activeGuideIndex >= 0 ? activeGuideIndex : 0
  const activeGuide = filteredGuides[safeActiveIndex] || null

  const carouselCards = useMemo(() => {
    const total = filteredGuides.length
    if (!total) return []

    const seen = new Set()
    const cards = []
    const offsets = total <= 3
      ? [-1, 0, 1]
      : carouselWidth > 0 && carouselWidth < 760
        ? COMPACT_CAROUSEL_OFFSETS
        : CAROUSEL_OFFSETS

    offsets.forEach((offset) => {
      const nextIndex = wrapIndex(safeActiveIndex + offset, total)
      if (seen.has(nextIndex)) return
      seen.add(nextIndex)
      const signedOffset = getShortestOffset(nextIndex, safeActiveIndex, total)
      cards.push({
        guide: filteredGuides[nextIndex],
        index: nextIndex,
        offset: signedOffset,
      })
    })

    cards.sort((a, b) => a.offset - b.offset)
    return cards
  }, [filteredGuides, safeActiveIndex, carouselWidth])

  const carouselStep = useMemo(() => {
    if (!carouselWidth) return 220
    if (carouselWidth < 640) {
      return Math.max(220, Math.min(380, carouselWidth * 0.84))
    }
    return Math.max(420, Math.min(700, carouselWidth * 0.62))
  }, [carouselWidth])

  const canSlideCarousel = filteredGuides.length > 1

  const openConfirmPopup = (guide) => {
    setModelPickerOpen(false)
    setBrandPickerOpen(false)
    if (confirmRevealTimerRef.current) {
      window.clearTimeout(confirmRevealTimerRef.current)
      confirmRevealTimerRef.current = null
    }
    if (confirmCloseTimerRef.current) {
      window.clearTimeout(confirmCloseTimerRef.current)
      confirmCloseTimerRef.current = null
    }
    setConfirmPhase('focus')
    setPendingGuide(guide)
  }

  const closeConfirmPopup = () => {
    if (!pendingGuide || confirmPhase === 'closing') return

    if (confirmRevealTimerRef.current) {
      window.clearTimeout(confirmRevealTimerRef.current)
      confirmRevealTimerRef.current = null
    }

    setConfirmPhase('closing')

    confirmCloseTimerRef.current = window.setTimeout(() => {
      setPendingGuide(null)
      setConfirmPhase('focus')
      confirmCloseTimerRef.current = null
    }, 340)
  }

  const launchGuideChat = (slug) => {
    if (!slug) return
    if (confirmRevealTimerRef.current) {
      window.clearTimeout(confirmRevealTimerRef.current)
      confirmRevealTimerRef.current = null
    }
    if (confirmCloseTimerRef.current) {
      window.clearTimeout(confirmCloseTimerRef.current)
      confirmCloseTimerRef.current = null
    }
    setPendingGuide(null)
    setConfirmPhase('focus')
    setLaunchingSlug(slug)
    showToast({
      type: 'info',
      message: t.guides.loadingAssistant || toastCopy.openingAssistant,
    })
    window.setTimeout(() => {
      navigate(`/chat/${slug}`)
    }, 520)
  }

  useEffect(() => {
    if (!pendingGuide) return undefined

    setConfirmPhase('focus')
    confirmRevealTimerRef.current = window.setTimeout(() => {
      setConfirmPhase('revealed')
      confirmRevealTimerRef.current = null
    }, 320)

    return () => {
      if (confirmRevealTimerRef.current) {
        window.clearTimeout(confirmRevealTimerRef.current)
        confirmRevealTimerRef.current = null
      }
    }
  }, [pendingGuide])

  useEffect(() => {
    return () => {
      if (confirmRevealTimerRef.current) {
        window.clearTimeout(confirmRevealTimerRef.current)
      }
      if (confirmCloseTimerRef.current) {
        window.clearTimeout(confirmCloseTimerRef.current)
      }
    }
  }, [])

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
    setNavMenuOpen(false)
  }

  const handleBrandSelect = (brandValue) => {
    setSelectedBrand(brandValue)
    setBrandPickerOpen(false)
    setModelPickerOpen(false)
  }

  const setActiveGuideByIndex = (nextIndex) => {
    if (!filteredGuides.length) return
    const wrapped = wrapIndex(nextIndex, filteredGuides.length)
    setActiveGuideSlug(filteredGuides[wrapped].slug)
  }

  const goToPreviousGuide = () => {
    if (!canSlideCarousel) return
    setActiveGuideByIndex(safeActiveIndex - 1)
  }

  const goToNextGuide = () => {
    if (!canSlideCarousel) return
    setActiveGuideByIndex(safeActiveIndex + 1)
  }

  const handleModelSelect = (slug) => {
    setActiveGuideSlug(slug)
    setModelPickerOpen(false)
  }

  const handleCarouselDragStart = () => {
    draggingCarouselRef.current = true
  }

  const handleCarouselDragEnd = (_event, info) => {
    if (!canSlideCarousel) return

    const travelThreshold = Math.max(48, carouselWidth * 0.1)
    const velocityThreshold = 520
    const movedLeft = info.offset.x <= -travelThreshold || info.velocity.x <= -velocityThreshold
    const movedRight = info.offset.x >= travelThreshold || info.velocity.x >= velocityThreshold

    if (movedLeft) {
      goToNextGuide()
    } else if (movedRight) {
      goToPreviousGuide()
    }

    window.setTimeout(() => {
      draggingCarouselRef.current = false
    }, 0)
  }

  const handleCardClick = (guide, offset) => {
    if (draggingCarouselRef.current) return
    if (offset === 0) {
      openConfirmPopup(guide)
      return
    }
    setActiveGuideSlug(guide.slug)
  }

  const openExitConfirm = () => {
    setLangOpen(false)
    setNavMenuOpen(false)
    setBrandPickerOpen(false)
    setModelPickerOpen(false)
    setShowExitConfirm(true)
  }

  const closeExitConfirm = () => {
    setShowExitConfirm(false)
  }

  const confirmExitGuides = () => {
    closeExitConfirm()
    showToast({ type: 'success', message: toastCopy.redirectingHome })
    navigate('/')
  }

  return (
    <Motion.main
      className={`guides-page${isGuideFocusActive ? ' guides-page--focus-mode' : ''}`}
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="guides-grid-overlay" />
      <div className="guides-light-bloom" />
      <div className="guides-bg-image" />

      <div className={`guides-main-ui${isGuideFocusActive ? ' guides-main-ui--hidden' : ''}`}>
        <header className="guides-header">
          <div className="guides-header-left">
            {isCompactNav ? (
              <div className="guides-home-brand guides-home-brand--static" aria-hidden>
                <img src="/logo top left.png" alt="CarChat" />
              </div>
            ) : (
              <button
                type="button"
                className="guides-home-brand"
                onClick={openExitConfirm}
                aria-label={t.guides.home}
              >
                <img src="/logo top left.png" alt="CarChat" />
              </button>
            )}
          </div>

          {isCompactNav ? (
            <button
              type="button"
              className="guides-burger-trigger"
              onClick={() => {
                setLangOpen(false)
                setBrandPickerOpen(false)
                setModelPickerOpen(false)
                setNavMenuOpen((previous) => !previous)
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
                onClick={() => setLangOpen((previous) => !previous)}
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

        {!loading && !errorKey && (
          <div className="guides-filters">
            {brands.length > 0 && (
              <div className="guides-brand-filter">
                <p>{filterLabel}</p>
                <button
                  type="button"
                  className="guides-brand-trigger"
                  onClick={() => {
                    setModelPickerOpen(false)
                    setBrandPickerOpen((prev) => !prev)
                  }}
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

            {filteredGuides.length > 0 && (
              <div className="guides-model-filter">
                <p>{modelFilterLabel}</p>
                <button
                  type="button"
                  className="guides-model-trigger"
                  onClick={() => {
                    setBrandPickerOpen(false)
                    setModelPickerOpen((prev) => !prev)
                  }}
                  aria-expanded={modelPickerOpen}
                  aria-haspopup="dialog"
                >
                  <span>{activeGuide?.name || modelFilterPlaceholder}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
              </div>
            )}
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
          <div className="guides-carousel-shell" role="region" aria-label={t.guides.title}>
            <button
              type="button"
              className="guides-carousel-arrow guides-carousel-arrow--left"
              onClick={goToPreviousGuide}
              aria-label={previousModelLabel}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>

            <Motion.div
              className="guides-carousel-viewport"
              ref={carouselViewportRef}
              tabIndex={0}
              drag={canSlideCarousel ? 'x' : false}
              dragConstraints={{ left: 0, right: 0 }}
              dragElastic={0.12}
              dragMomentum={false}
              onDragStart={handleCarouselDragStart}
              onDragEnd={handleCarouselDragEnd}
              onKeyDown={(event) => {
                if (event.key === 'ArrowLeft') {
                  event.preventDefault()
                  goToPreviousGuide()
                }
                if (event.key === 'ArrowRight') {
                  event.preventDefault()
                  goToNextGuide()
                }
              }}
            >
              <AnimatePresence initial={false}>
                {carouselCards.map(({ guide, offset, index }) => {
                  const distance = Math.abs(offset)
                  const scale = distance === 0 ? 0.9 : distance === 1 ? 0.5 : distance === 2 ? 0.3 : 0.18
                  const opacity = distance === 0 ? 1 : distance === 1 ? 0.42 : distance === 2 ? 0.08 : 0
                  const blur = distance === 0 ? 0 : distance === 1 ? 0.8 : distance === 2 ? 2.3 : 3.8
                  const x = offset * carouselStep
                  const rotateY = offset === 0 ? 0 : offset < 0 ? 8 + distance * 4 : -(8 + distance * 4)

                  return (
                    <Motion.article
                      key={guide.slug}
                      className={`guide-teaser${offset === 0 ? ' guide-teaser--active' : ''}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleCardClick(guide, offset)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          handleCardClick(guide, offset)
                        }
                      }}
                      style={{
                        '--float-delay': `${index * 0.15}s`,
                        pointerEvents: distance > 1 ? 'none' : 'auto',
                      }}
                      initial={{ opacity: 0, y: 16, scale: 0.95 }}
                      animate={{
                        x,
                        scale,
                        opacity,
                        rotateY,
                        filter: `blur(${blur}px)`,
                        y: distance === 0 ? 0 : distance === 1 ? 8 : distance === 2 ? 15 : 20,
                        zIndex: 20 - distance,
                      }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      transition={{
                        type: 'spring',
                        stiffness: 280,
                        damping: 28,
                        mass: 0.9,
                      }}
                      whileHover={distance <= 1 ? { scale: scale + 0.06, y: distance === 0 ? -10 : -2 } : undefined}
                      whileTap={{ scale: scale * 0.97 }}
                    >
                      <div className="guide-floating-vehicle">
                        {guide.image ? (
                          <img src={buildImageUrl(guide.image)} alt={guide.name} loading="lazy" />
                        ) : (
                          <div className="guide-teaser-placeholder">CC</div>
                        )}
                      </div>

                      <p className="guide-floating-name">{guide.name}</p>
                    </Motion.article>
                  )
                })}
              </AnimatePresence>
            </Motion.div>

            <button
              type="button"
              className="guides-carousel-arrow guides-carousel-arrow--right"
              onClick={goToNextGuide}
              aria-label={nextModelLabel}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>

            <p className="guides-carousel-hint">{swipeHintLabel}</p>
          </div>
        )}
        </section>
      </div>

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
        {modelPickerOpen && filteredGuides.length > 0 && (
          <Motion.div
            className="guides-model-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setModelPickerOpen(false)}
          >
            <Motion.div
              className="guides-model-popup"
              ref={modelPopupRef}
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 14, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onClick={(event) => event.stopPropagation()}
            >
              <h3>{modelFilterLabel}</h3>
              <div className="guides-model-options">
                {filteredGuides.map((guide) => (
                  <button
                    key={guide.slug}
                    type="button"
                    className={`guides-model-option${guide.slug === activeGuideSlug ? ' guides-model-option--active' : ''}`}
                    onClick={() => handleModelSelect(guide.slug)}
                  >
                    <span>{guide.name}</span>
                    <small>{guide.brand || brandUnknownLabel}</small>
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
            className={`guide-focus-stage guide-focus-stage--${confirmPhase}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Motion.div
              className="guide-focus-vehicle-wrap"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={
                confirmPhase === 'focus'
                  ? { opacity: 1, scale: 1.04, y: -4 }
                  : confirmPhase === 'revealed'
                    ? { opacity: 1, scale: 1, y: 0 }
                    : { opacity: 0.96, scale: 1.02, y: -3 }
              }
              transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="guide-focus-vehicle">
                {pendingGuide.image ? (
                  <img src={buildImageUrl(pendingGuide.image)} alt={pendingGuide.name} loading="lazy" />
                ) : (
                  <div className="guide-teaser-placeholder">CC</div>
                )}
              </div>
            </Motion.div>

            <div className="guide-focus-meta">
              <h2>{pendingGuide.name}</h2>
              <p>{pendingGuide.brand || brandUnknownLabel}</p>
              {pendingGuide.coverage_note ? (
                <small>{formatText(coverageLabel, { coverage: pendingGuide.coverage_note })}</small>
              ) : null}
            </div>

            <div className="guide-focus-actions">
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
                <h2>{exitConfirmTitle}</h2>
                <p>{exitConfirmText}</p>
              </div>

              <div className="guides-exit-actions">
                <button type="button" className="guides-exit-cancel" onClick={closeExitConfirm}>
                  {exitConfirmCancel}
                </button>
                <button type="button" className="guides-exit-accept" onClick={confirmExitGuides}>
                  {exitConfirmAccept}
                </button>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.main>
  )
}

export default GuidesPage

