import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import { useToast } from '../toast'
import './ChatPage.css'
import wrenchIcon from '../assets/icons/wrench.svg'
import dashboardIcon from '../assets/icons/dashboard.svg'
import navigationIcon from '../assets/icons/navigation.svg'

const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
}

const QUICK_ICONS = [wrenchIcon, dashboardIcon, navigationIcon]
const COMPACT_MENU_BREAKPOINT = 1024
const CHAT_REQUEST_TIMEOUT_MS = 45000
const MAX_INPUT_LENGTH = 3000
const KNOWN_STREAM_EVENTS = new Set([
  'start', 'chunk', 'end', 'error',
  'sources_start', 'source_item', 'sources_end',
  'video_result', 'video_none',
  'status',
])

const generateSessionId = () => {
  const arr = new Uint8Array(16)
  crypto.getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}
const ASSISTANT_ALIAS_BANK = {
  fr: {
    prefix: ['Atelier', 'Circuit', 'Pitlane', 'Moteur', 'Garage', 'Turbo'],
    core: ['Nova', 'Apex', 'Vortex', 'Volt', 'Piston', 'Sprint'],
  },
  en: {
    prefix: ['Torque', 'Apex', 'Pitlane', 'Drive', 'Garage', 'Vector'],
    core: ['Nova', 'Pulse', 'Vortex', 'Volt', 'Piston', 'Sprint'],
  },
  ko: {
    prefix: ['피트', '터보', '드라이브', '모터', '레이스', '기어'],
    core: ['노바', '펄스', '벡터', '볼트', '피스톤', '스프린트'],
  },
}

const pickRandom = (items) => items[Math.floor(Math.random() * items.length)]

const generateAssistantAlias = (lang = 'en') => {
  const bank = ASSISTANT_ALIAS_BANK[lang] || ASSISTANT_ALIAS_BANK.en
  const serial = Math.floor(10 + Math.random() * 90)
  return `${pickRandom(bank.prefix)} ${pickRandom(bank.core)}-${serial}`
}

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.35 } },
  exit: { opacity: 0, transition: { duration: 0.25 } },
}

const TOAST_COPY = {
  fr: {
    redirecting: 'Action validée. Redirection en cours...',
  },
  en: {
    redirecting: 'Action confirmed. Redirecting...',
  },
  ko: {
    redirecting: '확인되었습니다. 이동 중입니다...',
  },
}

const URL_REGEX = /(https?:\/\/[^\s)]+)/g
const YOUTUBE_URL_REGEX = /(https?:\/\/(?:www\.)?(?:youtube\.com\/[^\s)]+|youtu\.be\/[^\s)]+))/i
const VIDEO_LABEL_REGEX = /^(?:video.*youtube.*|recommended youtube video|youtube recommended video)\s*:?\s*$/i
const VIDEO_UI = {
  fr: { badge: 'Vidéo conseillée', action: 'Voir la vidéo' },
  en: { badge: 'Suggested video', action: 'Watch video' },
  ko: { badge: 'Recommended video', action: 'Open video' },
}

const sanitizeUrl = (url) => {
  return String(url || '').replace(/[)\],.;!?]+$/g, '')
}

const extractYoutubeId = (urlValue) => {
  try {
    const parsed = new URL(urlValue)
    const host = parsed.hostname.replace(/^www\./i, '').toLowerCase()
    if (host === 'youtu.be') {
      return parsed.pathname.split('/').filter(Boolean)[0] || ''
    }
    if (host.endsWith('youtube.com')) {
      if (parsed.pathname === '/watch') {
        return parsed.searchParams.get('v') || ''
      }
      const parts = parsed.pathname.split('/').filter(Boolean)
      const knownPrefixes = ['shorts', 'embed', 'live']
      const prefixIndex = parts.findIndex((part) => knownPrefixes.includes(part))
      if (prefixIndex >= 0 && parts[prefixIndex + 1]) {
        return parts[prefixIndex + 1]
      }
    }
  } catch {
    return ''
  }
  return ''
}

const youtubeThumbFromUrl = (urlValue) => {
  const videoId = extractYoutubeId(urlValue).trim()
  if (!videoId || !/^[a-zA-Z0-9_-]{6,}$/.test(videoId)) {
    return ''
  }
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
}

const renderTextWithLinks = (text, keyPrefix) => {
  const chunks = String(text || '').split(URL_REGEX)
  return chunks.map((chunk, index) => {
    if (/^https?:\/\/[^\s)]+$/i.test(chunk)) {
      return (
        <a key={`${keyPrefix}-u-${index}`} href={chunk} target="_blank" rel="noopener noreferrer">
          {chunk}
        </a>
      )
    }
    return <span key={`${keyPrefix}-t-${index}`}>{chunk}</span>
  })
}

const formatInline = (text) => {
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return segments.map((segment, index) => {
    if (segment.startsWith('**') && segment.endsWith('**')) {
      return <strong key={`s-${index}`}>{segment.slice(2, -2)}</strong>
    }

    if (segment.startsWith('`') && segment.endsWith('`')) {
      return <code key={`c-${index}`}>{segment.slice(1, -1)}</code>
    }

    return <span key={`t-${index}`}>{renderTextWithLinks(segment, `lnk-${index}`)}</span>
  })
}

const normalizeAssistantText = (rawText) => {
  const clean = (rawText || '').trim()
  return clean.replace(/^[\s:*"]+/u, '').trim()
}

const parseSseEventBlock = (rawBlock) => {
  const lines = String(rawBlock || '').split('\n')
  let event = 'message'
  const dataLines = []

  lines.forEach((line) => {
    if (!line || line.startsWith(':')) return
    if (line.startsWith('event:')) {
      event = line.slice(6).trim().toLowerCase() || 'message'
      return
    }
    if (line.startsWith('data:')) {
      let value = line.slice(5)
      if (value.startsWith(' ')) {
        value = value.slice(1)
      }
      dataLines.push(value)
    }
  })

  const rawData = dataLines.join('\n')
  if (!rawData) {
    return { event, data: '' }
  }

  try {
    return { event, data: JSON.parse(rawData) }
  } catch {
    return { event, data: rawData }
  }
}

const normalizeStreamEventName = (eventName, payload) => {
  const normalizedEvent = String(eventName || '').toLowerCase()
  if (KNOWN_STREAM_EVENTS.has(normalizedEvent)) {
    return normalizedEvent
  }

  if (payload && typeof payload === 'object') {
    const hintedEvent = String(payload.event || payload.type || '').toLowerCase()
    if (KNOWN_STREAM_EVENTS.has(hintedEvent)) {
      return hintedEvent
    }
  }

  return normalizedEvent || 'message'
}

const extractStreamText = (payload) => {
  if (typeof payload === 'string') {
    return payload
  }
  if (!payload || typeof payload !== 'object') {
    return ''
  }

  const textCandidates = [payload.text, payload.chunk, payload.delta, payload.content, payload.response]
  const firstText = textCandidates.find((value) => typeof value === 'string')
  return firstText || ''
}

const extractStreamError = (payload) => {
  if (typeof payload === 'string') {
    return payload.trim()
  }
  if (!payload || typeof payload !== 'object') {
    return ''
  }

  const errorCandidates = [payload.error, payload.message, payload.detail]
  const firstError = errorCandidates.find((value) => typeof value === 'string' && value.trim())
  return firstError ? firstError.trim() : ''
}

const SOURCE_I18N = {
  fr: { title: 'Sources', newTab: 'Nouvel onglet', unavailable: 'PDF non disponible pour le moment', externalPdf: 'Ce PDF est hébergé sur un site externe. Cliquez ci-dessous pour le consulter.', openPdf: 'Ouvrir le PDF' },
  en: { title: 'Sources', newTab: 'New tab', unavailable: 'PDF not available at the moment', externalPdf: 'This PDF is hosted externally. Click below to view it.', openPdf: 'Open PDF' },
  ko: { title: '\uCD9C\uCC98', newTab: '\uC0C8 \uD0ED', unavailable: 'PDF\uB97C \uD604\uC7AC \uC0AC\uC6A9\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4', externalPdf: '\uC774 PDF\uB294 \uC678\uBD80 \uC0AC\uC774\uD2B8\uC5D0 \uD638\uC2A4\uD305\uB418\uC5B4 \uC788\uC2B5\uB2C8\uB2E4.', openPdf: 'PDF \uC5F4\uAE30' },
}

function SourcesList({ sources, lang }) {
  const [proofIndex, setProofIndex] = useState(null)
  const [pdfError, setPdfError] = useState(false)
  const proofSrc = proofIndex !== null ? sources[proofIndex] : null
  const i = SOURCE_I18N[lang] || SOURCE_I18N.fr

  const openProof = (index) => {
    setPdfError(false)
    setProofIndex(index)
  }

  return (
    <div className="bot-sources-section">
      <h4 className="bot-heading">{i.title}</h4>
      <ul className="bot-sources-list">
        {sources.map((src, idx) => (
          <li key={`src-${idx}`} className={`bot-source-item bot-source-${src.kind}`}>
            {src.kind === 'manual' && src.slug ? (
              <button type="button" className="bot-source-link" onClick={() => openProof(idx)}>
                {src.display || `${src.label}, page ${src.page}`}
              </button>
            ) : src.kind === 'web' && src.url ? (() => {
              const safeHref = (src.url && /^https?:\/\//.test(src.url)) ? src.url : '#'
              return (
                <a href={safeHref} target="_blank" rel="noopener noreferrer" className="bot-source-link">
                  {src.display || src.label}
                </a>
              )
            })() : (
              <span>{src.display || src.label}</span>
            )}
          </li>
        ))}
      </ul>
      {proofSrc && (proofSrc.slug || proofSrc.pdf_url) && createPortal(
        <div className="proof-overlay" onClick={() => setProofIndex(null)}>
          <div className="proof-popup proof-popup--pdf" onClick={(e) => e.stopPropagation()}>
            <div className="proof-header">
              <span className="proof-label">{proofSrc.label}, page {proofSrc.page}</span>
              {!pdfError && (
                <a
                  href={proofSrc.pdf_url
                    ? `${proofSrc.pdf_url}#page=${String(proofSrc.page).split('-')[0]}`
                    : `${API_URL}/guides/${proofSrc.slug}/pdf#page=${String(proofSrc.page).split('-')[0]}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="proof-newtab"
                >
                  {i.newTab}
                </a>
              )}
              <button type="button" className="proof-close" onClick={() => setProofIndex(null)}>&times;</button>
            </div>
            {pdfError ? (
              <div className="proof-unavailable">
                <p>{i.unavailable}</p>
                {proofSrc.excerpt && <p className="proof-excerpt">{proofSrc.excerpt}</p>}
              </div>
            ) : proofSrc.pdf_url ? (
              /* External PDF (inspirauto.fr etc.) — can't embed cross-origin, open in new tab */
              <div className="proof-external">
                <p className="proof-external__text">
                  {i.externalPdf || 'Ce PDF est hébergé sur un site externe. Cliquez ci-dessous pour le consulter.'}
                </p>
                <a
                  href={`${proofSrc.pdf_url}#page=${String(proofSrc.page).split('-')[0]}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="proof-external__btn"
                >
                  {i.openPdf || 'Ouvrir le PDF'}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
                {proofSrc.excerpt && <p className="proof-excerpt">{proofSrc.excerpt}</p>}
              </div>
            ) : (
              /* Local PDF — safe to embed */
              <iframe
                className="proof-iframe"
                src={`${API_URL}/guides/${proofSrc.slug}/pdf#page=${String(proofSrc.page).split('-')[0]}`}
                title={`${proofSrc.label} - page ${proofSrc.page}`}
                onError={() => setPdfError(true)}
                onLoad={(e) => {
                  try {
                    const doc = e.target.contentDocument
                    if (doc && doc.body && doc.body.textContent.includes('PDF not found')) {
                      setPdfError(true)
                    }
                  } catch { /* cross-origin, PDF loaded fine */ }
                }}
              />
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

const RichBotMessage = memo(function RichBotMessage({ text, lang = 'fr', video, confidence, sources }) {
  const lines = normalizeAssistantText(text).replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let listBuffer = null
  let pendingVideoLabel = ''
  const videoUi = VIDEO_UI[lang] || VIDEO_UI.fr

  const flushList = () => {
    if (listBuffer && listBuffer.items.length > 0) {
      blocks.push(listBuffer)
    }
    listBuffer = null
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()

    if (!line) {
      flushList()
      pendingVideoLabel = ''
      return
    }

    if (VIDEO_LABEL_REGEX.test(line)) {
      flushList()
      pendingVideoLabel = line.replace(/:\s*$/, '')
      return
    }

    const youtubeMatch = line.match(YOUTUBE_URL_REGEX)
    if (youtubeMatch) {
      flushList()
      const url = sanitizeUrl(youtubeMatch[1])
      let title = line
        .replace(/^[-*]\s+/, '')
        .replace(youtubeMatch[1], '')
        .replace(/[:\s-]+$/, '')
        .trim()

      if (!title && pendingVideoLabel) {
        title = pendingVideoLabel.replace(/:\s*$/, '').trim()
      }
      if (!title || VIDEO_LABEL_REGEX.test(title)) {
        title = 'YouTube'
      }

      blocks.push({
        type: 'video',
        content: {
          title,
          url,
          thumb: youtubeThumbFromUrl(url),
        },
      })
      pendingVideoLabel = ''
      return
    }

    const headingMatch = line.match(/^#{1,3}\s+(.+)/)
    if (headingMatch) {
      flushList()
      blocks.push({ type: 'heading', content: headingMatch[1] })
      return
    }

    if (line.length <= 50 && line.endsWith(':') && !line.startsWith('- ') && !/[.!?,;]/.test(line.slice(0, -1))) {
      flushList()
      blocks.push({ type: 'heading', content: line.slice(0, -1) })
      pendingVideoLabel = ''
      return
    }

    const bulletMatch = line.match(/^[-*]\s+(.+)/)
    const numberedMatch = line.match(/^\d+\.\s+(.+)/)
    if (bulletMatch || numberedMatch) {
      const item = bulletMatch ? bulletMatch[1] : numberedMatch[1]
      const listType = numberedMatch ? 'ordered' : 'unordered'

      if (!listBuffer || listBuffer.listType !== listType) {
        flushList()
        listBuffer = { type: 'list', listType, items: [] }
      }

      listBuffer.items.push(item)
      return
    }

    flushList()
    blocks.push({ type: 'paragraph', content: line })
    pendingVideoLabel = ''
  })

  flushList()

  return (
    <div className="bot-rich-message">
      {confidence && (
        <span className={`confidence-badge confidence-${confidence}`}>
          {{ fr: { high: 'Fiabilite elevee', medium: 'Fiabilite moyenne', low: 'Fiabilite limitee' },
             en: { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' },
             ko: { high: '\uB192\uC740 \uC2E0\uB8B0\uB3C4', medium: '\uC911\uAC04 \uC2E0\uB8B0\uB3C4', low: '\uB0AE\uC740 \uC2E0\uB8B0\uB3C4' },
          }[lang]?.[confidence] || confidence}
        </span>
      )}
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          return (
            <h4 className="bot-heading" key={`h-${index}`}>
              {formatInline(block.content)}
            </h4>
          )
        }

        if (block.type === 'video') {
          return (
            <div className="bot-video-card" key={`v-${index}`}>
              <a className="bot-video-thumb" href={block.content.url} target="_blank" rel="noopener noreferrer">
                {block.content.thumb ? (
                  <img src={block.content.thumb} alt={block.content.title} loading="lazy" />
                ) : (
                  <div className="bot-video-thumb-fallback">
                    <span>YouTube</span>
                  </div>
                )}
                <span className="bot-video-play-icon" aria-hidden="true">&#9654;</span>
                <span className="bot-video-badge">{videoUi.badge}</span>
              </a>
              <div className="bot-video-content">
                <p className="bot-video-title">{block.content.title}</p>
              </div>
              <a className="bot-video-action" href={block.content.url} target="_blank" rel="noreferrer">
                {videoUi.action}
              </a>
            </div>
          )
        }

        if (block.type === 'list') {
          if (block.listType === 'ordered') {
            return (
              <ol className="bot-list" key={`l-${index}`}>
                {block.items.map((item, i) => (
                  <li key={`${i}-${item.slice(0, 30)}`}>{formatInline(item)}</li>
                ))}
              </ol>
            )
          }

          return (
            <ul className="bot-list" key={`l-${index}`}>
              {block.items.map((item) => (
                <li key={item}>{formatInline(item)}</li>
              ))}
            </ul>
          )
        }

        return (
          <p className="bot-paragraph" key={`p-${index}`}>
            {formatInline(block.content)}
          </p>
        )
      })}
      {sources && sources.length > 0 && (
        <SourcesList sources={sources} lang={lang} />
      )}
      {video && video.url && (
        <div className="bot-video-card" key="stream-video">
          <a className="bot-video-thumb" href={video.url} target="_blank" rel="noopener noreferrer">
            {video.thumb ? (
              <img src={video.thumb} alt={video.title} loading="lazy" />
            ) : (
              <div className="bot-video-thumb-fallback"><span>YouTube</span></div>
            )}
            <span className="bot-video-play-icon" aria-hidden="true">&#9654;</span>
            <span className="bot-video-badge">{videoUi.badge}</span>
          </a>
          <div className="bot-video-content">
            <p className="bot-video-title">{video.title}</p>
          </div>
          <a className="bot-video-action" href={video.url} target="_blank" rel="noreferrer">
            {videoUi.action}
          </a>
        </div>
      )}
    </div>
  )
})

function ChatPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [lang, setLang] = useAppLanguage()
  const [guide, setGuide] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')
  const [errorKey, setErrorKey] = useState('')
  const [langOpen, setLangOpen] = useState(false)
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [pendingExitPath, setPendingExitPath] = useState('')
  const [isCompactNav, setIsCompactNav] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= COMPACT_MENU_BREAKPOINT : false,
  )
  const [sessionId] = useState(() => generateSessionId())
  const [assistantAliases] = useState(() => ({
    fr: generateAssistantAlias('fr'),
    en: generateAssistantAlias('en'),
    ko: generateAssistantAlias('ko'),
  }))
  const chatContainerRef = useRef(null)
  const langDropdownRef = useRef(null)
  const tokenFlushTimerRef = useRef(null)
  const inputRef = useRef(null)
  const chunkBufferRef = useRef('')
  const drainTimerRef = useRef(null)
  const streamDoneRef = useRef(false)
  const userScrolledUpRef = useRef(false)
  const t = UI_TEXT[lang] || UI_TEXT.fr
  const toastCopy = TOAST_COPY[lang] || TOAST_COPY.en
  const coverageLabel = t.chat.coverageLabel || '{coverage}'
  const exitConfirmTitle = t.chat.exitConfirmTitle || 'End this chat?'
  const exitConfirmText = t.chat.exitConfirmText || 'Are you sure you want to leave this conversation?'
  const exitConfirmCancel = t.chat.exitConfirmCancel || 'Cancel'
  const exitConfirmAccept = t.chat.exitConfirmAccept || 'Leave'
  const exitConfirmKicker = lang === 'fr' ? 'TERMINER LA LIAISON ?' : lang === 'ko' ? '링크를 종료하시겠습니까?' : 'TERMINATE NEURAL LINK?'
  const exitNodeLabel = lang === 'fr' ? 'NOEUD.ACTIF' : lang === 'ko' ? '활성 노드' : 'ACTIVE.NODE'
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]
  const terminalSystemLabel = assistantAliases[lang] || assistantAliases.en
  const terminalProtocolLabel = 'PROTOCOL_SECURE_LINE'
  const executeLabel = lang === 'fr' ? 'EXECUTER' : lang === 'ko' ? '\uC2E4\uD589' : 'EXECUTE'

  const quickQuestions = useMemo(() => {
    return (t.chat.quickQuestions || []).map((text, index) => ({
      text,
      icon: QUICK_ICONS[index % QUICK_ICONS.length],
    }))
  }, [t])
  const isIntroMode = messages.length === 0 && !isLoading

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
    const loadGuide = async () => {
      try {
        const res = await fetch(`${API_URL}/guides/${slug}`)
        const data = await res.json()
        if (!data.success) {
          setErrorKey('guideNotFound')
          return
        }
        setGuide(data.guide)
        try {
          localStorage.setItem('mechora_last_vehicle', JSON.stringify({
            slug: slug,
            name: data.guide.name,
            brand: data.guide.brand || '',
            segment: data.guide.segment || '',
          }))
        } catch {}
      } catch {
        setErrorKey('guideLoadError')
      }
    }

    void loadGuide()
  }, [slug])

  /* -- detect user scrolling up (don't force scroll during streaming) -- */
  useEffect(() => {
    const el = chatContainerRef.current
    if (!el) return
    const handleScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      userScrolledUpRef.current = distanceFromBottom > 120
    }
    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => el.removeEventListener('scroll', handleScroll)
  }, [])

  /* -- auto-scroll only if user is near bottom ------------------------- */
  useEffect(() => {
    if (userScrolledUpRef.current) return
    const frame = requestAnimationFrame(() => {
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTo({
          top: chatContainerRef.current.scrollHeight,
          behavior: isStreaming ? 'auto' : 'smooth',
        })
      }
    })
    return () => cancelAnimationFrame(frame)
  }, [messages, isLoading, isStreaming])

  /* -- reset scroll flag when user sends a new message ----------------- */
  useEffect(() => {
    if (isLoading) {
      userScrolledUpRef.current = false
    }
  }, [isLoading])

  useEffect(() => {
    if (!langOpen) return undefined

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
    if (!showExitConfirm) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setShowExitConfirm(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [showExitConfirm])

  const closeExitConfirm = () => {
    setShowExitConfirm(false)
    setPendingExitPath('')
  }

  const openExitConfirm = (targetPath = '/') => {
    setLangOpen(false)
    setNavMenuOpen(false)
    setPendingExitPath(targetPath)
    setShowExitConfirm(true)
  }

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
    setNavMenuOpen(false)
  }

  const confirmExitChat = () => {
    const targetPath = pendingExitPath || '/'
    closeExitConfirm()
    showToast({ type: 'success', message: toastCopy.redirecting })
    navigate(targetPath)
  }

  useEffect(() => {
    return () => {
      if (tokenFlushTimerRef.current) {
        window.clearInterval(tokenFlushTimerRef.current)
      }
      if (drainTimerRef.current) {
        window.clearInterval(drainTimerRef.current)
      }
    }
  }, [])

  const streamBotMessage = (fullText) =>
    new Promise((resolve) => {
      if (drainTimerRef.current) {
        window.clearInterval(drainTimerRef.current)
        drainTimerRef.current = null
      }
      chunkBufferRef.current = ''
      streamDoneRef.current = false

      const safeText = normalizeAssistantText(fullText || '') || t.chat.unavailable
      const chars = Array.from(safeText)

      setMessages((previous) => {
        const lastMessage = previous[previous.length - 1]
        if (lastMessage && lastMessage.type === 'bot' && !lastMessage.content) {
          return previous
        }
        return [...previous, { type: 'bot', content: '' }]
      })
      setIsStreaming(true)

      if (chars.length === 0) {
        setIsStreaming(false)
        resolve()
        return
      }

      const step = chars.length > 1400 ? 40 : chars.length > 800 ? 25 : chars.length > 420 ? 15 : 10
      const intervalMs = chars.length > 900 ? 12 : 16
      let index = 0

      if (tokenFlushTimerRef.current) {
        window.clearInterval(tokenFlushTimerRef.current)
      }

      tokenFlushTimerRef.current = window.setInterval(() => {
        index = Math.min(chars.length, index + step)
        const nextContent = chars.slice(0, index).join('')

        setMessages((previous) => {
          if (previous.length === 0) return previous
          const updated = [...previous]
          const lastMessage = updated[updated.length - 1]

          if (!lastMessage || lastMessage.type !== 'bot') {
            updated.push({ type: 'bot', content: nextContent })
            return updated
          }

          updated[updated.length - 1] = { ...lastMessage, content: nextContent }
          return updated
        })

        if (index >= chars.length) {
          if (tokenFlushTimerRef.current) {
            window.clearInterval(tokenFlushTimerRef.current)
            tokenFlushTimerRef.current = null
          }
          setIsStreaming(false)
          resolve()
        }
      }, intervalMs)
    })

  const drainTick = () => {
    const buf = chunkBufferRef.current
    if (!buf) {
      if (streamDoneRef.current) {
        window.clearInterval(drainTimerRef.current)
        drainTimerRef.current = null
        streamDoneRef.current = false
        setIsStreaming(false)
      }
      return
    }
    const step = buf.length > 800 ? 12 : buf.length > 300 ? 6 : buf.length > 80 ? 3 : 2
    const piece = buf.slice(0, step)
    chunkBufferRef.current = buf.slice(step)
    setMessages((prev) => {
      if (!prev.length) return [{ type: 'bot', content: piece }]
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (!last || last.type !== 'bot') {
        return [...prev, { type: 'bot', content: piece }]
      }
      updated[updated.length - 1] = { ...last, content: (last.content || '') + piece }
      return updated
    })
  }

  const startDrain = () => {
    if (drainTimerRef.current) return
    drainTimerRef.current = window.setInterval(drainTick, 25)
  }

  const appendBotChunk = (chunkText) => {
    const nextChunk = String(chunkText || '')
    if (!nextChunk) return
    chunkBufferRef.current += nextChunk
    startDrain()
  }


  const requestChatJson = async ({ text, signal }) => {
    const response = await fetch(`${API_URL}/guides/${slug}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, lang, session_id: sessionId }),
      signal,
    })

    const data = await response.json()
    if (data.success) {
      return data.response || ''
    }

    return (data.error || '').trim() || t.chat.unavailable
  }

  const consumeChatStream = async ({ text, signal }) => {
    let hasChunkContent = false

    const response = await fetch(`${API_URL}/guides/${slug}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ message: text, lang, session_id: sessionId }),
      signal,
    })

    if (!response.ok) {
      const streamError = new Error(`stream endpoint unavailable (${response.status})`)
      streamError.allowFallback = true
      throw streamError
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase()
    if (!contentType.includes('text/event-stream') || !response.body) {
      const streamError = new Error('invalid stream response')
      streamError.allowFallback = true
      throw streamError
    }

    const ensureStreamingMessage = () => {
      setIsStreaming(true)
      setMessages((previous) => {
        const lastMessage = previous[previous.length - 1]
        if (lastMessage && lastMessage.type === 'bot') {
          return previous
        }
        return [...previous, { type: 'bot', content: '' }]
      })
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const handleStreamEvent = ({ event, data }) => {
      const eventName = normalizeStreamEventName(event, data)

      if (eventName === 'start') {
        // Don't create the bot message yet — wait for first chunk
        return
      }

      if (eventName === 'status') {
        const step = (data && typeof data === 'object') ? data.step : ''
        setStreamStatus(step || '')
        return
      }

      if (eventName === 'chunk') {
        const chunkText = extractStreamText(data)
        if (!chunkText) return
        ensureStreamingMessage()
        hasChunkContent = true
        appendBotChunk(chunkText)
        return
      }

      if (eventName === 'end') {
        setStreamStatus('')
        const confidence = (data && typeof data === 'object') ? (data.confidence || '') : ''
        if (confidence) {
          setMessages((prev) => {
            if (!prev.length) return prev
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.type === 'bot') {
              updated[updated.length - 1] = { ...last, confidence }
            }
            return updated
          })
        }
        return
      }

      if (eventName === 'sources_start') {
        return
      }

      if (eventName === 'source_item') {
        const src = (data && typeof data === 'object') ? data.source : null
        if (src) {
          setMessages((prev) => {
            if (!prev.length) return prev
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.type === 'bot') {
              const existing = last.sources || []
              updated[updated.length - 1] = { ...last, sources: [...existing, src] }
            }
            return updated
          })
        }
        return
      }

      if (eventName === 'sources_end') {
        return
      }

      if (eventName === 'video_result') {
        const videoData = (data && typeof data === 'object') ? data : {}
        const url = String(videoData.url || '').trim()
        if (!url || !/^https:\/\//.test(url)) return
        setMessages((previous) => {
          if (previous.length === 0) return previous
          const updated = [...previous]
          const lastMessage = updated[updated.length - 1]
          if (lastMessage && lastMessage.type === 'bot') {
            updated[updated.length - 1] = {
              ...lastMessage,
              video: {
                title: String(videoData.title || 'YouTube'),
                url,
                thumb: String(videoData.thumbnail || '') || youtubeThumbFromUrl(url),
              },
            }
          }
          return updated
        })
        return
      }

      if (eventName === 'video_none') {
        return
      }

      if (eventName === 'error') {
        const message = extractStreamError(data) || t.chat.serverUnavailable
        const streamError = new Error(message)
        streamError.allowFallback = !hasChunkContent
        streamError.hasChunkContent = hasChunkContent
        streamError.streamErrorMessage = message
        throw streamError
      }

      const fallbackChunk = extractStreamText(data)
      if (!fallbackChunk) return
      ensureStreamingMessage()
      hasChunkContent = true
      appendBotChunk(fallbackChunk)
    }

    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')
        let separatorIndex = buffer.indexOf('\n\n')

        while (separatorIndex >= 0) {
          const rawBlock = buffer.slice(0, separatorIndex)
          buffer = buffer.slice(separatorIndex + 2)

          if (rawBlock.trim()) {
            handleStreamEvent(parseSseEventBlock(rawBlock))
          }

          separatorIndex = buffer.indexOf('\n\n')
        }
      }

      buffer += decoder.decode().replace(/\r/g, '')
      if (buffer.trim()) {
        handleStreamEvent(parseSseEventBlock(buffer))
      }

      streamDoneRef.current = true
      startDrain()

      if (!hasChunkContent) {
        const streamError = new Error('empty stream response')
        streamError.allowFallback = true
        streamError.hasChunkContent = false
        throw streamError
      }
    } finally {
      reader.releaseLock()
      // isStreaming is set to false by the drain when buffer is empty
    }
  }

  const sendMessage = async (messageText) => {
    const text = (messageText || input).trim()
    if (!text || isLoading || isStreaming) return
    setStreamStatus('')

    // Cancel any pending drain from a previous stream
    if (drainTimerRef.current) {
      window.clearInterval(drainTimerRef.current)
      drainTimerRef.current = null
    }
    chunkBufferRef.current = ''
    streamDoneRef.current = false

    setMessages((previous) => [...previous, { type: 'user', content: text }])
    setInput('')
    setIsLoading(true)
    setLangOpen(false)
    let timeoutId

    try {
      const controller = new AbortController()
      timeoutId = window.setTimeout(() => controller.abort(), CHAT_REQUEST_TIMEOUT_MS)
      try {
        await consumeChatStream({ text, signal: controller.signal })
      } catch (streamError) {
        if (streamError?.name === 'AbortError') {
          throw streamError
        }

        if (streamError?.allowFallback) {
          const fallbackResponse = await requestChatJson({ text, signal: controller.signal })
          await streamBotMessage(fallbackResponse)
          return
        }

        const streamErrorText = streamError?.streamErrorMessage || t.chat.serverUnavailable
        if (streamError?.hasChunkContent) {
          appendBotChunk(`\n\n${streamErrorText}`)
          streamDoneRef.current = true
          startDrain()
        } else {
          await streamBotMessage(streamErrorText)
        }
      }
    } catch (error) {
      if (error?.name === 'AbortError') {
        await streamBotMessage(t.chat.serverUnavailable)
        return
      }
      await streamBotMessage(t.chat.serverUnavailable)
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId)
      }
      setIsLoading(false)
      if (!drainTimerRef.current) {
        setIsStreaming(false)
      }
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  if (errorKey) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--error)" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <h2>{t.chat[errorKey] || t.chat.guideLoadError}</h2>
          <button className="btn-secondary" onClick={() => navigate('/guides')}>{t.chat.guides}</button>
        </div>
      </Motion.div>
    )
  }

  if (!guide) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <div className="loader-ring" />
          <p>{t.chat.loadingChat}</p>
        </div>
      </Motion.div>
    )
  }

  return (
    <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <div className="chat-bg-image" />
      <header className="chat-header">
        {isCompactNav ? (
          <div className="chat-brand chat-brand-static" aria-hidden>
            <img src="/logo-mechora.png" alt="Mechora" width="122" height="36" loading="lazy" />
            <div className="chat-brand-copy">
              <span className="chat-brand-system">{terminalSystemLabel}</span>
              <p>{guide.name}</p>
              {guide.coverage_note ? (
                <small className="chat-brand-note">{formatText(coverageLabel, { coverage: guide.coverage_note })}</small>
              ) : null}
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="chat-brand chat-brand-link"
            onClick={() => openExitConfirm('/')}
            aria-label={(UI_TEXT[lang] || UI_TEXT.fr).guides.home}
          >
            <img src="/logo-mechora.png" alt="Mechora" width="122" height="36" loading="lazy" />
            <div className="chat-brand-copy">
              <span className="chat-brand-system">{terminalSystemLabel}</span>
              <p>{guide.name}</p>
              {guide.coverage_note ? (
                <small className="chat-brand-note">{formatText(coverageLabel, { coverage: guide.coverage_note })}</small>
              ) : null}
            </div>
          </button>
        )}

        <div className="chat-header-right">
          <span className="chat-header-protocol">{terminalProtocolLabel}</span>
          {isCompactNav ? (
            <button
              type="button"
              className="chat-burger-trigger"
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
            <div className="lang-switcher" ref={langDropdownRef}>
              <Motion.button
                type="button"
                className="lang-toggle"
                onClick={() => setLangOpen((prev) => !prev)}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.96 }}
              >
                <img
                  className="chat-lang-flag"
                  src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.en}
                  alt={`${currentLang?.label || 'EN'} flag`}
                />
                {currentLang?.label}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </Motion.button>

              <AnimatePresence>
                {langOpen && (
                  <Motion.div
                    className="chat-lang-dropdown"
                    initial={{ opacity: 0, y: -6, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.96 }}
                    transition={{ duration: 0.18 }}
                  >
                    {LANGUAGES.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        className={`chat-lang-option${entry.code === lang ? ' chat-lang-option--active' : ''}`}
                        onClick={() => handleLangSelect(entry.code)}
                      >
                        <img
                          className="chat-lang-flag"
                          src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                          alt={`${entry.label} flag`}
                        />
                        <span>{entry.label}</span>
                      </button>
                    ))}
                  </Motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </header>

      <AnimatePresence>
        {isCompactNav && navMenuOpen && (
          <Motion.div
            className="chat-nav-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setNavMenuOpen(false)}
          >
            <Motion.div
              className="chat-nav-menu"
              initial={{ opacity: 0, y: -10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              onClick={(event) => event.stopPropagation()}
            >
              <button type="button" className="chat-nav-home" onClick={() => openExitConfirm('/')}>
                {(UI_TEXT[lang] || UI_TEXT.fr).guides.home}
              </button>
              <div className="chat-nav-languages">
                {LANGUAGES.map((entry) => (
                  <button
                    key={entry.code}
                    type="button"
                    className={`chat-nav-lang-option${entry.code === lang ? ' chat-nav-lang-option--active' : ''}`}
                    onClick={() => handleLangSelect(entry.code)}
                  >
                    <img
                      className="chat-lang-flag"
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

      <main className="chat-body" ref={chatContainerRef}>
          {!isIntroMode && (
            <div className="chat-vehicle-banner">
              <p>{terminalSystemLabel}</p>
              <h1>{guide.name}</h1>
            </div>
          )}

          <div className={`chat-messages${isIntroMode ? ' chat-messages--empty' : ''}`}>
            <AnimatePresence>
              {messages.length === 0 && !isLoading && (
                <Motion.div
                  className="chat-intro-card"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.45 }}
                >
                  <h2>{t.chat.askFirst}</h2>
                  <p>{formatText(t.chat.askFirstDesc, { vehicle: guide.name })}</p>

                  <div className="chat-suggestions chat-suggestions--inline">
                    {quickQuestions.map((item, index) => (
                      <Motion.button
                        key={item.text}
                        className="suggestion-pill"
                        onClick={() => sendMessage(item.text)}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.22 + (index * 0.08) }}
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        <img src={item.icon} alt="" loading="lazy" />
                        <span>{item.text}</span>
                      </Motion.button>
                    ))}
                  </div>
                </Motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence initial={false}>
              {messages.map((msg, index) => {
                const isLastBotStreaming = isStreaming && msg.type === 'bot' && index === messages.length - 1
                return (
                  <Motion.div
                    key={`${msg.type}-${index}`}
                    className={`msg ${msg.type}`}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28 }}
                  >
                    <div className="msg-avatar">
                      <span className="msg-avatar-tag">{msg.type === 'user' ? 'USR' : 'AI'}</span>
                    </div>

                    <div className="msg-bubble">
                      {msg.type === 'bot' ? (
                        <RichBotMessage
                          text={msg.content}
                          lang={lang}
                          video={isLastBotStreaming ? null : msg.video}
                          confidence={isLastBotStreaming ? null : msg.confidence}
                          sources={isLastBotStreaming ? null : msg.sources}
                        />
                      ) : msg.content}
                    </div>
                  </Motion.div>
                )
              })}
            </AnimatePresence>

            <AnimatePresence>
              {isLoading && !isStreaming && (
                <Motion.div
                  className="msg bot"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="msg-avatar">
                    <span className="msg-avatar-tag">AI</span>
                  </div>
                  <div className="msg-bubble msg-typing">
                    <span /><span /><span />
                    {streamStatus && (
                      <p className="typing-status">{{ fr: {
                        manual_search: 'Recherche dans le manuel...', web_search: 'Recherche sur le web...', generating: 'Generation en cours...',
                      }, en: {
                        manual_search: 'Searching manual...', web_search: 'Searching the web...', generating: 'Generating response...',
                      }, ko: {
                        manual_search: '\uB9E4\uB274\uC5BC \uAC80\uC0C9 \uC911...', web_search: '\uC6F9 \uAC80\uC0C9 \uC911...', generating: '\uC751\uB2F5 \uC0DD\uC131 \uC911...',
                      }}[lang]?.[streamStatus] || ''}</p>
                    )}
                  </div>
                </Motion.div>
              )}
            </AnimatePresence>
          </div>
      </main>

      <footer className="chat-footer">
        <div className="chat-input-wrap">
          <div className="chat-input-row">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`> ${formatText(t.chat.placeholder, { vehicle: guide.name })}`}
              disabled={isLoading || isStreaming}
              maxLength={MAX_INPUT_LENGTH}
              aria-label={formatText(t.chat.placeholder, { vehicle: guide.name })}
            />
            <Motion.button
              className="chat-send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || isLoading || isStreaming}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
              title={t.chat.send}
              aria-label={t.chat.send}
            >
              {executeLabel}
            </Motion.button>
          </div>
        </div>
      </footer>

      <AnimatePresence>
        {showExitConfirm && (
          <Motion.div
            className="chat-exit-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeExitConfirm}
          >
            <Motion.div
              className="chat-exit-popup"
              initial={{ opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="chat-exit-top">
                <span className="chat-exit-sigil" aria-hidden>{'\u25CE'}</span>
                <p className="chat-exit-kicker">{exitConfirmKicker}</p>
                <h2>{exitConfirmTitle}</h2>
                <p className="chat-exit-text">{exitConfirmText}</p>
              </div>

              <div className="chat-exit-actions">
                <button type="button" className="chat-exit-cancel" onClick={closeExitConfirm}>
                  {exitConfirmCancel}
                </button>
                <button type="button" className="chat-exit-accept" onClick={confirmExitChat}>
                  {exitConfirmAccept}
                </button>
              </div>

              <div className="chat-exit-foot">
                <span>SYS.ID: AURIS-V3</span>
                <span>{exitNodeLabel}: {guide.name}</span>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  )
}

export default ChatPage
