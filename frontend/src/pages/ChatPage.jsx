import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import { useToast } from '../toast'
import './ChatPage.css'
import wrenchIcon from '../assets/icons/wrench.svg'
import dashboardIcon from '../assets/icons/dashboard.svg'
import navigationIcon from '../assets/icons/navigation.svg'
import infotainmentIcon from '../assets/icons/infotainment.svg'

const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
}

const QUICK_ICONS = [wrenchIcon, dashboardIcon, navigationIcon]
const COMPACT_MENU_BREAKPOINT = 1024

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.35 } },
  exit: { opacity: 0, transition: { duration: 0.25 } },
}

const TOAST_COPY = {
  fr: {
    redirecting: 'Action validee. Redirection en cours...',
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
  fr: { badge: 'Video conseillee', action: 'Voir la video' },
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

const youtubeEmbedFromUrl = (urlValue) => {
  const videoId = extractYoutubeId(urlValue).trim()
  if (!videoId || !/^[a-zA-Z0-9_-]{6,}$/.test(videoId)) {
    return ''
  }
  return `https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1`
}

const renderTextWithLinks = (text, keyPrefix) => {
  const chunks = String(text || '').split(URL_REGEX)
  return chunks.map((chunk, index) => {
    if (/^https?:\/\/[^\s)]+$/i.test(chunk)) {
      return (
        <a key={`${keyPrefix}-u-${index}`} href={chunk} target="_blank" rel="noreferrer">
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
  return clean.replace(/^[^\p{L}\p{N}]+/u, '').trim()
}

function RichBotMessage({ text, lang = 'fr' }) {
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
          embed: youtubeEmbedFromUrl(url),
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

    if (line.length <= 70 && line.endsWith(':') && !line.startsWith('- ')) {
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
              <div className="bot-video-thumb">
                {block.content.embed ? (
                  <iframe
                    src={block.content.embed}
                    title={block.content.title}
                    loading="lazy"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                  />
                ) : block.content.thumb ? (
                  <img src={block.content.thumb} alt={block.content.title} loading="lazy" />
                ) : (
                  <div className="bot-video-thumb-fallback">
                    <span>YouTube</span>
                  </div>
                )}
                <span className="bot-video-badge">{videoUi.badge}</span>
              </div>
              <div className="bot-video-content">
                <p className="bot-video-title">{block.content.title}</p>
                <span className="bot-video-url">{block.content.url}</span>
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
                {block.items.map((item) => (
                  <li key={item}>{formatInline(item)}</li>
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
    </div>
  )
}

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
  const [errorKey, setErrorKey] = useState('')
  const [langOpen, setLangOpen] = useState(false)
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [pendingExitPath, setPendingExitPath] = useState('')
  const [isCompactNav, setIsCompactNav] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= COMPACT_MENU_BREAKPOINT : false,
  )
  const chatContainerRef = useRef(null)
  const langDropdownRef = useRef(null)
  const tokenFlushTimerRef = useRef(null)
  const inputRef = useRef(null)
  const t = UI_TEXT[lang] || UI_TEXT.fr
  const toastCopy = TOAST_COPY[lang] || TOAST_COPY.en
  const coverageLabel = t.chat.coverageLabel || '{coverage}'
  const exitConfirmTitle = t.chat.exitConfirmTitle || 'End this chat?'
  const exitConfirmText = t.chat.exitConfirmText || 'Are you sure you want to leave this conversation?'
  const exitConfirmCancel = t.chat.exitConfirmCancel || 'Cancel'
  const exitConfirmAccept = t.chat.exitConfirmAccept || 'Leave'
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]

  const quickQuestions = useMemo(() => {
    return (t.chat.quickQuestions || []).map((text, index) => ({
      text,
      icon: QUICK_ICONS[index % QUICK_ICONS.length],
    }))
  }, [t])

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
      } catch {
        setErrorKey('guideLoadError')
      }
    }

    void loadGuide()
  }, [slug])

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: isStreaming ? 'auto' : 'smooth',
      })
    }
  }, [messages, isLoading, isStreaming])

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

  const ensureBotMessage = (initialText = '') => {
      setMessages((previous) => {
        if (previous.length === 0 || previous[previous.length - 1]?.type !== 'bot') {
          return [...previous, { type: 'bot', content: initialText }]
        }
        return previous
      })
    }

  const appendToBotMessage = (chunk = '') => {
      if (!chunk) return
      setMessages((previous) => {
        if (previous.length === 0) return previous
        const updated = [...previous]
        const last = updated[updated.length - 1]
        if (!last || last.type !== 'bot') {
          updated.push({ type: 'bot', content: chunk })
          return updated
        }
        updated[updated.length - 1] = {
          ...last,
          content: `${last.content || ''}${chunk}`,
        }
        return updated
      })
    }

  const setBotMessage = (text = '') => {
      setMessages((previous) => {
        if (previous.length === 0) return previous
        const updated = [...previous]
        const last = updated[updated.length - 1]
        if (!last || last.type !== 'bot') {
          updated.push({ type: 'bot', content: text })
          return updated
        }
        updated[updated.length - 1] = { ...last, content: text }
        return updated
      })
    }

  useEffect(() => {
    return () => {
      if (tokenFlushTimerRef.current) {
        window.clearInterval(tokenFlushTimerRef.current)
      }
    }
  }, [])

  const streamBotMessage = (fullText) =>
    new Promise((resolve) => {
      const safeText = normalizeAssistantText(fullText || '') || t.chat.unavailable
      const chars = Array.from(safeText)

      setMessages((previous) => [...previous, { type: 'bot', content: '' }])
      setIsStreaming(true)

      if (chars.length === 0) {
        setIsStreaming(false)
        resolve()
        return
      }

      const step = chars.length > 1400 ? 20 : chars.length > 800 ? 14 : chars.length > 420 ? 10 : 7
      const intervalMs = chars.length > 900 ? 14 : 18
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

  const sendMessage = async (messageText) => {
    const text = (messageText || input).trim()
    if (!text || isLoading || isStreaming) return

    setMessages((previous) => [...previous, { type: 'user', content: text }])
    setInput('')
    setIsLoading(true)
    setLangOpen(false)

    try {
      const response = await fetch(`${API_URL}/guides/${slug}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, lang }),
      })
      const data = await response.json()

      if (data.success) {
        await streamBotMessage(data.response || '')
      } else {
        const fallback = (data.error || '').trim() || t.chat.unavailable
        await streamBotMessage(fallback)
      }
    } catch {
      await streamBotMessage(t.chat.serverUnavailable)
    } finally {
      setIsLoading(false)
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
            <img src="/logo top left.png" alt="CarChat" width="122" height="36" loading="lazy" />
            <div>
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
            <img src="/logo top left.png" alt="CarChat" width="122" height="36" loading="lazy" />
            <div>
              <p>{guide.name}</p>
              {guide.coverage_note ? (
                <small className="chat-brand-note">{formatText(coverageLabel, { coverage: guide.coverage_note })}</small>
              ) : null}
            </div>
          </button>
        )}

        <div className="chat-header-right">
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
        <AnimatePresence>
          {messages.length === 0 && !isLoading && (
            <Motion.div
              className="chat-welcome"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.45 }}
            >
              <div className="chat-welcome-icon">
                <img src={navigationIcon} alt="" loading="lazy" />
              </div>
              <h2>{t.chat.askFirst}</h2>
              <p>{formatText(t.chat.askFirstDesc, { vehicle: guide.name })}</p>

              <div className="chat-suggestions">
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

        <div className="chat-messages">
          <AnimatePresence initial={false}>
            {messages.map((msg, index) => (
              <Motion.div
                key={`${msg.type}-${index}`}
                className={`msg ${msg.type}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28 }}
              >
                <div className="msg-avatar">
                  {msg.type === 'user' ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  ) : (
                    <img src={infotainmentIcon} alt="" loading="lazy" />
                  )}
                </div>

                <div className="msg-bubble">
                  {msg.type === 'bot' ? <RichBotMessage text={msg.content} lang={lang} /> : msg.content}
                </div>
              </Motion.div>
            ))}
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
                  <img src={infotainmentIcon} alt="" loading="lazy" />
                </div>
                <div className="msg-bubble msg-typing">
                  <span /><span /><span />
                </div>
              </Motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      <footer className="chat-footer">
        <div className="chat-input-wrap">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={formatText(t.chat.placeholder, { vehicle: guide.name })}
            disabled={isLoading || isStreaming}
          />
          <Motion.button
            className="chat-send-btn"
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading || isStreaming}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.95 }}
            title={t.chat.send}
            aria-label={t.chat.send}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </Motion.button>
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
                <h2>{exitConfirmTitle}</h2>
                <p>{exitConfirmText}</p>
              </div>

              <div className="chat-exit-actions">
                <button type="button" className="chat-exit-cancel" onClick={closeExitConfirm}>
                  {exitConfirmCancel}
                </button>
                <button type="button" className="chat-exit-accept" onClick={confirmExitChat}>
                  {exitConfirmAccept}
                </button>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  )
}

export default ChatPage
