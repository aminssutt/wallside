import { useMemo, useState } from 'react'
import { LineChart } from '../charts'
import { SERIES, pct, pctNum } from '../format'
import { METRICS, R, SHORT, VARIANTS, labelOf } from '../meta'

/** E1: accuracy as a function of how many manuals are searched. */
export default function Scale({ data, still }) {
  const { e1 } = data
  const [metric, setMetric] = useState('chunk_hit_5')
  const [variant, setVariant] = useState('native_plain')
  const [strategy, setStrategy] = useState('hard')

  const tiers = useMemo(() => [...new Set(e1.rows.map((r) => r.n))].sort((a, b) => a - b), [e1])
  const maxN = tiers[tiers.length - 1]
  const value = (retriever, v, s, n, m) =>
    e1.rows.find((r) => r.retriever === retriever && r.variant === v && r.strategy === s && r.n === n)?.[m]

  const series = useMemo(
    () =>
      e1.retrievers.map((r, index) => ({
        label: labelOf(r.spec),
        short: SHORT[r.spec] || r.label,
        color: SERIES[index % SERIES.length],
        points: e1.rows
          .filter((row) => row.retriever === r.spec && row.variant === variant && row.strategy === strategy)
          .sort((a, b) => a.n - b.n)
          .map((row) => ({ x: row.n, y: row[metric], lo: row[`${metric}_lo`], hi: row[`${metric}_hi`] })),
      })),
    [e1, metric, strategy, variant],
  )

  return (
    <article className="view">
      <span className="tab">E1 · CORPUS SIZE</span>
      <h1>The more manuals, the less it finds</h1>
      <p className="lede">
        For a question that names no vehicle, the hybrid retriever finds the right passage{' '}
        <strong>{pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'))}</strong> of the time when it only
        searches the right manual, <strong>{pct(value(R.hybrid, 'native_plain', 'hard', 5, 'chunk_hit_5'))}</strong>{' '}
        among 5 manuals of the same brand, and{' '}
        <strong>{pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'))}</strong> across all {maxN}. Switch
        the question to <em>Model</em> and watch name routing cancel the effect of size entirely.
      </p>

      <div className="panel">
        <div className="controls">
          <div className="control">
            <span className="control-label">Measure</span>
            <div className="seg">
              {METRICS.map(([key, label]) => (
                <button key={key} type="button" aria-pressed={metric === key} onClick={() => setMetric(key)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="control">
            <span className="control-label">Question says</span>
            <div className="seg">
              {VARIANTS.map(([key, label]) => (
                <button key={key} type="button" aria-pressed={variant === key} onClick={() => setVariant(key)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="control">
            <span className="control-label">Distractors</span>
            <div className="seg">
              <button type="button" aria-pressed={strategy === 'hard'} onClick={() => setStrategy('hard')}>Same brand</button>
              <button type="button" aria-pressed={strategy === 'random'} onClick={() => setStrategy('random')}>Random</button>
            </div>
          </div>
        </div>
        <div className="legend">
          {series.map((s) => <span key={s.label}><i style={{ background: s.color }} />{s.label}</span>)}
        </div>
        <LineChart
          key={`${metric}-${variant}-${strategy}`}
          series={series}
          animate={!still}
          height={320}
          xLabel="manuals searched (log scale)"
          yLabel={metric === 'chunk_hit_5' ? 'right passage in the top 5' : 'right manual at rank 1'}
        />
      </div>
      <p className="caption">
        Each point: the manual holding the answer plus N−1 distractors, averaged over 5 draws. Bands are 95%
        confidence intervals over questions; hover for values.
      </p>

      <details className="drawer">
        <summary>The same numbers as a table</summary>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Method</th>{tiers.map((n) => <th key={n} className="num">{n}</th>)}</tr></thead>
            <tbody>
              {e1.retrievers.map((r) => (
                <tr key={r.spec}>
                  <td>{labelOf(r.spec)}</td>
                  {tiers.map((n) => <td key={n} className="num">{pctNum(value(r.spec, variant, strategy, n, metric))}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </article>
  )
}
