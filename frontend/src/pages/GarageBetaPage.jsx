import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { API_URL } from '../api'
import './GarageBetaPage.css'

const DTC_PRESETS = ['P0171', 'P0300', 'P0420', 'P0101', 'P0128', 'P2187']

const GARAGE_TYPES = [
  { value: 'independent', label: 'Garage indépendant' },
  { value: 'franchise', label: 'Réseau / franchise' },
  { value: 'concession', label: 'Concession constructeur' },
  { value: 'fleet', label: 'Atelier flotte' },
  { value: 'school', label: 'CFA / centre de formation' },
]

const TEAM_SIZES = ['1', '2-5', '6-10', '11-25', '26+']

function formatFiche(result) {
  const { code, title, symptoms, causes, checks, structure, hint } = result
  const lines = []
  lines.push(`FICHE DIAGNOSTIC — ${code}`)
  lines.push('─'.repeat(44))
  if (title) lines.push(`Intitulé : ${title}`)
  if (structure?.category) lines.push(`Catégorie : ${structure.category}`)
  if (structure?.scope) lines.push(`Portée : ${structure.scope}`)
  if (structure?.subsystem_hint) lines.push(`Sous-système : ${structure.subsystem_hint}`)
  if (symptoms?.length) {
    lines.push('')
    lines.push('Symptômes observés :')
    symptoms.forEach((s) => lines.push(`  • ${s}`))
  }
  if (causes?.length) {
    lines.push('')
    lines.push('Causes probables :')
    causes.forEach((c) => lines.push(`  • ${c}`))
  }
  if (checks?.length) {
    lines.push('')
    lines.push('Contrôles à effectuer :')
    checks.forEach((c) => lines.push(`  • ${c}`))
  }
  if (hint) {
    lines.push('')
    lines.push(`Note : ${hint}`)
  }
  lines.push('')
  lines.push(`Généré via Auris Garage Beta — ${new Date().toLocaleDateString('fr-FR')}`)
  return lines.join('\n')
}

export default function GarageBetaPage() {
  const [health, setHealth] = useState(null)
  const [dtcInput, setDtcInput] = useState('')
  const [dtcBusy, setDtcBusy] = useState(false)
  const [dtcError, setDtcError] = useState('')
  const [dtcResult, setDtcResult] = useState(null)
  const [relatedRecalls, setRelatedRecalls] = useState([])
  const [ficheCopied, setFicheCopied] = useState(false)
  const [feedback, setFeedback] = useState(null)

  const [recallBrand, setRecallBrand] = useState('')
  const [recallQuery, setRecallQuery] = useState('')
  const [recallBusy, setRecallBusy] = useState(false)
  const [recallError, setRecallError] = useState('')
  const [recallHits, setRecallHits] = useState([])

  const [waitlist, setWaitlist] = useState({
    email: '',
    garage_name: '',
    country: 'France',
    garage_type: '',
    team_size: '',
  })
  const [waitlistBusy, setWaitlistBusy] = useState(false)
  const [waitlistStatus, setWaitlistStatus] = useState(null)

  const resultRef = useRef(null)

  useEffect(() => {
    fetch(`${API_URL}/garage/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  const corporaReady = useMemo(() => {
    if (!health?.corpora) return false
    return Boolean(health.corpora.dtc?.built && health.corpora.recalls?.built)
  }, [health])

  const fiche = useMemo(() => {
    if (!dtcResult?.valid) return ''
    return formatFiche(dtcResult)
  }, [dtcResult])

  const fetchRelatedRecalls = useCallback(async (query) => {
    try {
      const res = await fetch(`${API_URL}/garage/recalls-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 3 }),
      })
      if (!res.ok) return
      const data = await res.json()
      setRelatedRecalls(data?.results || [])
    } catch {
      /* silent */
    }
  }, [])

  const handleDtcLookup = useCallback(
    async (raw) => {
      const code = String(raw || dtcInput).trim().toUpperCase()
      if (!code) {
        setDtcError('Entrez un code (ex. P0300).')
        return
      }
      setDtcError('')
      setDtcBusy(true)
      setDtcResult(null)
      setRelatedRecalls([])
      setFicheCopied(false)
      setFeedback(null)
      try {
        const res = await fetch(`${API_URL}/garage/dtc/${encodeURIComponent(code)}`)
        const data = await res.json()
        if (!res.ok || !data?.success) {
          setDtcError(
            data?.error === 'invalid_dtc_format'
              ? 'Format invalide. Utilisez un code OBD-II (P/B/C/U + 4 caractères).'
              : 'Code introuvable dans la base.'
          )
          return
        }
        setDtcResult(data)
        setDtcInput(code)
        const searchTerms = [data?.title, code].filter(Boolean).join(' ')
        if (searchTerms) fetchRelatedRecalls(searchTerms)
        requestAnimationFrame(() => {
          resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
      } catch {
        setDtcError('Erreur réseau. Vérifiez votre connexion.')
      } finally {
        setDtcBusy(false)
      }
    },
    [dtcInput, fetchRelatedRecalls]
  )

  const handleRecallSearch = useCallback(async () => {
    const q = recallQuery.trim()
    const brand = recallBrand.trim()
    if (!q && !brand) {
      setRecallError('Saisissez une marque ou un mot-clé.')
      return
    }
    setRecallError('')
    setRecallBusy(true)
    try {
      const res = await fetch(`${API_URL}/garage/recalls-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, brand, limit: 8 }),
      })
      const data = await res.json()
      if (!res.ok || !data?.success) {
        setRecallError('Impossible de rechercher pour le moment.')
        setRecallHits([])
        return
      }
      setRecallHits(data?.results || [])
    } catch {
      setRecallError('Erreur réseau.')
    } finally {
      setRecallBusy(false)
    }
  }, [recallBrand, recallQuery])

  const handleWaitlist = useCallback(
    async (event) => {
      event.preventDefault()
      if (!waitlist.email.trim()) {
        setWaitlistStatus({ kind: 'error', msg: 'Email requis.' })
        return
      }
      setWaitlistBusy(true)
      setWaitlistStatus(null)
      try {
        const res = await fetch(`${API_URL}/garage/waitlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...waitlist, lang: 'fr', source: 'garage_beta_page' }),
        })
        const data = await res.json()
        if (!res.ok || !data?.success) {
          setWaitlistStatus({
            kind: 'error',
            msg: data?.error === 'invalid_email' ? 'Email invalide.' : "Inscription impossible.",
          })
          return
        }
        setWaitlistStatus({
          kind: 'success',
          msg: data.already_exists
            ? 'Vous êtes déjà sur la liste — merci !'
            : 'Inscription confirmée. Nous revenons vers vous sous peu.',
        })
      } catch {
        setWaitlistStatus({ kind: 'error', msg: 'Erreur réseau.' })
      } finally {
        setWaitlistBusy(false)
      }
    },
    [waitlist]
  )

  const copyFiche = useCallback(async () => {
    if (!fiche) return
    try {
      await navigator.clipboard.writeText(fiche)
      setFicheCopied(true)
      setTimeout(() => setFicheCopied(false), 1800)
    } catch {
      /* ignore */
    }
  }, [fiche])

  return (
    <div className="garage">
      <div className="garage-inner">
        {/* ---------- Top bar ---------- */}
        <div className="garage-topbar">
          <div className="garage-brand">
            <span>Auris · <em style={{ fontStyle: 'italic', color: 'var(--accent)' }}>Garage</em></span>
            <span className="garage-badge">
              <span className="dot" />
              BETA B2B
            </span>
          </div>
          <Link to="/">← retour site</Link>
        </div>

        {/* ---------- Hero ---------- */}
        <Motion.section
          className="garage-hero"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
        >
          <span className="garage-hero-eyebrow">Atelier · Diagnostic · Formation</span>
          <h1>
            L'atelier assisté par <span className="accent">l'IA Auris</span>
          </h1>
          <p>
            Recherchez n'importe quel code défaut OBD-II, consultez les rappels constructeurs
            et générez une fiche d'intervention prête à partager. Module beta réservé
            aux garages partenaires.
          </p>
        </Motion.section>

        {/* ---------- Health banner ---------- */}
        {health && !corporaReady && (
          <div className="status-banner info">
            Corpus en cours de chargement — certaines recherches peuvent être limitées.
          </div>
        )}

        {/* ---------- DTC panel ---------- */}
        <Motion.section
          className="garage-panel"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
        >
          <h2>Diagnostic code défaut</h2>
          <p className="panel-sub">
            Tape un code OBD-II (ex. <code>P0171</code>) pour obtenir symptômes, causes probables
            et contrôles à effectuer.
          </p>

          <div className="dtc-grid">
            <div className="garage-field">
              <label>Code</label>
              <input
                className={`garage-input is-dtc${dtcError ? ' invalid' : ''}`}
                placeholder="P0300"
                value={dtcInput}
                maxLength={7}
                onChange={(e) => {
                  setDtcInput(e.target.value.toUpperCase())
                  setDtcError('')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleDtcLookup()
                }}
              />
            </div>
            <div className="garage-field" style={{ alignSelf: 'end' }}>
              <button
                className="garage-button"
                onClick={() => handleDtcLookup()}
                disabled={dtcBusy}
              >
                {dtcBusy ? 'Recherche…' : 'Analyser le code'}
              </button>
            </div>
            <div className="garage-field" style={{ alignSelf: 'end' }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {health?.curated_dtc_count
                  ? `${health.curated_dtc_count} codes curés + décodage structurel SAE J2012`
                  : 'Base SAE J2012 + dictionnaire curé'}
              </span>
            </div>
          </div>

          <div className="dtc-presets">
            {DTC_PRESETS.map((c) => (
              <button
                key={c}
                type="button"
                className="dtc-chip"
                onClick={() => handleDtcLookup(c)}
                disabled={dtcBusy}
              >
                {c}
              </button>
            ))}
          </div>

          {dtcError && (
            <div className="status-banner error" style={{ marginTop: 18 }}>
              {dtcError}
            </div>
          )}

          <AnimatePresence mode="wait">
            {dtcResult && (
              <Motion.div
                key={dtcResult.code || 'struct'}
                ref={resultRef}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35 }}
                style={{ marginTop: 24 }}
              >
                <div className="result-header">
                  <div>
                    <div className="result-code">{dtcResult.code || dtcInput}</div>
                    <h3 className="result-title">
                      {dtcResult.title || 'Code reconnu — décodage structurel'}
                    </h3>
                    <div className="result-meta">
                      {dtcResult.structure?.category && (
                        <span className="meta-tag">{dtcResult.structure.category}</span>
                      )}
                      {dtcResult.structure?.scope && (
                        <span className="meta-tag">{dtcResult.structure.scope}</span>
                      )}
                      {dtcResult.structure?.subsystem_hint && (
                        <span className="meta-tag">{dtcResult.structure.subsystem_hint}</span>
                      )}
                      {dtcResult.curated === false && <span className="meta-tag">Non curé</span>}
                    </div>
                  </div>
                </div>

                {dtcResult.symptoms?.length > 0 && (
                  <div className="result-section">
                    <h3>Symptômes</h3>
                    <ul>
                      {dtcResult.symptoms.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {dtcResult.causes?.length > 0 && (
                  <div className="result-section">
                    <h3>Causes probables</h3>
                    <ul>
                      {dtcResult.causes.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {dtcResult.checks?.length > 0 && (
                  <div className="result-section">
                    <h3>Contrôles à effectuer</h3>
                    <ul>
                      {dtcResult.checks.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {dtcResult.curated === false && dtcResult.hint && (
                  <div className="result-section">
                    <h3>Décodage structurel</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 14.5 }}>
                      {dtcResult.hint}
                    </p>
                  </div>
                )}

                {relatedRecalls.length > 0 && (
                  <div className="related-recalls">
                    <h3
                      style={{
                        fontFamily: 'var(--font-body)',
                        fontSize: 13,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.14em',
                        color: 'var(--accent)',
                        margin: '0 0 12px',
                      }}
                    >
                      Rappels constructeurs liés
                    </h3>
                    {relatedRecalls.map((r, i) => (
                      <div key={`${r.doc_id || i}`} className="recall-card">
                        <div className="recall-title">{r.title || r.brand || 'Rappel'}</div>
                        <div className="recall-snippet">
                          {(r.text || '').slice(0, 220)}
                          {r.text?.length > 220 ? '…' : ''}
                        </div>
                        {r.url && (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: 'var(--tech)', fontSize: 12 }}
                          >
                            source →
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {fiche && (
                  <div className="fiche">
                    <div className="fiche-header">
                      <h3>Fiche d'intervention</h3>
                      <button
                        className="garage-button ghost"
                        type="button"
                        onClick={copyFiche}
                        style={{ padding: '8px 18px', fontSize: 12 }}
                      >
                        {ficheCopied ? '✓ Copié' : 'Copier'}
                      </button>
                    </div>
                    <div className="fiche-pre">{fiche}</div>
                  </div>
                )}

                <div className="feedback">
                  <span>Utile ?</span>
                  <button
                    type="button"
                    className={`feedback-button${feedback === 'up' ? ' active up' : ''}`}
                    onClick={() => setFeedback('up')}
                  >
                    👍 Oui
                  </button>
                  <button
                    type="button"
                    className={`feedback-button${feedback === 'down' ? ' active down' : ''}`}
                    onClick={() => setFeedback('down')}
                  >
                    👎 À améliorer
                  </button>
                </div>
              </Motion.div>
            )}
          </AnimatePresence>
        </Motion.section>

        {/* ---------- Recalls panel ---------- */}
        <Motion.section
          className="garage-panel"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <h2>Rappels constructeurs</h2>
          <p className="panel-sub">
            Recherche dans les corpus RappelConso (data.gouv.fr) et NHTSA.
            {health?.corpora?.recalls?.documents
              ? ` ${health.corpora.recalls.documents} documents indexés.`
              : ''}
          </p>

          <div className="dtc-grid" style={{ gridTemplateColumns: '180px 1fr auto' }}>
            <div className="garage-field">
              <label>Marque</label>
              <input
                className="garage-input"
                placeholder="Renault, Peugeot…"
                value={recallBrand}
                onChange={(e) => setRecallBrand(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRecallSearch()}
              />
            </div>
            <div className="garage-field">
              <label>Mot-clé / modèle</label>
              <input
                className="garage-input"
                placeholder="airbag, freins, clio…"
                value={recallQuery}
                onChange={(e) => setRecallQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRecallSearch()}
              />
            </div>
            <div className="garage-field" style={{ alignSelf: 'end' }}>
              <button
                className="garage-button"
                onClick={handleRecallSearch}
                disabled={recallBusy}
              >
                {recallBusy ? 'Recherche…' : 'Chercher'}
              </button>
            </div>
          </div>

          {recallError && (
            <div className="status-banner error" style={{ marginTop: 18 }}>
              {recallError}
            </div>
          )}

          {recallHits.length > 0 && (
            <div style={{ marginTop: 20 }}>
              {recallHits.map((r, i) => (
                <Motion.div
                  key={`${r.doc_id || i}`}
                  className="recall-card"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: i * 0.04 }}
                >
                  <div className="recall-title">
                    {r.title || r.brand || 'Rappel constructeur'}
                  </div>
                  <div className="result-meta" style={{ marginTop: 4, marginBottom: 6 }}>
                    {r.brand && <span className="meta-tag">{r.brand}</span>}
                    {r.model && <span className="meta-tag">{r.model}</span>}
                    {r.year && <span className="meta-tag">{r.year}</span>}
                    {r.source && <span className="meta-tag">{r.source}</span>}
                  </div>
                  <div className="recall-snippet">
                    {(r.text || '').slice(0, 320)}
                    {r.text?.length > 320 ? '…' : ''}
                  </div>
                  {r.url && (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--tech)', fontSize: 12 }}
                    >
                      source officielle →
                    </a>
                  )}
                </Motion.div>
              ))}
            </div>
          )}
        </Motion.section>

        {/* ---------- Waitlist panel ---------- */}
        <Motion.section
          className="garage-panel"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <h2>Rejoindre la beta</h2>
          <p className="panel-sub">
            Accès prioritaire au module garage complet (OBD live, historique interventions,
            partage équipe). Limité aux 50 premiers ateliers.
          </p>

          {waitlistStatus && (
            <div className={`status-banner ${waitlistStatus.kind}`}>{waitlistStatus.msg}</div>
          )}

          <form className="waitlist-grid" onSubmit={handleWaitlist}>
            <div className="garage-field full-row">
              <label>Email professionnel *</label>
              <input
                type="email"
                className="garage-input"
                placeholder="contact@monatelier.fr"
                value={waitlist.email}
                onChange={(e) => setWaitlist({ ...waitlist, email: e.target.value })}
                required
              />
            </div>

            <div className="garage-field">
              <label>Nom du garage</label>
              <input
                className="garage-input"
                placeholder="Garage du Centre"
                value={waitlist.garage_name}
                onChange={(e) => setWaitlist({ ...waitlist, garage_name: e.target.value })}
              />
            </div>

            <div className="garage-field">
              <label>Pays</label>
              <input
                className="garage-input"
                value={waitlist.country}
                onChange={(e) => setWaitlist({ ...waitlist, country: e.target.value })}
              />
            </div>

            <div className="garage-field">
              <label>Type de structure</label>
              <select
                className="garage-input"
                value={waitlist.garage_type}
                onChange={(e) => setWaitlist({ ...waitlist, garage_type: e.target.value })}
              >
                <option value="">— Choisir —</option>
                {GARAGE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="garage-field">
              <label>Taille de l'équipe</label>
              <select
                className="garage-input"
                value={waitlist.team_size}
                onChange={(e) => setWaitlist({ ...waitlist, team_size: e.target.value })}
              >
                <option value="">— Choisir —</option>
                {TEAM_SIZES.map((t) => (
                  <option key={t} value={t}>
                    {t} technicien(s)
                  </option>
                ))}
              </select>
            </div>

            <div className="garage-field full-row" style={{ marginTop: 8 }}>
              <button type="submit" className="garage-button" disabled={waitlistBusy}>
                {waitlistBusy ? 'Envoi…' : 'Demander un accès beta'}
              </button>
            </div>
          </form>
        </Motion.section>

        {/* ---------- Disclaimer ---------- */}
        <div className="garage-disclaimer">
          <strong>Beta B2B.</strong> Les informations fournies sont indicatives et s'appuient sur
          les normes publiques (SAE J2012) et les rappels officiels (RappelConso, NHTSA).
          Elles <strong>ne remplacent pas</strong> le diagnostic d'un professionnel ni la
          documentation constructeur.
        </div>
      </div>
    </div>
  )
}
