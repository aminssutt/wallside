import { useId, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { SERIES, dec, pct, pctNum } from './format'

/**
 * SVG charts for the research results, drawn from the experiment data.
 * Categorical colours come from the validated palette used in the report figures, in fixed slot order.
 */
/** Line chart with confidence bands, log-x, end labels and a crosshair tooltip. */
export function LineChart({ series, xLabel, yLabel, height = 360, animate = true }) {
  const [hover, setHover] = useState(null)
  const titleId = useId()
  const W = 780
  const M = { top: 16, right: 168, bottom: 48, left: 54 }
  const xs = useMemo(
    () => [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b),
    [series],
  )
  if (!xs.length) return null
  const lx = (x) => Math.log(x)
  const [x0, x1] = [lx(xs[0]), lx(xs[xs.length - 1])]
  const X = (x) => M.left + ((lx(x) - x0) / (x1 - x0 || 1)) * (W - M.left - M.right)
  const Y = (y) => M.top + (1 - y) * (height - M.top - M.bottom)

  const ends = series
    .map((s) => {
      const last = [...s.points].reverse().find((p) => p.y != null)
      return last ? { label: s.short || s.label, color: s.color, y: Y(last.y), x: X(last.x) } : null
    })
    .filter(Boolean)
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i += 1) {
    if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15
  }

  const nearest = (event) => {
    const box = event.currentTarget.getBoundingClientRect()
    const px = ((event.clientX - box.left) / box.width) * W
    setHover(xs.reduce((a, b) => (Math.abs(X(b) - px) < Math.abs(X(a) - px) ? b : a)))
  }

  return (
    <div className="chart" onPointerLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-labelledby={titleId}>
        <title id={titleId}>{yLabel}</title>
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((v) => (
          <g key={v}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={Y(v)} y2={Y(v)} />
            <text className="tick" x={M.left - 8} y={Y(v) + 4} textAnchor="end">{pctNum(v, 0)}</text>
          </g>
        ))}
        {xs.map((x) => (
          <text key={x} className="tick" x={X(x)} y={height - M.bottom + 18} textAnchor="middle">{x}</text>
        ))}
        <text className="axis" x={(M.left + W - M.right) / 2} y={height - 8} textAnchor="middle">{xLabel}</text>
        <text className="axis" x={16} y={M.top + (height - M.top - M.bottom) / 2}
              transform={`rotate(-90 16 ${M.top + (height - M.top - M.bottom) / 2})`} textAnchor="middle">{yLabel}</text>

        {series.map((s) => {
          const pts = s.points.filter((p) => p.y != null)
          if (pts.length < 2 || pts[0].lo == null) return null
          const band = pts.map((p) => `${X(p.x)},${Y(p.hi)}`)
            .concat([...pts].reverse().map((p) => `${X(p.x)},${Y(p.lo)}`)).join(' ')
          return (
            <motion.polygon
              key={`${s.label}-band`} points={band} fill={s.color}
              initial={animate ? { opacity: 0 } : false}
              animate={animate ? { opacity: 0.14 } : undefined}
              transition={{ duration: 0.7, delay: 0.3 }}
              opacity={animate ? undefined : 0.14}
            />
          )
        })}
        {series.map((s) => {
          const pts = s.points.filter((p) => p.y != null)
          return (
            <g key={s.label}>
              <motion.polyline
                points={pts.map((p) => `${X(p.x)},${Y(p.y)}`).join(' ')}
                fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round"
                initial={animate ? { pathLength: 0 } : false}
                animate={animate ? { pathLength: 1 } : undefined}
                transition={{ duration: 0.9, ease: 'easeOut' }}
              />
              {pts.map((p, i) => (
                <motion.circle
                  key={p.x} cx={X(p.x)} cy={Y(p.y)} r={hover === p.x ? 5.5 : 4}
                  fill={s.color} stroke="var(--bg-primary)" strokeWidth="2"
                  initial={animate ? { opacity: 0, scale: 0.6 } : false}
                  animate={animate ? { opacity: 1, scale: 1 } : undefined}
                  transition={{ duration: 0.3, delay: animate ? 0.25 + i * 0.05 : 0 }}
                />
              ))}
            </g>
          )
        })}
        {ends.map((e) => (
          <g key={e.label}>
            <line x1={e.x + 6} x2={e.x + 14} y1={e.y} y2={e.y} stroke={e.color} strokeWidth="2" />
            <text className="end-label" x={e.x + 18} y={e.y + 4}>{e.label}</text>
          </g>
        ))}
        {hover != null && <line className="crosshair" x1={X(hover)} x2={X(hover)} y1={M.top} y2={height - M.bottom} />}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={height - M.top - M.bottom}
              fill="transparent" onPointerMove={nearest} />
      </svg>
      {hover != null && (
        <div className="tip" style={{ left: `${(X(hover) / W) * 100}%` }}>
          <b>{hover} manual{hover > 1 ? 's' : ''}</b>
          {series
            .map((s) => ({ s, p: s.points.find((p) => p.x === hover) }))
            .filter((row) => row.p?.y != null)
            .sort((a, b) => b.p.y - a.p.y)
            .map(({ s, p }) => (
              <div className="tip-row" key={s.label}>
                <i style={{ background: s.color }} />
                <span>{s.label}</span>
                <span className="tip-value">{pct(p.y)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

/** Accuracy against the number of clarifying questions asked (policies + a detector threshold sweep). */
export function ParetoChart({ policies, sweep, labels, height = 330, animate = true }) {
  const titleId = useId()
  const W = 780
  const M = { top: 16, right: 30, bottom: 48, left: 54 }
  const xMax = Math.max(1.1, ...[...policies, ...sweep].map((p) => p.avg_turns)) * 1.08
  const X = (x) => M.left + (x / xMax) * (W - M.left - M.right)
  const Y = (y) => M.top + (1 - y) * (height - M.top - M.bottom)
  const marks = { never: '■', always: '▲', name_rule: '◆', oracle: '★' }

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-labelledby={titleId}>
        <title id={titleId}>Accuracy against the number of questions asked</title>
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((v) => (
          <g key={v}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={Y(v)} y2={Y(v)} />
            <text className="tick" x={M.left - 8} y={Y(v) + 4} textAnchor="end">{pctNum(v, 0)}</text>
          </g>
        ))}
        {[0, 0.2, 0.4, 0.6, 0.8, 1.0].filter((v) => v <= xMax).map((v) => (
          <text key={v} className="tick" x={X(v)} y={height - M.bottom + 18} textAnchor="middle">{dec(v, 1)}</text>
        ))}
        <text className="axis" x={(M.left + W - M.right) / 2} y={height - 8} textAnchor="middle">clarifying questions per query</text>
        <text className="axis" x={16} y={height / 2} transform={`rotate(-90 16 ${height / 2})`} textAnchor="middle">right manual at rank 1</text>

        <motion.polyline points={sweep.map((p) => `${X(p.avg_turns)},${Y(p.doc_hit_1)}`).join(' ')}
                  fill="none" stroke={SERIES[4]} strokeWidth="2" strokeDasharray="5 4"
                  initial={animate ? { pathLength: 0 } : false}
                  whileInView={animate ? { pathLength: 1 } : undefined}
                  viewport={{ once: true }}
                  transition={{ duration: 0.9, ease: 'easeOut' }} />
        {sweep.map((p) => (
          <circle key={p.policy} cx={X(p.avg_turns)} cy={Y(p.doc_hit_1)} r="4" fill={SERIES[4]} stroke="var(--bg-primary)" strokeWidth="2" />
        ))}
        {policies.map((p, index) => (
          <motion.g key={p.policy}
            initial={animate ? { opacity: 0, scale: 0.85 } : false}
            whileInView={animate ? { opacity: 1, scale: 1 } : undefined}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.25 + index * 0.08 }}
            style={{ transformOrigin: `${X(p.avg_turns)}px ${Y(p.doc_hit_1)}px` }}>
            <line x1={X(p.avg_turns)} x2={X(p.avg_turns)} y1={Y(p.doc_hit_1_lo)} y2={Y(p.doc_hit_1_hi)} stroke={SERIES[index]} strokeWidth="2" />
            <circle cx={X(p.avg_turns)} cy={Y(p.doc_hit_1)} r="7" fill={SERIES[index]} stroke="var(--bg-primary)" strokeWidth="2" />
            <text className="end-label" x={X(p.avg_turns) + (p.avg_turns > xMax * 0.75 ? -12 : 12)}
                  y={Y(p.doc_hit_1) - 12} textAnchor={p.avg_turns > xMax * 0.75 ? 'end' : 'start'}>
              {marks[p.policy] || '●'} {labels[p.policy]} · {pct(p.doc_hit_1, 0)}
            </text>
          </motion.g>
        ))}
      </svg>
    </div>
  )
}

/** Paired bars: how well each signal detects ambiguity, and whether the answer depends on the vehicle. */
export function SignalBars({ rows, names, animate = true }) {
  const titleId = useId()
  const W = 780
  const rowH = 36
  const M = { top: 10, right: 62, bottom: 36, left: 210 }
  const height = M.top + M.bottom + rowH * rows.length
  const X = (v) => M.left + ((v - 0.5) / 0.5) * (W - M.left - M.right)
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-labelledby={titleId}>
        <title id={titleId}>Detection power of each signal</title>
        {[0.5, 0.6, 0.7, 0.8, 0.9, 1].map((v) => (
          <g key={v}>
            <line className="grid" x1={X(v)} x2={X(v)} y1={M.top} y2={height - M.bottom} />
            <text className="tick" x={X(v)} y={height - M.bottom + 16} textAnchor="middle">{dec(v, 1)}</text>
          </g>
        ))}
        <text className="axis" x={(M.left + W - M.right) / 2} y={height - 4} textAnchor="middle">AUC (0.5 = chance)</text>
        {rows.map((row, index) => {
          const y = M.top + index * rowH
          return (
            <g key={row.signal}>
              <text className="row-label" x={M.left - 10} y={y + rowH / 2 + 4} textAnchor="end">{names[row.signal] || row.signal}</text>
              {[[row.auc, SERIES[0], 5], [row.generic_auc, SERIES[1], 18]].map(([value, color, offset]) => (
                <g key={offset}>
                  <motion.rect
                    x={X(0.5)} y={y + offset} height="11" rx="2" fill={color}
                    initial={animate ? { width: 0 } : false}
                    whileInView={animate ? { width: Math.max(1, X(Math.max(value, 0.5)) - X(0.5)) } : undefined}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: 0.1 + index * 0.05, ease: 'easeOut' }}
                    width={animate ? undefined : Math.max(1, X(Math.max(value, 0.5)) - X(0.5))}
                  />
                  <text className="tick" x={X(Math.max(value, 0.5)) + 6} y={y + offset + 10}>{dec(value)}</text>
                </g>
              ))}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
