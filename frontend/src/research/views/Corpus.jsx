import { intEn, pct } from '../format'

/** What the system searches, and how the exam that grades it was built. */
export default function Corpus({ data }) {
  const { corpus, dataset } = data
  const sample = dataset.sample
  const lang = sample.queries.en_plain ? 'en' : 'fr'
  const audit = dataset.audit
  const audited = audit && audit.supported + audit.supported_with_extra_detail + audit.unsupported

  const facts = [
    [corpus.manuals, 'manuals'],
    [intEn(corpus.chunks), 'passages'],
    [intEn(corpus.pages), 'pages'],
    [corpus.vehicles, 'vehicles'],
    [corpus.brands, 'brands'],
    [`${corpus.lang_fr} / ${corpus.lang_en}`, 'French / English'],
  ]

  return (
    <article className="view">
      <span className="tab">DATA · CORPUS</span>
      <h1>The library and the exam</h1>
      <p className="lede">
        The corpus is extracted verbatim from the production indexes — the same chunks, the same vectors — so the
        measurements describe the real system, not a rebuilt approximation of it.
      </p>

      <div className="facts">
        {facts.map(([value, label]) => (
          <div key={label}><b>{value}</b><span>{label}</span></div>
        ))}
      </div>

      <div className="split">
        <section>
          <h2 className="kicker">Defects found in the data</h2>
          <ul className="findings">
            <li>
              <span className="where">EXTRACTION</span>
              <span>
                <strong>{intEn(corpus.garbled_chunks)} unreadable passages</strong> —{' '}
                {corpus.garbled_manuals.map((m) => `${m.name} (${pct(m.share, 0)})`).join(', ')}. The PDF extractor
                mis-decoded those embedded fonts. Fixed by falling back to PyMuPDF; re-indexing still to do.
              </span>
            </li>
            <li>
              <span className="where">DUPLICATES</span>
              <span>
                <strong>The same PDF indexed twice:</strong>{' '}
                {corpus.duplicates.map((d) => `${d.manual} = ${d.of}`).join(', ')}.
              </span>
            </li>
            <li>
              <span className="where">SHARED TEXT</span>
              <span>
                <strong>{intEn(corpus.shared_text_chunks)} passages</strong> are word-for-word identical to a passage
                in another manual — the “right document” is sometimes ambiguous by nature, so every metric is reported
                strict and lenient.
              </span>
            </li>
          </ul>
        </section>

        <section>
          <h2 className="kicker">How a question is made</h2>
          <p>
            A Gemini model (<code>{dataset.generator}</code>, a different generation from the one under test) reads one
            passage and writes a question an owner would ask, the answer, and a verbatim quote. The question is kept
            only if that quote is found again in the passage — the answer key is the text itself, not a judgement.
          </p>
          <div className="note">
            <strong>Partial set:</strong> {intEn(dataset.questions)} questions over {dataset.manuals} manuals
            ({dataset.splits.test} test, {dataset.splits.dev} dev), rebuilt from cache when the Gemini prepaid credits
            ran out. It covers mostly the first manuals alphabetically, so these figures are provisional.
            {audit && ` Independent audit of ${audited} random questions: ${audit.supported + audit.supported_with_extra_detail} answers supported by their quote, ${audit.unsupported} unsupported.`}
          </div>
        </section>
      </div>

      <h2 className="kicker">One question, eight forms</h2>
      <div className="sample">
        <div>
          <span className="kind">GENERATED · {sample.manual} · page {sample.page}</span>
          {[['No vehicle', 'plain'], ['Brand', 'brand'], ['Model', 'model'], ['Full name', 'full']].map(([label, form]) => (
            <p key={form}><span className="form">{label}</span>{sample.queries[`${lang}_${form}`]}</p>
          ))}
        </div>
        <div>
          <span className="kind">ANSWER KEY</span>
          <p><span className="form">Expected answer</span>{sample.answer}</p>
          <p><span className="form">Verbatim quote</span><em>“{sample.evidence}”</em></p>
        </div>
      </div>
      <p className="caption">
        The same question in four levels of vehicle detail, in both languages: that is how the study separates “the
        retriever cannot find the page” from “the question never said which car”.
      </p>
    </article>
  )
}
