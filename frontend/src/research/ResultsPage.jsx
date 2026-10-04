import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion as Motion, useReducedMotion } from 'framer-motion'
import Overview from './views/Overview'
import Corpus from './views/Corpus'
import Scale from './views/Scale'
import Methods from './views/Methods'
import Clarify from './views/Clarify'
import Protocol from './views/Protocol'
import './ResultsPage.css'

/**
 * Research results site. Every number is read from research-results.json, written by
 * research/scripts/build_report.py from the experiment outputs; nothing is typed in by hand.
 * One short page per question, switched by the navbar — no long scroll.
 */

const PAGES = [
  { id: 'overview', tab: '00', nav: 'Overview', title: 'Finding the right manual', view: Overview },
  { id: 'corpus', tab: 'DATA', nav: 'Corpus & exam', title: 'The library and the exam', view: Corpus },
  { id: 'scale', tab: 'E1', nav: 'Corpus size', title: 'The more manuals, the less it finds', view: Scale },
  { id: 'methods', tab: 'E2', nav: 'Methods', title: 'Every method, and what it does', view: Methods },
  { id: 'clarify', tab: 'E4', nav: 'Clarification', title: 'Asking beats guessing', view: Clarify },
  { id: 'protocol', tab: 'HOW', nav: 'Protocol', title: 'How the evaluation is run', view: Protocol },
]

const idFromHash = () => {
  const id = window.location.hash.replace(/^#\/?/, '')
  return PAGES.some((p) => p.id === id) ? id : 'overview'
}

function useResults() {
  const [data, setData] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    fetch('/research-results.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('missing'))))
      .then(setData)
      .catch(() => setFailed(true))
  }, [])
  return { data, failed }
}

export default function ResultsPage() {
  const { data, failed } = useResults()
  const still = useReducedMotion()
  const [pageId, setPageId] = useState(idFromHash)

  useEffect(() => {
    const sync = () => setPageId(idFromHash())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  const page = useMemo(() => PAGES.find((p) => p.id === pageId) || PAGES[0], [pageId])

  useEffect(() => {
    document.title = `${page.title} — Wallside`
    window.scrollTo({ top: 0, behavior: still ? 'auto' : 'smooth' })
  }, [page, still])

  const go = (id) => (event) => {
    event.preventDefault()
    window.location.hash = `/${id}`
    setPageId(id)
  }

  const View = page.view

  return (
    <div className="research">
      <header className="navbar">
        <a className="brand" href="#/overview" onClick={go('overview')}>
          <span className="brand-mark">WALLSIDE</span>
          <span className="brand-name">Retrieval research</span>
        </a>
        <nav aria-label="Sections">
          {PAGES.map((p) => (
            <a
              key={p.id}
              href={`#/${p.id}`}
              onClick={go(p.id)}
              aria-current={p.id === page.id ? 'page' : undefined}
            >
              <span className="nav-tab">{p.tab}</span>
              {p.nav}
              {p.id === page.id && (
                <Motion.i layoutId="nav-underline" transition={{ duration: still ? 0 : 0.35, ease: [0.22, 0.61, 0.36, 1] }} />
              )}
            </a>
          ))}
        </nav>
      </header>

      <main className="stage">
        {failed && (
          <p className="empty">
            Results have not been generated yet. Run{' '}
            <code>python scripts/build_report.py --json ../frontend/public/research-results.json</code> inside{' '}
            <code>research/</code>.
          </p>
        )}
        {!failed && !data && <p className="empty">Loading results…</p>}
        {!failed && data && (
          <AnimatePresence mode="wait">
            <Motion.div
              key={page.id}
              initial={still ? false : { opacity: 0, y: 14 }}
              animate={still ? {} : { opacity: 1, y: 0 }}
              exit={still ? {} : { opacity: 0, y: -8 }}
              transition={{ duration: 0.34, ease: [0.22, 0.61, 0.36, 1] }}
            >
              <View data={data} still={still} go={go} />
            </Motion.div>
          </AnimatePresence>
        )}
      </main>
    </div>
  )
}
