import { useEffect, useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { LineChart, ParetoChart, SignalBars } from './charts'
import { SERIES, dec, intEn, pct, pctNum } from './format'
import './ResultsPage.css'

/**
 * Research results site. Every number is read from research-results.json, written by
 * research/scripts/build_report.py from the experiment outputs; nothing is typed in by hand.
 */

const R = {
  bm25: 'bm25_stem',
  dense: 'dense:bge-m3',
  hybrid: 'wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)',
  ctx: 'wsum(bm25_stem+ctx,dense:bge-m3+ctx;w=0.3|0.7)',
  router: 'name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))',
  hnsw: 'hnsw(dense:bge-m3)',
}
const LABELS = {
  [R.bm25]: 'BM25 (keywords)',
  [R.dense]: 'bge-m3 (meaning)',
  [R.hybrid]: 'Hybrid 0.3 BM25 + 0.7 bge-m3',
  [R.ctx]: 'Hybrid + document headers',
  [R.router]: 'Name routing + hybrid',
  [R.hnsw]: 'bge-m3, approximate index (HNSW)',
  bm25: 'BM25 (no stemming)',
  'bm25_stem+ctx': 'BM25 + document headers',
  'dense:bge-m3+ctx': 'bge-m3 + document headers',
  'dense:multilingual-e5-large-instruct': 'e5-large (meaning)',
  'rrf(bm25_stem,dense:bge-m3)': 'RRF fusion (today in production)',
  'rm3(bm25)': 'BM25 + query expansion (RM3)',
  'doc_router(dense:bge-m3+ctx)': 'Pick the manual, then the passage',
  'name_boost(dense:bge-m3;lam=0.5)': 'bge-m3 + vehicle-name boost',
  'name_router(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': 'Name routing (name kept in the query)',
  'rerank(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': 'Hybrid + cross-encoder reranking',
  'rerank(name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)))': 'Routing + hybrid + cross-encoder reranking',
  'm3rerank(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': 'Hybrid + BGE-M3 reranking (multi-vector)',
}
const SHORT = {
  [R.bm25]: 'BM25', [R.dense]: 'bge-m3', [R.hybrid]: 'hybrid',
  [R.ctx]: '+ headers', [R.router]: 'routing', [R.hnsw]: 'HNSW',
}
const labelOf = (spec) => LABELS[spec] || spec

const VARIANTS = [
  ['native_plain', 'No vehicle'],
  ['native_brand', 'Brand'],
  ['native_model', 'Model'],
  ['native_full', 'Full name'],
]
const METRICS = [
  ['chunk_hit_5', 'Right passage (top 5)'],
  ['doc_hit_1', 'Right manual (rank 1)'],
]
const POLICY_LABEL = {
  never: 'Never ask',
  always: 'Always ask',
  name_rule: 'Ask when no vehicle is named',
  oracle: 'Oracle',
}
const SIGNAL_NAME = {
  vehicle_margin: 'gap between 1st and 2nd vehicle',
  passage_agreement: 'agreement between passages',
  top1_vehicle_share: 'share of the top vehicle',
  vehicle_entropy: 'spread across vehicles',
  n_vehicles_top10: 'vehicles in the top 10',
  n_brands_top10: 'brands in the top 10',
  query_tokens: 'question length',
  mentions_brand: 'brand mentioned',
}
const ACTION_LABEL = { answer: 'answer', clarify: 'ask', abstain: 'abstain' }
const SECTIONS = [
  ['question', '00', 'What we measure'],
  ['corpus', 'DATA', 'Corpus'],
  ['scale', 'E1', 'Corpus size'],
  ['techniques', 'E2', 'Techniques'],
  ['clarify', 'E4', 'Clarification'],
  ['method', 'METHOD', 'Method'],
]

/** The decision layer writes compact reasons; spell them out. */
const readableReason = (reason) => {
  const brand = /no manual for brand '(.+)'/.exec(reason)
  if (brand) return `no manual for ${brand[1].replace(/^./, (c) => c.toUpperCase())}`
  const offTopic = /off-topic \(max similarity ([\d.]+) < ([\d.]+)\)/.exec(reason)
  if (offTopic) return `off-topic (similarity ${dec(offTopic[1], 3)} < ${dec(offTopic[2], 3)})`
  const many = /(\d+|many) candidate vehicles \(p=([\d.]+)\)/.exec(reason)
  if (many) return `many possible vehicles (p = ${dec(many[2])})`
  const versions = /(\d+) versions match the name/.exec(reason)
  if (versions) return `${versions[1]} versions share that name`
  return reason
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

function Reveal({ children, delay = 0, className = '' }) {
  const still = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={still ? false : { opacity: 0, y: 18 }}
      whileInView={still ? {} : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.55, delay, ease: [0.22, 0.61, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}

function Section({ id, tab, title, lede, children }) {
  return (
    <section id={id}>
      <Reveal className="section-head">
        <span className="tab">{tab}</span>
        <h2>{title}</h2>
        {lede && <p className="lede">{lede}</p>}
      </Reveal>
      {children}
    </section>
  )
}

export default function ResultsPage() {
  const { data, failed } = useResults()
  const still = useReducedMotion()
  const [metric, setMetric] = useState('chunk_hit_5')
  const [variant, setVariant] = useState('native_plain')
  const [strategy, setStrategy] = useState('hard')
  const [scope, setScope] = useState('global')

  useEffect(() => { document.title = 'Finding the right manual — research results' }, [])

  const e1 = data?.e1
  const maxN = useMemo(() => (e1 ? Math.max(...e1.rows.map((r) => r.n)) : 0), [e1])
  const tiers = useMemo(() => (e1 ? [...new Set(e1.rows.map((r) => r.n))].sort((a, b) => a - b) : []), [e1])
  const value = (retriever, v, s, n, m) =>
    e1?.rows.find((r) => r.retriever === retriever && r.variant === v && r.strategy === s && r.n === n)?.[m]

  const series = useMemo(() => {
    if (!e1) return []
    return e1.retrievers.map((r, index) => ({
      label: labelOf(r.spec),
      short: SHORT[r.spec] || r.label,
      color: SERIES[index % SERIES.length],
      points: e1.rows
        .filter((row) => row.retriever === r.spec && row.variant === variant && row.strategy === strategy)
        .sort((a, b) => a.n - b.n)
        .map((row) => ({ x: row.n, y: row[metric], lo: row[`${metric}_lo`], hi: row[`${metric}_hi`] })),
    }))
  }, [e1, metric, strategy, variant])

  if (failed) {
    return (
      <main className="results">
        <p className="empty">
          Results have not been generated yet. Run <code>python scripts/build_report.py --json ../frontend/public/research-results.json</code> inside <code>research/</code>.
        </p>
      </main>
    )
  }
  if (!data) return <main className="results"><p className="empty">Loading results…</p></main>

  const { corpus, dataset, e2, e4 } = data
  const policies = e4.policies.filter((p) => ['none', 'direct'].includes(p.strategy))
  const policy = (name) => policies.find((p) => p.policy === name)
  const byVariant = (name, v) => e4.by_variant.find((p) => p.policy === name && p.variant === v && ['none', 'direct'].includes(p.strategy))
  const sweep = policies.filter((p) => p.policy.startsWith('classifier')).sort((a, b) => a.avg_turns - b.avg_turns)
  const mainPolicies = ['never', 'always', 'name_rule', 'oracle'].map(policy).filter(Boolean)
  const genericity = e4.detection.genericity_among_ambiguous || {}
  const okExamples = e4.examples.filter((e) => e.correct_action === true || e.correct_action === 'True').length
  const rise = still ? {} : { initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 } }

  const readouts = [
    {
      from: pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'), 0),
      to: pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'), 0),
      caption: `right passage found inside 1 manual, then across ${maxN}, for a question that names no vehicle`,
    },
    {
      from: pct(value(R.hybrid, 'native_model', 'hard', maxN, 'doc_hit_1'), 0),
      to: pct(value(R.router, 'native_model', 'hard', maxN, 'doc_hit_1'), 0),
      caption: `right manual among ${maxN} when the question names the model: search alone, then name routing`,
    },
    {
      from: pct(byVariant('never', 'native_plain')?.doc_hit_1, 0),
      to: pct(byVariant('name_rule', 'native_plain')?.doc_hit_1, 0),
      caption: `right manual for a question with no vehicle: no clarification, then ${dec(policy('name_rule')?.avg_turns)} question asked`,
    },
  ]

  return (
    <div className="results">
      <nav className="toc" aria-label="Contents">
        <ol>
          {SECTIONS.map(([id, tab, title]) => (
            <li key={id}><a href={`#${id}`}><span className="tab">{tab}</span>{title}</a></li>
          ))}
        </ol>
      </nav>

      <main>
        <header className="cover">
          <motion.p className="eyebrow" {...rise} transition={{ duration: 0.5 }}>
            <span>Research · retrieval over car owner manuals</span>
            <span className="flag">Provisional results</span>
          </motion.p>
          <motion.h1 {...rise} transition={{ duration: 0.65, delay: 0.06 }}>Finding the right manual</motion.h1>
          <motion.p className="lede" {...rise} transition={{ duration: 0.6, delay: 0.14 }}>
            An assistant answering from {corpus.manuals} owner manuals has to find the right document first, then
            the right page. This site measures how well it does that as the library grows, which techniques hold
            up, and when asking one question beats guessing.
          </motion.p>
          <div className="readouts">
            {readouts.map((item, index) => (
              <motion.div
                className="readout"
                key={item.caption}
                {...rise}
                transition={{ duration: 0.6, delay: 0.22 + index * 0.08 }}
              >
                <p className="readout-figure"><span>{item.from}</span><i>→</i><b>{item.to}</b></p>
                <p className="readout-caption">{item.caption}</p>
              </motion.div>
            ))}
          </div>
        </header>

        <Section id="question" tab="00" title="What we measure">
          <Reveal>
            <p>
              For every question the system must retrieve <strong>the right manual</strong> (which vehicle) and
              <strong> the right passage</strong> (which page). Both are measured separately, with 95% confidence
              intervals, while varying three things: how many manuals are searched, the retrieval technique, and
              how much the question says about the vehicle.
            </p>
            <div className="cards">
              <article><h3>E1 · Corpus size</h3><p>How much accuracy is lost going from 1 to {maxN} manuals, with random or same-brand distractors?</p></article>
              <article><h3>E2 · Techniques</h3><p>Keywords, meaning, hybrids, document headers, routing, reranking: which one holds up at full scale?</p></article>
              <article><h3>E4 · Clarification</h3><p>When the question names no vehicle, should the system guess or ask? And what does asking cost?</p></article>
            </div>
          </Reveal>
        </Section>

        <Section
          id="corpus"
          tab="DATA"
          title="The library and the exam"
          lede={`Extracted verbatim from the production indexes: ${corpus.manuals} manuals, ${intEn(corpus.chunks)} passages, ${intEn(corpus.pages)} pages, ${corpus.vehicles} vehicles, ${corpus.lang_fr} French and ${corpus.lang_en} English manuals.`}
        >
          <Reveal>
            <h3>Data defects found along the way</h3>
            <ul className="findings">
              <li>
                <span className="where">PDF EXTRACTION</span>
                <span><strong>{intEn(corpus.garbled_chunks)} unreadable passages</strong> — {corpus.garbled_manuals.map((m) => `${m.name} (${pct(m.share, 0)})`).join(', ')}. The extractor mis-decoded those fonts; fixed (falls back to PyMuPDF), re-indexing still to do.</span>
              </li>
              <li>
                <span className="where">DUPLICATES</span>
                <span><strong>The same PDF indexed twice:</strong> {corpus.duplicates.map((d) => `${d.manual} = ${d.of}`).join(', ')}.</span>
              </li>
              <li>
                <span className="where">SHARED TEXT</span>
                <span><strong>{intEn(corpus.shared_text_chunks)} passages</strong> are word-for-word identical to a passage in another manual: the “right document” is sometimes ambiguous by nature.</span>
              </li>
            </ul>
          </Reveal>

          <Reveal>
            <h3>The exam: questions whose answer page is known</h3>
            <p>
              For each passage, a Gemini model (<code>{dataset.generator}</code>, a different generation from the one
              under test) writes an owner-style question, its answer, and a verbatim quote. A question is kept only
              if that quote really appears in the passage. Every question exists in eight forms: two languages ×
              (no vehicle, brand, model, full name).
            </p>
            <div className="note">
              <strong>Partial set:</strong> {intEn(dataset.questions)} questions over {dataset.manuals} manuals
              ({dataset.splits.test} test, {dataset.splits.dev} dev), rebuilt from cache when the Gemini prepaid
              credits ran out. It covers mostly the first manuals alphabetically, so these figures are provisional.
              {dataset.audit && ` Independent audit of ${dataset.audit.supported + dataset.audit.supported_with_extra_detail + dataset.audit.unsupported} random questions: ${dataset.audit.supported + dataset.audit.supported_with_extra_detail} answers supported by their quote, ${dataset.audit.unsupported} unsupported.`}
            </div>
            <div className="sample">
              <div>
                <span className="kind">GENERATED QUESTION · {dataset.sample.manual} · page {dataset.sample.page}</span>
                {[['No vehicle', 'plain'], ['Brand', 'brand'], ['Model', 'model'], ['Full name', 'full']].map(([label, form]) => (
                  <p key={form}><span className="form">{label}</span>{dataset.sample.queries[`en_${form}`] || dataset.sample.queries[`fr_${form}`]}</p>
                ))}
              </div>
              <div>
                <span className="kind">GROUND TRUTH</span>
                <p><span className="form">Expected answer</span>{dataset.sample.answer}</p>
                <p><span className="form">Verbatim quote</span><em>“{dataset.sample.evidence}”</em></p>
              </div>
            </div>
          </Reveal>
        </Section>

        <Section
          id="scale"
          tab="E1"
          title="The more manuals, the less it finds"
          lede={`For a question that names no vehicle, the best retriever finds the right passage ${pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'))} of the time when it only searches the right manual, ${pct(value(R.hybrid, 'native_plain', 'hard', 5, 'chunk_hit_5'))} with 5 manuals of the same brand, and ${pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'))} across all ${maxN}. Switch to “Model” to watch name routing cancel the effect of size.`}
        >
          <Reveal className="panel">
            <div className="controls">
              <span className="control-label">Measure</span>
              <div className="seg">
                {METRICS.map(([key, label]) => (
                  <button key={key} type="button" aria-pressed={metric === key} onClick={() => setMetric(key)}>{label}</button>
                ))}
              </div>
              <span className="control-label">Question</span>
              <div className="seg">
                {VARIANTS.map(([key, label]) => (
                  <button key={key} type="button" aria-pressed={variant === key} onClick={() => setVariant(key)}>{label}</button>
                ))}
              </div>
              <span className="control-label">Distractors</span>
              <div className="seg">
                <button type="button" aria-pressed={strategy === 'hard'} onClick={() => setStrategy('hard')}>Same brand</button>
                <button type="button" aria-pressed={strategy === 'random'} onClick={() => setStrategy('random')}>Random</button>
              </div>
            </div>
            <div className="legend">
              {series.map((s) => <span key={s.label}><i style={{ background: s.color }} />{s.label}</span>)}
            </div>
            <LineChart
              key={`${metric}-${variant}-${strategy}`}
              series={series}
              animate={!still}
              xLabel="manuals searched (log scale)"
              yLabel={metric === 'chunk_hit_5' ? 'right passage in the top 5' : 'right manual at rank 1'}
            />
          </Reveal>
          <p className="caption">The manual holding the answer plus N−1 distractors (5 draws per size). Bands show the 95% confidence interval; hover for values.</p>
          <Reveal className="table-wrap">
            <table>
              <thead><tr><th>Technique</th>{tiers.map((n) => <th key={n} className="num">{n}</th>)}</tr></thead>
              <tbody>
                {e1.retrievers.map((r) => (
                  <tr key={r.spec}>
                    <td>{labelOf(r.spec)}</td>
                    {tiers.map((n) => <td key={n} className="num">{pctNum(value(r.spec, variant, strategy, n, metric))}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>
        </Section>

        <Section id="techniques" tab="E2" title="Which techniques hold up at full scale">
          {!e2 ? (
            <Reveal><div className="note">The full comparison (rerankers included) is still running. It will appear here at the next results build.</div></Reveal>
          ) : (
            <Reveal>
              <div className="controls">
                <span className="control-label">Searched</span>
                <div className="seg">
                  <button type="button" aria-pressed={scope === 'global'} onClick={() => setScope('global')}>All manuals</button>
                  <button type="button" aria-pressed={scope === 'vehicle'} onClick={() => setScope('vehicle')}>Inside the vehicle</button>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Technique</th>
                      <th className="num">No vehicle</th><th className="num">Model</th>
                      <th className="num">Full name</th><th className="num">Other language</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const metricKey = scope === 'global' ? 'doc_hit_1' : 'chunk_hit_5'
                      const refVariant = scope === 'global' ? 'native_model' : 'native_plain'
                      const specs = [...new Set(e2.rows.map((r) => r.retriever))].sort((a, b) => {
                        const ref = (spec) => e2.rows.find((r) => r.retriever === spec && r.variant === refVariant && r.scope === scope)?.[metricKey] ?? 0
                        return ref(b) - ref(a)
                      })
                      return specs.map((spec, index) => {
                        const row = (v) => e2.rows.find((r) => r.retriever === spec && r.variant === v && r.scope === scope)
                        return (
                          <tr key={spec} className={index === 0 ? 'best' : ''}>
                            <td title={spec}>{labelOf(spec)}</td>
                            {['native_plain', 'native_model', 'native_full', 'cross_plain'].map((v) => {
                              const cell = row(v)
                              return (
                                <td key={v} className="num">
                                  {pctNum(cell?.[metricKey])}
                                  {cell && <span className="ci">{pctNum(cell[`${metricKey}_lo`], 0)}–{pctNum(cell[`${metricKey}_hi`], 0)}</span>}
                                </td>
                              )
                            })}
                          </tr>
                        )
                      })
                    })()}
                  </tbody>
                </table>
              </div>
              <p className="caption">
                {scope === 'global' ? 'Right manual at rank 1, searching all manuals.' : 'Right passage in the top 5, searching the vehicle’s own manuals.'}
                {' '}95% confidence intervals in small type. Cross-encoder reranking adds roughly 1.5 s per question.
              </p>
            </Reveal>
          )}
        </Section>

        <Section
          id="clarify"
          tab="E4"
          title="Asking beats guessing"
          lede={`“How do I change my battery?” has no single answer but ${corpus.vehicles}, one per vehicle. On questions that name no vehicle, never asking gets the right manual ${pct(byVariant('never', 'native_plain')?.doc_hit_1)} of the time; a single clarifying question takes it to ${pct(byVariant('name_rule', 'native_plain')?.doc_hit_1)}.`}
        >
          <Reveal className="panel">
            <ParetoChart policies={mainPolicies} sweep={sweep} labels={POLICY_LABEL} animate={!still} />
          </Reveal>
          <p className="caption">Simulated dialogues: a simulated user answers with their real vehicle. Bars are 95% confidence intervals; the dashed line is the learned detector at different thresholds.</p>

          <Reveal className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Policy</th><th className="num">Right manual</th><th className="num">Right passage</th>
                  <th className="num">Questions / query</th><th className="num">Missed</th><th className="num">Unnecessary</th>
                </tr>
              </thead>
              <tbody>
                {[...mainPolicies, ...sweep.filter((p) => p.policy.endsWith('0.8'))].map((p) => (
                  <tr key={p.policy} className={p.policy === 'name_rule' ? 'best' : ''}>
                    <td>{POLICY_LABEL[p.policy] || p.policy.replace('classifier@', 'Detector, threshold ')}</td>
                    <td className="num">{pctNum(p.doc_hit_1)}<span className="ci">{pctNum(p.doc_hit_1_lo, 0)}–{pctNum(p.doc_hit_1_hi, 0)}</span></td>
                    <td className="num">{pctNum(p.chunk_hit_5)}<span className="ci">{pctNum(p.chunk_hit_5_lo, 0)}–{pctNum(p.chunk_hit_5_hi, 0)}</span></td>
                    <td className="num">{dec(p.avg_turns)}</td>
                    <td className="num">{pctNum(p.missed_clarification, 0)}</td>
                    <td className="num">{pctNum(p.unnecessary_clarification, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>

          <Reveal>
            <h3>Spotting ambiguity: yes. Knowing whether it matters: no.</h3>
            <p>
              Signals computed without any LLM detect very well that a question names no vehicle
              (detector: AUC <strong>{dec(e4.detection.classifier.roc_auc)}</strong>, recall {pct(e4.detection.classifier['recall@0.5'])}).
              But among the {intEn(genericity.n_test)} ambiguous questions they cannot tell whether the answer actually
              changes from one vehicle to another: AUC <strong>{dec(genericity.classifier_auc)}</strong>, barely above chance.
              That is the line where an LLM becomes necessary.
            </p>
          </Reveal>
          <Reveal className="panel">
            <div className="legend">
              <span><i style={{ background: SERIES[0] }} />Detecting that the vehicle is missing</span>
              <span><i style={{ background: SERIES[1] }} />Detecting whether the answer depends on it</span>
            </div>
            <SignalBars rows={e4.signals.filter((s) => s.generic_auc != null && SIGNAL_NAME[s.signal])} names={SIGNAL_NAME} animate={!still} />
          </Reveal>

          <Reveal>
            <h3>Decisions on real questions</h3>
            <p>{e4.examples.length} hand-written questions with the expected decision. The system decides correctly in <strong>{okExamples} of {e4.examples.length}</strong> cases.</p>
          </Reveal>
          <Reveal className="table-wrap">
            <table className="examples">
              <thead><tr><th>Question</th><th>Expected</th><th>Decision</th><th>Question asked, or reason</th></tr></thead>
              <tbody>
                {e4.examples.map((example) => {
                  const ok = example.correct_action === true || example.correct_action === 'True'
                  return (
                    <tr key={example.id} className={ok ? '' : 'wrong'}>
                      <td>{example.query}</td>
                      <td><span className={`pill ${example.expected}`}>{ACTION_LABEL[example.expected]}</span></td>
                      <td><span className={`pill ${example.predicted}`}>{ACTION_LABEL[example.predicted]}</span>{!ok && <span className="wrong-flag">wrong</span>}</td>
                      <td>
                        {example.predicted === 'clarify' ? (
                          <>{example.question}<div className="options">{String(example.options).split(' | ').join(' · ')}</div></>
                        ) : example.predicted === 'answer' ? (
                          <span className="mono">{example.top_manual} · page {example.top_page}</span>
                        ) : readableReason(example.reason)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Reveal>

          <Reveal>
            <h3>Simulated dialogues</h3>
            <div className="dialogues">
              {e4.dialogues.map((dialogue) => (
                <article key={dialogue.query}>
                  <span className="kind">
                    QUESTION {dialogue.variant === 'native_plain' ? 'WITHOUT VEHICLE' : dialogue.variant === 'native_brand' ? 'WITH THE BRAND' : 'WITH THE MODEL'}
                  </span>
                  <p className="say user">{dialogue.query}</p>
                  {dialogue.turns.map((turn) => (
                    <div key={turn.q}>
                      <p className="say bot">{turn.q}</p>
                      <div className="chips">{turn.options.map((option) => <span key={option}>{option}</span>)}</div>
                      <p className="say user">{turn.a}</p>
                    </div>
                  ))}
                  <p className="outcome">Retrieved: <span className="mono">{dialogue.top_manual} · page {dialogue.top_page}</span>{dialogue.doc_ok ? ' — right manual' : ''}</p>
                </article>
              ))}
            </div>
          </Reveal>
        </Section>

        <Section id="method" tab="METHOD" title="Method and limits">
          <Reveal>
            <ul className="method">
              <li><strong>Metrics.</strong> Right manual at rank 1, right passage among the top 5 (the ones sent to the LLM), nDCG@10, confusions with a same-brand manual. A passage counts as right when it contains the ground-truth quote; the computation is cross-checked against <code>ranx</code>.</li>
              <li><strong>Statistics.</strong> The question is the unit of analysis. 95% confidence intervals (Wilson for proportions, bootstrap otherwise); systems are compared with a paired randomization test and Holm correction.</li>
              <li><strong>Protocol.</strong> Settings are chosen on the <em>dev</em> split; every number published here comes from the <em>test</em> split.</li>
              <li><strong>Limits.</strong> The question set is partial and synthetic; the production retriever (Gemini embeddings) and the LLM answering step are not measured yet; the simulated user always knows their exact vehicle.</li>
            </ul>
            <p className="footer-note">
              Generated from <code>research/results</code> · dataset <code>{dataset.name}</code> ·
              {' '}{intEn(corpus.chunks)} passages · provisional figures.
            </p>
          </Reveal>
        </Section>
      </main>
    </div>
  )
}
