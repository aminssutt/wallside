import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import './ChatPage.css'
import navigationIcon from '../assets/icons/navigation.svg'
import infotainmentIcon from '../assets/icons/infotainment.svg'
import wrenchIcon from '../assets/icons/wrench.svg'
import dashboardIcon from '../assets/icons/dashboard.svg'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002/api'

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.35 } },
  exit: { opacity: 0, transition: { duration: 0.25 } },
}

const quickQuestions = [
  { text: 'Comment faire la vidange ?', icon: wrenchIcon },
  { text: "Quels sont les intervalles d'entretien ?", icon: dashboardIcon },
  { text: 'Ou se trouve le filtre a air ?', icon: navigationIcon },
]

const formatInline = (text) => {
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return segments.map((segment, index) => {
    if (segment.startsWith('**') && segment.endsWith('**')) {
      return <strong key={`s-${index}`}>{segment.slice(2, -2)}</strong>
    }

    if (segment.startsWith('`') && segment.endsWith('`')) {
      return <code key={`c-${index}`}>{segment.slice(1, -1)}</code>
    }

    return <span key={`t-${index}`}>{segment}</span>
  })
}

const normalizeAssistantText = (rawText) => {
  const clean = (rawText || '').trim()
  return clean
    .replace(/^📖\s*/, '')
    .replace(/^🌐\s*/i, '')
    .replace(/^💡\s*/i, '')
    .trim()
}

const limitAssistantText = (text, maxChars = 980) => {
  if (text.length <= maxChars) {
    return text
  }

  const clipped = text.slice(0, maxChars).trim()
  const safe = clipped.lastIndexOf(' ') > 50 ? clipped.slice(0, clipped.lastIndexOf(' ')) : clipped
  return `${safe}\n\n_Resume pour garder une reponse lisible._`
}

function RichBotMessage({ text }) {
  const lines = normalizeAssistantText(text).replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let listBuffer = null

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
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const chatContainerRef = useRef(null)
  const inputRef = useRef(null)

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
    const loadSession = async () => {
      try {
        const res = await fetch(`${API_URL}/session/${sessionId}/status`)
        const data = await res.json()
        if (!data.success) {
          setError('Session introuvable')
          return
        }

        if (data.session.status !== 'ready') {
          navigate(`/processing/${sessionId}`)
          return
        }

        setSession(data.session)
      } catch {
        setError('Impossible de charger la session')
      }
    }

    void loadSession()
  }, [sessionId, navigate])

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages, isLoading])

  const sendMessage = async (messageText) => {
    const text = (messageText || input).trim()
    if (!text || isLoading) return

    setMessages((previous) => [...previous, { type: 'user', content: text }])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/session/${sessionId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await response.json()

      if (data.success) {
        const cleaned = limitAssistantText(normalizeAssistantText(data.response || ''))
        setMessages((previous) => [...previous, { type: 'bot', content: cleaned }])
      } else {
        setMessages((previous) => [...previous, { type: 'bot', content: `### Erreur\n${data.error || 'Reponse indisponible'}` }])
      }
    } catch {
      setMessages((previous) => [...previous, { type: 'bot', content: '### Erreur\nConnexion serveur indisponible.' }])
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

  if (error) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--error)" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <h2>{error}</h2>
          <button className="btn-secondary" onClick={() => navigate('/')}>Retour accueil</button>
        </div>
      </Motion.div>
    )
  }

  if (!session) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <div className="loader-ring" />
          <p>Chargement du chat...</p>
        </div>
      </Motion.div>
    )
  }

  return (
    <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <header className="chat-header">
        <div className="chat-brand">
          <img src="/logo-84.webp" alt="CC" width="42" height="42" loading="lazy" />
          <div>
            <p>Car Chat : CC</p>
            <span>{session.vehicle_name}</span>
          </div>
        </div>

        <Motion.button
          type="button"
          className="chat-home-btn"
          onClick={() => navigate('/')}
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
        >
          Return home
        </Motion.button>
      </header>

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
              <h2>Ask your first question</h2>
              <p>
                Your assistant is ready for <strong>{session.vehicle_name}</strong>.
                Ask maintenance, warning lights, usage or specification questions.
              </p>

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
                  {msg.type === 'bot' ? <RichBotMessage text={msg.content} /> : msg.content}
                </div>
              </Motion.div>
            ))}
          </AnimatePresence>

          <AnimatePresence>
            {isLoading && (
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
            placeholder={`Question about ${session.vehicle_name}...`}
            disabled={isLoading}
          />
          <Motion.button
            className="chat-send-btn"
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.95 }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </Motion.button>
        </div>
      </footer>
    </Motion.div>
  )
}

export default ChatPage
