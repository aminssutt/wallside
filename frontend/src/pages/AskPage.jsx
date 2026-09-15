import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_URL } from '../api'
import { UI_TEXT, useAppLanguage } from '../i18n'
import './AskPage.css'

/**
 * Ask flow: the question comes first, the vehicle second — and only when it is needed.
 *
 * The backend decides on every message (POST /api/ask/decide) whether it can answer, must ask which
 * vehicle the user has, or has no manual for that brand. Once a vehicle is known the question is sent to
 * that vehicle's manual (POST /api/guides/<slug>/chat/stream), and the answer streams in with its pages.
 */

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
const norm = (value) => String(value || '')
  .normalize('NFKD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase()

function useGuides() {
  const [guides, setGuides] = useState([])
  const [error, setError] = useState(false)
  useEffect(() => {
    let alive = true
    fetch(`${API_URL}/guides`)
      .then((r) => r.json())
      .then((data) => { if (alive && data?.success) setGuides(data.guides || []) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [])
  return { guides, error }
}

function VehiclePicker({ guides, brand, query, onQuery, onPick, t }) {
  const matches = useMemo(() => {
    const q = norm(query)
    const list = guides.filter((g) => (brand ? norm(g.brand) === norm(brand) : true))
    const scoped = q ? list.filter((g) => norm(`${g.brand} ${g.name}`).includes(q)) : list
    return scoped.slice(0, 60)
  }, [guides, brand, query])

  return (
    <div className="picker">
      <input
        id="ask-vehicle-search"
        className="picker-search"
        type="search"
        autoComplete="off"
        value={query}
        placeholder={t.searchPlaceholder}
        onChange={(event) => onQuery(event.target.value)}
      />
      {matches.length === 0 ? (
        <p className="picker-empty">{t.noMatch}</p>
      ) : (
        <ul className="picker-list">
          {matches.map((guide) => (
            <li key={guide.slug}>
              <button type="button" className="picker-item" onClick={() => onPick(guide)}>
                <span className="picker-name">{guide.name}</span>
                <span className="picker-brand">{guide.brand}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Sources({ sources, t }) {
  if (!sources?.length) return null
  const manuals = sources.filter((s) => s.kind === 'manual')
  if (!manuals.length) return null
  return (
    <div className="sources">
      <span className="sources-title">{t.sources}</span>
      <ul>
        {manuals.map((source, index) => (
          <li key={`${source.label}-${source.page}-${index}`}>
            <a
              href={`${API_URL}/guides/${source.slug}/pdf#page=${String(source.page).split('-')[0]}`}
              target="_blank"
              rel="noreferrer"
            >
              {t.page} {source.page}
            </a>
            <span className="sources-file">{source.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function AskPage() {
  const { lang, setLang } = useAppLanguage()
  const t = (UI_TEXT[lang] || UI_TEXT.fr).ask
  const { guides } = useGuides()
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [vehicle, setVehicle] = useState(null)
  const [pending, setPending] = useState(null)      // question waiting for a vehicle
  const [picker, setPicker] = useState(null)        // { brand } when the vehicle list is open
  const [pickerQuery, setPickerQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const sessionId = useRef(newId()).current
  const threadEnd = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { threadEnd.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }) }, [messages, picker])

  const push = useCallback((message) => setMessages((prev) => [...prev, { id: newId(), ...message }]), [])

  const streamAnswer = useCallback(async (text, target) => {
    setBusy(true)
    const botId = newId()
    push({ id: botId, role: 'bot', kind: 'answer', text: '', streaming: true, vehicle: target })
    const update = (patch) => setMessages((prev) => prev.map((m) => (m.id === botId ? { ...m, ...patch } : m)))
    try {
      const response = await fetch(`${API_URL}/guides/${target.slug}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ message: text, lang, session_id: sessionId }),
      })
      if (!response.ok || !response.body) throw new Error(`stream ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let answer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''
        for (const block of blocks) {
          const event = /^event:\s*(.+)$/m.exec(block)?.[1]?.trim()
          const dataLines = block.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trim())
          if (!dataLines.length) continue
          let payload
          try { payload = JSON.parse(dataLines.join('\n')) } catch { continue }
          if (event === 'chunk' && payload?.text) {
            answer += payload.text
            update({ text: answer })
          } else if (event === 'end') {
            answer = String(payload?.response || answer)
            update({ text: answer, sources: payload?.sources_structured || [], streaming: false })
          } else if (event === 'error') {
            update({ text: t.streamError, streaming: false, failed: true })
          }
        }
      }
      update({ streaming: false })
    } catch {
      update({ text: t.streamError, streaming: false, failed: true })
    } finally {
      setBusy(false)
    }
  }, [lang, push, sessionId, t.streamError])

  const chooseVehicle = useCallback((guide) => {
    const target = { slug: guide.slug, name: guide.name }
    setVehicle(target)
    setPicker(null)
    setPickerQuery('')
    push({ role: 'user', kind: 'vehicle', text: guide.name })
    if (pending) {
      const question = pending
      setPending(null)
      streamAnswer(question, target)
    }
  }, [pending, push, streamAnswer])

  const send = useCallback(async (event) => {
    event?.preventDefault?.()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    push({ role: 'user', kind: 'question', text })

    setBusy(true)
    let decision = null
    try {
      const response = await fetch(`${API_URL}/ask/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, lang }),
      })
      decision = await response.json()
    } catch {
      decision = null
    }
    setBusy(false)

    if (decision?.action === 'abstain') {
      push({ role: 'bot', kind: 'abstain', brand: decision.brand })
      return
    }
    if (decision?.action === 'answer') {
      const target = decision.vehicle
      const switched = vehicle && vehicle.slug !== target.slug
      setVehicle(target)
      if (switched) push({ role: 'bot', kind: 'switch', vehicle: target })
      streamAnswer(text, target)
      return
    }
    if (vehicle) {           // vehicle already known and the question names none: keep it
      streamAnswer(text, vehicle)
      return
    }
    setPending(text)
    push({ role: 'bot', kind: 'clarify', reason: decision?.reason || 'no_vehicle', brand: decision?.brand || '', options: decision?.options || [] })
    setPicker({ brand: decision?.brand || '' })
  }, [busy, draft, lang, push, streamAnswer, vehicle])

  const suggestions = t.suggestions
  const empty = messages.length === 0

  return (
    <div className="ask">
      <header className="ask-header">
        <Link to="/" className="ask-home" aria-label={t.home}>Wallside</Link>
        <div className="ask-header-right">
          {vehicle && (
            <span className="vehicle-chip">
              <span className="vehicle-dot" aria-hidden="true" />
              {vehicle.name}
              <button type="button" onClick={() => { setPicker({ brand: '' }); setPickerQuery('') }}>{t.change}</button>
            </span>
          )}
          <div className="lang-switch" role="group" aria-label="Langue">
            {['fr', 'en', 'ko'].map((code) => (
              <button key={code} type="button" aria-pressed={lang === code} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </header>

      <main className="ask-main">
        {empty && (
          <section className="ask-intro">
            <h1>{t.title}</h1>
            <p>{t.lede}</p>
            <ul className="ask-suggestions">
              {suggestions.map((s) => (
                <li key={s}><button type="button" onClick={() => { setDraft(s); inputRef.current?.focus() }}>{s}</button></li>
              ))}
            </ul>
          </section>
        )}

        <ol className="thread">
          {messages.map((message) => {
            if (message.role === 'user') {
              return (
                <li key={message.id} className={`msg user ${message.kind === 'vehicle' ? 'is-vehicle' : ''}`}>
                  <p>{message.kind === 'vehicle' ? `${t.myVehicle} ${message.text}` : message.text}</p>
                </li>
              )
            }
            if (message.kind === 'clarify') {
              return (
                <li key={message.id} className="msg bot">
                  <p className="clarify-question">
                    {message.reason === 'several_versions' ? t.whichVersion
                      : message.reason === 'brand_only' ? `${t.whichModel} ${message.brand} ?`
                        : t.whichVehicle}
                  </p>
                  {message.options?.length > 0 && (
                    <div className="options">
                      {message.options.map((option) => (
                        <button key={option.slug} type="button" onClick={() => chooseVehicle(option)}>{option.name}</button>
                      ))}
                    </div>
                  )}
                  <p className="clarify-hint">{t.orSearch}</p>
                </li>
              )
            }
            if (message.kind === 'abstain') {
              return (
                <li key={message.id} className="msg bot">
                  <p><strong>{message.brand}</strong> {t.noManualForBrand}</p>
                  <p className="clarify-hint">{t.browseCatalog} <Link to="/guides">{t.catalog}</Link>.</p>
                </li>
              )
            }
            if (message.kind === 'switch') {
              return <li key={message.id} className="msg bot subtle"><p>{t.switchedTo} <strong>{message.vehicle.name}</strong>.</p></li>
            }
            return (
              <li key={message.id} className="msg bot">
                {message.vehicle && <span className="answer-vehicle">{message.vehicle.name}</span>}
                <p className={`answer ${message.failed ? 'failed' : ''}`}>
                  {message.text}
                  {message.streaming && <span className="caret" aria-hidden="true" />}
                </p>
                {!message.streaming && !message.failed && !message.sources?.some((s) => s.kind === 'manual') && (
                  <p className="no-source">{t.noManualSource}</p>
                )}
                <Sources sources={message.sources} t={t} />
              </li>
            )
          })}
          {busy && !messages.some((m) => m.streaming) && <li className="msg bot"><p className="thinking">{t.thinking}</p></li>}
        </ol>

        {picker && (
          <section className="picker-panel" aria-label={t.whichVehicle}>
            <header>
              <span>{picker.brand ? `${t.brandVehicles} ${picker.brand}` : t.allVehicles}</span>
              <button type="button" onClick={() => setPicker(null)} aria-label={t.close}>×</button>
            </header>
            <VehiclePicker
              guides={guides}
              brand={picker.brand}
              query={pickerQuery}
              onQuery={setPickerQuery}
              onPick={chooseVehicle}
              t={t}
            />
          </section>
        )}
        <div ref={threadEnd} />
      </main>

      <form className="composer" onSubmit={send}>
        <input
          id="ask-input"
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={vehicle ? `${t.askAbout} ${vehicle.name}` : t.placeholder}
          aria-label={t.placeholder}
          autoComplete="off"
        />
        <button type="submit" disabled={!draft.trim() || busy}>{t.send}</button>
      </form>
    </div>
  )
}
