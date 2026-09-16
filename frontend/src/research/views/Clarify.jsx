import { useState } from 'react'
import { ParetoChart, SignalBars } from '../charts'
import { SERIES, dec, intEn, pct, pctNum } from '../format'
import { ACTION_LABEL, POLICY_LABEL, SIGNAL_NAME, readableReason } from '../meta'

const TABS = [
  ['policies', 'Ask or guess'],
  ['signals', 'What the system can tell'],
  ['examples', 'Decisions on real questions'],
]

/** E4: when the question names no vehicle, answer / ask / abstain. */
export default function Clarify({ data, still }) {
  const { corpus, e4 } = data
  const [tab, setTab] = useState('policies')

  const policies = e4.policies.filter((p) => ['none', 'direct'].includes(p.strategy))
  const byVariant = (name, variant) =>
    e4.by_variant.find((p) => p.policy === name && p.variant === variant && ['none', 'direct'].includes(p.strategy))
  const sweep = policies.filter((p) => p.policy.startsWith('classifier')).sort((a, b) => a.avg_turns - b.avg_turns)
  const main = ['never', 'always', 'name_rule', 'oracle'].map((k) => policies.find((p) => p.policy === k)).filter(Boolean)
  const genericity = e4.detection.genericity_among_ambiguous || {}
  const okExamples = e4.examples.filter((e) => e.correct_action === true || e.correct_action === 'True').length

  return (
    <article className="view">
      <span className="tab">E4 · CLARIFICATION</span>
      <h1>Asking beats guessing</h1>
      <p className="lede">
        “How do I change my battery?” has no single answer but {corpus.vehicles}, one per vehicle. On questions that
        name no vehicle, never asking gets the right manual{' '}
        <strong>{pct(byVariant('never', 'native_plain')?.doc_hit_1)}</strong> of the time; a single clarifying question
        takes it to <strong>{pct(byVariant('name_rule', 'native_plain')?.doc_hit_1)}</strong>. The decision is
        three-way: <span className="pill answer">answer</span> <span className="pill clarify">ask</span>{' '}
        <span className="pill abstain">abstain</span>.
      </p>

      <div className="controls">
        <div className="seg">
          {TABS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={tab === key} onClick={() => setTab(key)}>{label}</button>
          ))}
        </div>
      </div>

      {tab === 'policies' && (
        <>
          <div className="panel">
            <ParetoChart policies={main} sweep={sweep} labels={POLICY_LABEL} animate={!still} height={300} />
          </div>
          <p className="caption">
            Simulated dialogues on the test split, pooled over all four question forms — the 18% → 97% headline is the
            harder subset that names no vehicle. The simulated user answers with their real vehicle, and that answer is
            used as a filter, never as extra query words. Bars are 95% confidence intervals; the dashed line is the
            learned detector swept across thresholds.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Policy</th><th className="num">Right manual</th><th className="num">Right passage</th>
                  <th className="num">Questions / query</th><th className="num">Missed</th><th className="num">Unnecessary</th>
                </tr>
              </thead>
              <tbody>
                {[...main, ...sweep.filter((p) => p.policy.endsWith('0.8'))].map((p) => (
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
          </div>
          <p className="caption">
            The winning rule needs no model: <strong>ask whenever the question names no vehicle</strong>, offering the
            three most likely vehicles plus free text.
          </p>
        </>
      )}

      {tab === 'signals' && (
        <>
          <p>
            Signals computed from the retrieval results alone — no LLM call — detect very well that a question names no
            vehicle (learned detector: AUC <strong>{dec(e4.detection.classifier.roc_auc)}</strong>, recall{' '}
            {pct(e4.detection.classifier['recall@0.5'])}). But among the {intEn(genericity.n_test)} ambiguous questions
            they cannot tell whether the answer actually changes from one vehicle to another: AUC{' '}
            <strong>{dec(genericity.classifier_auc)}</strong>, barely above chance. That is the exact line where an LLM
            becomes necessary — and why the system still asks about seat belts.
          </p>
          <div className="panel">
            <div className="legend">
              <span><i style={{ background: SERIES[0] }} />Detecting that the vehicle is missing</span>
              <span><i style={{ background: SERIES[1] }} />Detecting whether the answer depends on it</span>
            </div>
            <SignalBars rows={e4.signals.filter((s) => s.generic_auc != null && SIGNAL_NAME[s.signal])} names={SIGNAL_NAME} animate={!still} />
          </div>
          <p className="caption">Area under the ROC curve on the test split. 0.5 is chance, 1 is perfect.</p>
        </>
      )}

      {tab === 'examples' && (
        <>
          <p>
            {e4.examples.length} hand-written questions with the decision a human expects. The system decides correctly
            in <strong>{okExamples} of {e4.examples.length}</strong> cases; the misses are generic questions where it
            asks for a vehicle that would not change the answer.
          </p>
          <div className="table-wrap scroll">
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
                        ) : readableReason(example.reason, dec)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <h2 className="kicker">Simulated dialogues</h2>
          <div className="dialogues">
            {e4.dialogues.slice(0, 3).map((dialogue) => (
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
                <p className="outcome">
                  Retrieved: <span className="mono">{dialogue.top_manual} · page {dialogue.top_page}</span>
                  {dialogue.doc_ok ? ' — right manual' : ''}
                </p>
              </article>
            ))}
          </div>
        </>
      )}
    </article>
  )
}
