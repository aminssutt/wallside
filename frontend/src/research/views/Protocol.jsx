import { intEn } from '../format'

/** How the evaluation is run: metrics, statistics, protocol, reproduction, limits. */
export default function Protocol({ data }) {
  const { corpus, dataset } = data

  const blocks = [
    {
      tab: '01',
      title: 'Metrics',
      body: (
        <ul>
          <li><strong>Right manual at rank 1</strong> (<code>doc_hit@1</code>) — the top hit comes from the vehicle the question is about.</li>
          <li><strong>Right passage in the top 5</strong> (<code>chunk_hit@5</code>) — the passage holding the ground-truth quote is among the five sent to the LLM.</li>
          <li><strong>nDCG@10</strong> and <strong>same-brand confusions</strong> are recorded alongside, to separate “wrong car” from “wrong page”.</li>
          <li>A passage counts as right only when it contains the verbatim quote. Because {intEn(corpus.shared_text_chunks)} passages are duplicated across manuals, every metric also has a lenient variant that accepts an identical passage from another manual.</li>
          <li>The whole metric implementation is cross-checked against the <code>ranx</code> library.</li>
        </ul>
      ),
    },
    {
      tab: '02',
      title: 'Statistics',
      body: (
        <ul>
          <li>The <strong>question</strong> is the unit of analysis; the random draws of distractor manuals are averaged within each question first.</li>
          <li>95% confidence intervals: Wilson for proportions, percentile bootstrap otherwise.</li>
          <li>Two methods are compared with a <strong>paired randomization test</strong> (sign-flip over questions), with Holm correction across the family of comparisons.</li>
        </ul>
      ),
    },
    {
      tab: '03',
      title: 'Protocol',
      body: (
        <ul>
          <li>Questions are split <strong>{dataset.splits.dev} dev / {dataset.splits.test} test</strong>. Fusion weights, routing rules and decision thresholds are chosen on dev; every number published here comes from test.</li>
          <li>Corpus-size conditions mask a single global index rather than rebuilding one per size, so BM25 statistics stay identical across conditions — a documented choice, not an accident.</li>
          <li>The off-topic threshold is calibrated on in-domain questions only (1st percentile of their similarity), never on the off-topic examples it is tested on.</li>
        </ul>
      ),
    },
    {
      tab: '04',
      title: 'Known limits',
      body: (
        <ul>
          <li><strong>Partial, synthetic question set.</strong> {intEn(dataset.questions)} questions over {dataset.manuals} of the {corpus.manuals} manuals, skewed toward the first ones alphabetically, to be redone in full.</li>
          <li><strong>The production embeddings are not measured yet.</strong> Encoding questions with <code>gemini-embedding-001</code> needs the API; results here use local models. The replica experiment is coded and ready.</li>
          <li><strong>The answering step is not measured yet.</strong> Whether the LLM cites the right page, and abstains when it should, is a separate experiment waiting on the same API.</li>
          <li><strong>The simulated user is ideal</strong> — they always know their exact vehicle, year and generation.</li>
          <li><strong>Genericity labels come from the generator itself</strong>, so “the answer depends on the vehicle” inherits that model’s judgement.</li>
        </ul>
      ),
    },
  ]

  return (
    <article className="view">
      <span className="tab">HOW · PROTOCOL</span>
      <h1>How the evaluation is run</h1>
      <p className="lede">
        Everything on this site is regenerated from the raw experiment outputs by one script — no figure is typed in by
        hand, and the whole pipeline reruns from the corpus with three commands.
      </p>

      <div className="protocol">
        {blocks.map((block) => (
          <section key={block.tab}>
            <span className="tab">{block.tab}</span>
            <h2>{block.title}</h2>
            {block.body}
          </section>
        ))}
      </div>

      <h2 className="kicker">Reproduce it</h2>
      <pre className="code">{`make corpus embed dataset
ragscale run configs/e1_scaling.yaml
ragscale run configs/e2_techniques.yaml
ragscale clarify configs/e4_clarification.yaml
python scripts/build_report.py --json ../frontend/public/research-results.json`}</pre>
      <p className="footer-note">
        Branch <code>research</code>, directory <code>research/</code> · dataset <code>{dataset.name}</code> ·{' '}
        {intEn(corpus.chunks)} passages · figures provisional.
      </p>
    </article>
  )
}
