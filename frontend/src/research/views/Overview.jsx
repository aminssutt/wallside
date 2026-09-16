import { motion as Motion } from 'framer-motion'
import { dec, intEn, pct } from '../format'
import { FAMILIES, R } from '../meta'

/** Landing page: what the study asks, how it is measured, and which methods are compared. */
export default function Overview({ data, still, go }) {
  const { corpus, dataset, e1, e4 } = data
  const maxN = Math.max(...e1.rows.map((r) => r.n))
  const value = (retriever, variant, strategy, n, metric) =>
    e1.rows.find((r) => r.retriever === retriever && r.variant === variant && r.strategy === strategy && r.n === n)?.[metric]
  const byVariant = (name, variant) =>
    e4.by_variant.find((p) => p.policy === name && p.variant === variant && ['none', 'direct'].includes(p.strategy))
  const nameRule = e4.policies.find((p) => p.policy === 'name_rule' && p.strategy === 'direct')

  const rise = still ? {} : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } }
  const step = (i) => ({ duration: 0.5, delay: still ? 0 : 0.06 * i, ease: [0.22, 0.61, 0.36, 1] })

  const readouts = [
    {
      from: pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'), 0),
      to: pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'), 0),
      caption: `right passage found searching 1 manual, then all ${maxN}`,
    },
    {
      from: pct(value(R.hybrid, 'native_model', 'hard', maxN, 'doc_hit_1'), 0),
      to: pct(value(R.router, 'native_model', 'hard', maxN, 'doc_hit_1'), 0),
      caption: 'right manual when the question names the model: search alone, then name routing',
    },
    {
      from: pct(byVariant('never', 'native_plain')?.doc_hit_1, 0),
      to: pct(byVariant('name_rule', 'native_plain')?.doc_hit_1, 0),
      caption: `right manual with no vehicle named: guessing, then ${dec(nameRule?.avg_turns)} clarifying question`,
    },
  ]

  return (
    <article className="view">
      <Motion.p className="eyebrow" {...rise} transition={step(0)}>
        <span>Retrieval over {corpus.manuals} car owner manuals</span>
        <span className="flag">Provisional results · partial question set</span>
      </Motion.p>
      <Motion.h1 {...rise} transition={step(1)}>Finding the right manual</Motion.h1>
      <Motion.p className="lede" {...rise} transition={step(2)}>
        An assistant answering from a library of {corpus.manuals} owner manuals has to solve two problems before it
        can say anything useful: <strong>which vehicle</strong> the question is about, and <strong>which page</strong>
        {' '}of that vehicle’s manual holds the answer. This study measures, on {intEn(corpus.chunks)} real passages,
        how well retrieval alone can do that — how much accuracy the library size costs, which methods survive at
        full scale, and when the system should stop guessing the vehicle and simply ask.
      </Motion.p>

      <Motion.div className="readouts" {...rise} transition={step(3)}>
        {readouts.map((item) => (
          <div className="readout" key={item.caption}>
            <p className="readout-figure"><span>{item.from}</span><i>→</i><b>{item.to}</b></p>
            <p className="readout-caption">{item.caption}</p>
          </div>
        ))}
      </Motion.div>

      <Motion.section {...rise} transition={step(4)}>
        <h2 className="kicker">The three questions</h2>
        <div className="cards three">
          <a className="card" href="#/scale" onClick={go('scale')}>
            <span className="card-tab">E1</span>
            <h3>Does size break it?</h3>
            <p>
              The same question is answered from 1, 2, 5, 10, 20, 50, 100 and {maxN} manuals. Distractors are drawn
              either at random or from the same brand — the lookalike case.
            </p>
            <span className="card-go">See the curve</span>
          </a>
          <a className="card" href="#/methods" onClick={go('methods')}>
            <span className="card-tab">E2</span>
            <h3>Which method wins?</h3>
            <p>
              Eighteen retrieval configurations — keywords, embeddings, fusion, routing, reranking — measured on the
              same questions, each one described in full.
            </p>
            <span className="card-go">Compare the methods</span>
          </a>
          <a className="card" href="#/clarify" onClick={go('clarify')}>
            <span className="card-tab">E4</span>
            <h3>When should it ask?</h3>
            <p>
              “How do I change my battery?” has {corpus.vehicles} different answers, one per vehicle. No retriever can
              guess it. We measure what one clarifying question buys, and what it costs.
            </p>
            <span className="card-go">See the dialogues</span>
          </a>
        </div>
      </Motion.section>

      <Motion.section {...rise} transition={step(5)}>
        <h2 className="kicker">How it is evaluated</h2>
        <ol className="steps">
          <li>
            <div>
              <h3>An exam with a known answer page</h3>
              <p>
                For each passage, a Gemini model writes an owner-style question, its answer, and a{' '}
                <strong>verbatim quote</strong> from that passage. The question is kept only if the quote really appears
                there — so the correct manual and the correct page are known, not judged. Each question exists in eight
                forms: French or English × (no vehicle, brand, model, full name).
              </p>
            </div>
          </li>
          <li>
            <div>
              <h3>Two separate scores</h3>
              <p>
                <strong>Right manual at rank 1</strong> — did the top hit come from the right vehicle?{' '}
                <strong>Right passage in the top 5</strong> — is the quoted passage among the five sent to the LLM?
                nDCG@10 and same-brand confusions are recorded alongside. A passage counts as right only when it
                contains the ground-truth quote.
              </p>
            </div>
          </li>
          <li>
            <div>
              <h3>Numbers you can argue with</h3>
              <p>
                Every figure carries a 95% confidence interval, the question is the unit of analysis, settings are
                chosen on a dev split and reported on a held-out test split, and methods are compared with a paired
                randomization test. The metric code is cross-checked against <code>ranx</code>.
              </p>
            </div>
          </li>
        </ol>
      </Motion.section>

      <Motion.section {...rise} transition={step(6)}>
        <h2 className="kicker">The five families of method compared</h2>
        <div className="cards families">
          {FAMILIES.map((family) => (
            <div className="family" key={family.key}>
              <span className={`badge ${family.key}`}>{family.title}</span>
              <p>{family.line}</p>
            </div>
          ))}
        </div>
        <p className="after">
          <a href="#/methods" onClick={go('methods')}>Every method, with how it works and what it scored →</a>
        </p>
      </Motion.section>

      <Motion.p className="footer-note" {...rise} transition={step(7)}>
        {intEn(dataset.questions)} questions over {dataset.manuals} manuals ({dataset.splits.test} test,{' '}
        {dataset.splits.dev} dev) · dataset <code>{dataset.name}</code> · figures provisional while the full question
        set is being generated.
      </Motion.p>
    </article>
  )
}
