import { useMemo, useState } from 'react'
import { motion as Motion } from 'framer-motion'
import { pctNum } from '../format'
import { FAMILY_LABEL, familyOf, howOf, labelOf } from '../meta'

const SCOPES = [
  ['vehicle', 'Inside the right vehicle', 'chunk_hit_5', 'native_plain', 'right passage in the top 5'],
  ['global', 'Across all manuals', 'doc_hit_1', 'native_model', 'right manual at rank 1'],
]

/** E2: every retrieval method, what it actually does, and what it scored. */
export default function Methods({ data, still }) {
  const { e2 } = data
  const [scopeKey, setScopeKey] = useState('vehicle')
  const [, , metric, refVariant, metricLabel] = SCOPES.find((s) => s[0] === scopeKey)
  const [selected, setSelected] = useState(null)

  const rows = e2?.rows
  const ranked = useMemo(() => {
    if (!rows) return []
    const cell = (spec, variant, scope) => rows.find((r) => r.retriever === spec && r.variant === variant && r.scope === scope)
    return [...new Set(rows.map((r) => r.retriever))]
      .map((spec) => ({ spec, score: cell(spec, refVariant, scopeKey)?.[metric] ?? 0, cell }))
      .sort((a, b) => b.score - a.score)
  }, [rows, refVariant, scopeKey, metric])

  if (!e2) {
    return (
      <article className="view">
        <span className="tab">E2 · METHODS</span>
        <h1>Every method, and what it does</h1>
        <div className="note">The full comparison (rerankers included) is still running. It will appear here at the next results build.</div>
      </article>
    )
  }

  const current = ranked.find((r) => r.spec === selected) || ranked[0]
  const cell = (variant, scope) => rows.find((r) => r.retriever === current.spec && r.variant === variant && r.scope === scope)
  const detail = [
    ['Inside the vehicle · right passage', cell('native_plain', 'vehicle'), 'chunk_hit_5'],
    ['Other language · right passage', cell('cross_plain', 'vehicle'), 'chunk_hit_5'],
    ['All manuals, model named · right manual', cell('native_model', 'global'), 'doc_hit_1'],
    ['All manuals, model named · right passage', cell('native_model', 'global'), 'chunk_hit_5'],
  ]

  return (
    <article className="view">
      <span className="tab">E2 · METHODS</span>
      <h1>Every method, and what it does</h1>
      <p className="lede">
        {ranked.length} retrieval configurations, all measured on the same test questions. Pick one to read exactly
        what it computes — the model, the parameters and the order of operations are the ones that were run.
      </p>

      <div className="controls">
        <div className="control">
          <span className="control-label">Rank by</span>
          <div className="seg">
            {SCOPES.map(([key, label]) => (
              <button key={key} type="button" aria-pressed={scopeKey === key} onClick={() => setScopeKey(key)}>{label}</button>
            ))}
          </div>
        </div>
        <div className="legend">
          {Object.entries(FAMILY_LABEL).map(([key, label]) => (
            <span key={key}><i className={`dot ${key}`} />{label}</span>
          ))}
        </div>
      </div>

      <div className="methods">
        <ol className="method-list">
          {ranked.map((row, index) => (
            <li key={row.spec}>
              <button
                type="button"
                aria-pressed={row.spec === current.spec}
                onClick={() => setSelected(row.spec)}
              >
                <span className="rank">{index + 1}</span>
                <span className="method-name">
                  {labelOf(row.spec)}
                  <i className={`dot ${familyOf(row.spec)}`} aria-hidden="true" />
                </span>
                <span className="method-score">{pctNum(row.score)}</span>
              </button>
            </li>
          ))}
          <li className="list-hint">{ranked.length} configurations · scroll for the rest</li>
        </ol>

        <Motion.aside
          className="method-detail"
          key={current.spec}
          initial={still ? false : { opacity: 0, y: 10 }}
          animate={still ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}
        >
          <span className={`badge ${familyOf(current.spec)}`}>{FAMILY_LABEL[familyOf(current.spec)] || 'Method'}</span>
          <h2>{labelOf(current.spec)}</h2>
          <p className="how">{howOf(current.spec) || 'No description recorded for this specification.'}</p>
          <p className="spec-line"><span>spec</span><code>{current.spec}</code></p>
          <dl className="detail-metrics">
            {detail.map(([label, row, key]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  {pctNum(row?.[key])}
                  {row && <span className="ci">{pctNum(row[`${key}_lo`], 0)}–{pctNum(row[`${key}_hi`], 0)}</span>}
                </dd>
              </div>
            ))}
          </dl>
        </Motion.aside>
      </div>

      <p className="caption">
        Ranked by {metricLabel}, question form <em>{refVariant === 'native_plain' ? 'no vehicle' : 'model named'}</em>.
        95% confidence intervals in small type. Cross-encoder reranking adds roughly 1.5 s per question; everything
        else answers in milliseconds.
      </p>
    </article>
  )
}
