import { useEffect, useMemo, useState } from 'react'
import { LineChart, ParetoChart, SignalBars } from './charts'
import { SERIES, dec, intFr, pct, pctNum } from './format'
import './ResultsPage.css'

/**
 * Research results site: everything on this page is read from research-results.json, which is written by
 * research/scripts/build_report.py from the experiment outputs. No number is typed in by hand.
 */

const R = {
  bm25: 'bm25_stem',
  dense: 'dense:bge-m3',
  hybrid: 'wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)',
  ctx: 'wsum(bm25_stem+ctx,dense:bge-m3+ctx;w=0.3|0.7)',
  router: 'name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))',
  hnsw: 'hnsw(dense:bge-m3)',
}
const RETRIEVER_LABEL = {
  [R.bm25]: 'BM25 (mots-clés)',
  [R.dense]: 'bge-m3 (sens)',
  [R.hybrid]: 'Hybride 0,3 BM25 + 0,7 bge-m3',
  [R.ctx]: 'Hybride + en-têtes de document',
  [R.router]: 'Routage par nom + hybride',
  [R.hnsw]: 'bge-m3, index approximatif HNSW',
}
const RETRIEVER_SHORT = {
  [R.bm25]: 'BM25', [R.dense]: 'bge-m3', [R.hybrid]: 'hybride',
  [R.ctx]: '+ en-têtes', [R.router]: 'routage', [R.hnsw]: 'HNSW',
}
const VARIANTS = [
  ['native_plain', 'Sans véhicule'],
  ['native_brand', 'Marque'],
  ['native_model', 'Modèle'],
  ['native_full', 'Nom complet'],
]
const METRICS = [
  ['chunk_hit_5', 'Bon passage (top 5)'],
  ['doc_hit_1', 'Bon manuel (1er)'],
]
const POLICY_LABEL = {
  never: 'Ne jamais demander',
  always: 'Toujours demander',
  name_rule: 'Demander si aucun véhicule nommé',
  oracle: 'Oracle',
}
const SIGNAL_NAME = {
  vehicle_margin: 'écart 1er / 2e véhicule',
  passage_agreement: 'accord entre les passages',
  top1_vehicle_share: 'part du 1er véhicule',
  vehicle_entropy: 'dispersion entre véhicules',
  n_vehicles_top10: 'véhicules dans le top 10',
  n_brands_top10: 'marques dans le top 10',
  query_tokens: 'longueur de la question',
  mentions_brand: 'marque mentionnée',
}
const ACTION_LABEL = { answer: 'répondre', clarify: 'clarifier', abstain: "s'abstenir" }

/** The decision layer writes its reasons in English; show them in French. */
const translateReason = (reason) => {
  const brand = /no manual for brand '(.+)'/.exec(reason)
  if (brand) return `aucun manuel pour la marque ${brand[1].replace(/^./, (c) => c.toUpperCase())}`
  const offTopic = /off-topic \(max similarity ([\d.]+) < ([\d.]+)\)/.exec(reason)
  if (offTopic) return `hors sujet (similarité maximale ${dec(offTopic[1], 3)} < ${dec(offTopic[2], 3)})`
  const many = /(\d+|many) candidate vehicles \(p=([\d.]+)\)/.exec(reason)
  if (many) return `plusieurs véhicules possibles (p = ${dec(many[2])})`
  const versions = /(\d+) versions match the name/.exec(reason)
  if (versions) return `${versions[1]} versions portent ce nom`
  if (reason === 'one vehicle identified') return 'un seul véhicule identifié'
  return reason
}
const SECTIONS = [
  ['resume', '00', 'Résumé'],
  ['corpus', 'DATA', 'Corpus'],
  ['echelle', 'E1', 'Taille du corpus'],
  ['techniques', 'E2', 'Techniques'],
  ['clarification', 'E4', 'Clarification'],
  ['methode', 'MÉTH', 'Méthode'],
]

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

function Readout({ from, to, caption }) {
  return (
    <div className="readout">
      <p className="readout-figure"><span>{from}</span><i>→</i><b>{to}</b></p>
      <p className="readout-caption">{caption}</p>
    </div>
  )
}

function Section({ id, tab, title, lede, children }) {
  return (
    <section id={id}>
      <header className="section-head">
        <span className="tab">{tab}</span>
        <h2>{title}</h2>
        {lede && <p className="lede">{lede}</p>}
      </header>
      {children}
    </section>
  )
}

export default function ResultsPage() {
  const { data, failed } = useResults()
  const [metric, setMetric] = useState('chunk_hit_5')
  const [variant, setVariant] = useState('native_plain')
  const [strategy, setStrategy] = useState('hard')
  const [scope, setScope] = useState('global')

  useEffect(() => { document.title = 'Trouver le bon manuel — résultats de recherche' }, [])

  const e1 = data?.e1
  const maxN = useMemo(() => (e1 ? Math.max(...e1.rows.map((r) => r.n)) : 0), [e1])
  const tiers = useMemo(() => (e1 ? [...new Set(e1.rows.map((r) => r.n))].sort((a, b) => a - b) : []), [e1])
  const value = (retriever, v, s, n, m) =>
    e1?.rows.find((r) => r.retriever === retriever && r.variant === v && r.strategy === s && r.n === n)?.[m]

  const series = useMemo(() => {
    if (!e1) return []
    return e1.retrievers.map((r, index) => ({
      label: RETRIEVER_LABEL[r.spec] || r.label,
      short: RETRIEVER_SHORT[r.spec] || r.label,
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
        <p className="empty">Les résultats ne sont pas encore générés. Lancez <code>python scripts/build_report.py --json ../frontend/public/research-results.json</code> dans <code>research/</code>.</p>
      </main>
    )
  }
  if (!data) return <main className="results"><p className="empty">Chargement des résultats…</p></main>

  const { corpus, dataset, e2, e4 } = data
  const policies = e4.policies.filter((p) => ['none', 'direct'].includes(p.strategy))
  const policy = (name) => policies.find((p) => p.policy === name)
  const byVariant = (name, v) => e4.by_variant.find((p) => p.policy === name && p.variant === v && ['none', 'direct'].includes(p.strategy))
  const sweep = policies.filter((p) => p.policy.startsWith('classifier')).sort((a, b) => a.avg_turns - b.avg_turns)
  const mainPolicies = ['never', 'always', 'name_rule', 'oracle'].map(policy).filter(Boolean)
  const genericity = e4.detection.genericity_among_ambiguous || {}
  const okExamples = e4.examples.filter((e) => e.correct_action === true || e.correct_action === 'True').length

  return (
    <div className="results">
      <nav className="toc" aria-label="Sommaire">
        <ol>
          {SECTIONS.map(([id, tab, title]) => (
            <li key={id}><a href={`#${id}`}><span className="tab">{tab}</span>{title}</a></li>
          ))}
        </ol>
      </nav>

      <main>
        <header className="cover">
          <p className="eyebrow"><span>Recherche · RAG sur manuels automobiles</span><span className="flag">Résultats provisoires</span></p>
          <h1>Trouver le bon manuel</h1>
          <p className="lede">
            Un assistant qui répond à partir de {corpus.manuals} manuels doit d'abord trouver le bon document,
            puis la bonne page. Ce site mesure à quel point il y parvient quand la bibliothèque grandit,
            quelles techniques résistent, et quand il vaut mieux poser une question que deviner.
          </p>
          <div className="readouts">
            <Readout
              from={pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'), 0)}
              to={pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'), 0)}
              caption={`bon passage trouvé dans 1 manuel, puis dans ${maxN}, pour une question sans nom de véhicule`}
            />
            <Readout
              from={pct(value(R.hybrid, 'native_model', 'hard', maxN, 'doc_hit_1'), 0)}
              to={pct(value(R.router, 'native_model', 'hard', maxN, 'doc_hit_1'), 0)}
              caption={`bon manuel sur ${maxN}, question nommant le modèle : recherche seule, puis routage par nom`}
            />
            <Readout
              from={pct(byVariant('never', 'native_plain')?.doc_hit_1, 0)}
              to={pct(byVariant('name_rule', 'native_plain')?.doc_hit_1, 0)}
              caption={`bon manuel pour une question sans véhicule : sans clarification, puis avec ${dec(policy('name_rule')?.avg_turns)} question posée`}
            />
          </div>
        </header>

        <Section id="resume" tab="00" title="Ce que l'on mesure">
          <p>
            Pour chaque question, le système doit retrouver <strong>le bon manuel</strong> (quel véhicule) et
            <strong> le bon passage</strong> (quelle page). Ces deux niveaux sont mesurés séparément, avec des
            intervalles de confiance à 95 %, en faisant varier la taille du corpus fouillé, la technique de
            recherche, et l'information que la question donne sur le véhicule.
          </p>
          <div className="cards">
            <article><h3>E1 · Taille du corpus</h3><p>Combien perd-on en passant de 1 à {maxN} manuels, avec des distracteurs aléatoires ou de la même marque ?</p></article>
            <article><h3>E2 · Techniques</h3><p>Mots-clés, sens, hybrides, en-têtes de document, routage, reranking : laquelle tient à grande échelle ?</p></article>
            <article><h3>E4 · Clarification</h3><p>Quand la question ne nomme aucun véhicule, faut-il deviner ou demander ? Et que coûte une question ?</p></article>
          </div>
        </Section>

        <Section id="corpus" tab="DATA" title="Le corpus et l'examen"
                 lede={`Extrait à l'identique des index de production : ${corpus.manuals} manuels, ${intFr(corpus.chunks)} passages, ${intFr(corpus.pages)} pages, ${corpus.vehicles} véhicules, ${corpus.lang_fr} manuels en français et ${corpus.lang_en} en anglais.`}>
          <h3>Défauts de données trouvés en chemin</h3>
          <ul className="findings">
            <li>
              <span className="where">EXTRACTION PDF</span>
              <span><strong>{intFr(corpus.garbled_chunks)} passages illisibles</strong> — {corpus.garbled_manuals.map((m) => `${m.name} (${pct(m.share, 0)})`).join(', ')}. L'extracteur décodait mal ces polices ; correctif livré (bascule sur PyMuPDF), réindexation à faire.</span>
            </li>
            <li>
              <span className="where">DOUBLONS</span>
              <span><strong>Un même PDF indexé deux fois :</strong> {corpus.duplicates.map((d) => `${d.manual} = ${d.of}`).join(', ')}.</span>
            </li>
            <li>
              <span className="where">TEXTE PARTAGÉ</span>
              <span><strong>{intFr(corpus.shared_text_chunks)} passages</strong> ont un texte identique dans un autre manuel : le « bon document » est parfois ambigu par nature.</span>
            </li>
          </ul>

          <h3>L'examen : des questions dont on connaît la bonne page</h3>
          <p>
            Un modèle Gemini (<code>{dataset.generator}</code>, d'une autre génération que le modèle évalué) écrit
            pour chaque passage une question de propriétaire, sa réponse, et une citation mot pour mot. La question
            n'est gardée que si la citation se retrouve vraiment dans le passage. Chaque question existe en huit
            versions : deux langues × (sans véhicule, marque, modèle, nom complet).
          </p>
          <div className="note">
            <strong>Jeu partiel :</strong> {intFr(dataset.questions)} questions sur {dataset.manuals} manuels
            ({dataset.splits.test} test, {dataset.splits.dev} dev), reconstruit depuis le cache quand les crédits
            Gemini se sont épuisés. Il couvre surtout les premiers manuels par ordre alphabétique : les chiffres
            sont provisoires.
            {dataset.audit && ` Audit indépendant de ${dataset.audit.supported + dataset.audit.supported_with_extra_detail + dataset.audit.unsupported} questions tirées au hasard : ${dataset.audit.supported + dataset.audit.supported_with_extra_detail} réponses étayées par leur citation, ${dataset.audit.unsupported} non étayée.`}
          </div>
          <div className="sample">
            <div>
              <span className="kind">QUESTION GÉNÉRÉE · {dataset.sample.manual} · page {dataset.sample.page}</span>
              {[['Sans véhicule', 'plain'], ['Marque', 'brand'], ['Modèle', 'model'], ['Nom complet', 'full']].map(([label, form]) => (
                <p key={form}><span className="form">{label}</span>{dataset.sample.queries[`fr_${form}`]}</p>
              ))}
            </div>
            <div>
              <span className="kind">RÉFÉRENCE</span>
              <p><span className="form">Réponse attendue</span>{dataset.sample.answer}</p>
              <p><span className="form">Citation du manuel</span><em>« {dataset.sample.evidence} »</em></p>
            </div>
          </div>
        </Section>

        <Section id="echelle" tab="E1" title="Plus il y a de manuels, moins on trouve"
                 lede={`Pour une question sans nom de véhicule, la meilleure recherche retrouve le bon passage dans ${pct(value(R.hybrid, 'native_plain', 'hard', 1, 'chunk_hit_5'))} des cas quand elle ne fouille que le bon manuel, ${pct(value(R.hybrid, 'native_plain', 'hard', 5, 'chunk_hit_5'))} avec 5 manuels de la même marque, et ${pct(value(R.hybrid, 'native_plain', 'hard', maxN, 'chunk_hit_5'))} sur les ${maxN}. Choisissez « Modèle » pour voir le routage par nom annuler l'effet de taille.`}>
          <div className="panel">
            <div className="controls">
              <span className="control-label">Mesure</span>
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
              <span className="control-label">Distracteurs</span>
              <div className="seg">
                <button type="button" aria-pressed={strategy === 'hard'} onClick={() => setStrategy('hard')}>Même marque</button>
                <button type="button" aria-pressed={strategy === 'random'} onClick={() => setStrategy('random')}>Aléatoires</button>
              </div>
            </div>
            <div className="legend">
              {series.map((s) => <span key={s.label}><i style={{ background: s.color }} />{s.label}</span>)}
            </div>
            <LineChart
              series={series}
              xLabel="manuels dans le corpus fouillé (échelle logarithmique)"
              yLabel={metric === 'chunk_hit_5' ? 'bon passage dans le top 5' : 'bon manuel en 1re position'}
            />
          </div>
          <p className="caption">Le manuel qui contient la réponse, plus N−1 distracteurs (5 tirages par taille). Les bandes montrent l'intervalle de confiance à 95 %.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Technique</th>{tiers.map((n) => <th key={n} className="num">{n}</th>)}</tr></thead>
              <tbody>
                {e1.retrievers.map((r) => (
                  <tr key={r.spec}>
                    <td>{RETRIEVER_LABEL[r.spec] || r.label}</td>
                    {tiers.map((n) => <td key={n} className="num">{pctNum(value(r.spec, variant, strategy, n, metric))}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section id="techniques" tab="E2" title="Quelles techniques tiennent à grande échelle">
          {!e2 ? (
            <div className="note">Le comparatif complet (rerankers inclus) est encore en cours de calcul. Il apparaîtra ici à la prochaine génération des résultats.</div>
          ) : (
            <>
              <div className="controls">
                <span className="control-label">Périmètre</span>
                <div className="seg">
                  <button type="button" aria-pressed={scope === 'global'} onClick={() => setScope('global')}>Tous les manuels</button>
                  <button type="button" aria-pressed={scope === 'vehicle'} onClick={() => setScope('vehicle')}>Dans le véhicule</button>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Technique</th>
                      {VARIANTS.filter(([v]) => v !== 'native_brand').map(([, label]) => <th key={label} className="num">{label}</th>)}
                      <th className="num">Autre langue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...new Set(e2.rows.map((r) => r.retriever))].map((spec) => {
                      const row = (v) => e2.rows.find((r) => r.retriever === spec && r.variant === v && r.scope === scope)
                      const metricKey = scope === 'global' ? 'doc_hit_1' : 'chunk_hit_5'
                      return (
                        <tr key={spec}>
                          <td>{RETRIEVER_LABEL[spec] || e2.rows.find((r) => r.retriever === spec)?.label}<div className="spec">{spec}</div></td>
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
                    })}
                  </tbody>
                </table>
              </div>
              <p className="caption">{scope === 'global' ? 'Bon manuel en 1re position sur tous les manuels.' : 'Bon passage dans les 5 premiers, en cherchant dans les manuels du véhicule.'} Intervalles de confiance à 95 % en petit.</p>
            </>
          )}
        </Section>

        <Section id="clarification" tab="E4" title="Demander plutôt que deviner"
                 lede={`« Comment changer ma batterie ? » n'a pas une réponse mais ${corpus.vehicles}, une par véhicule. Sur les questions sans nom de véhicule, ne jamais demander donne le bon manuel dans ${pct(byVariant('never', 'native_plain')?.doc_hit_1)} des cas ; une seule question de clarification le fait monter à ${pct(byVariant('name_rule', 'native_plain')?.doc_hit_1)}.`}>
          <div className="panel">
            <ParetoChart policies={mainPolicies} sweep={sweep} labels={POLICY_LABEL} />
          </div>
          <p className="caption">Dialogues simulés : un utilisateur simulé répond avec son vrai véhicule. Les barres montrent l'intervalle de confiance à 95 %, la ligne pointillée le détecteur appris à différents seuils.</p>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Politique</th><th className="num">Bon manuel</th><th className="num">Bon passage</th>
                  <th className="num">Questions / requête</th><th className="num">Clarifications manquées</th><th className="num">Clarifications inutiles</th>
                </tr>
              </thead>
              <tbody>
                {[...mainPolicies, ...sweep.filter((p) => p.policy.endsWith('0.8'))].map((p) => (
                  <tr key={p.policy} className={p.policy === 'name_rule' ? 'best' : ''}>
                    <td>{POLICY_LABEL[p.policy] || p.policy.replace('classifier@', 'Détecteur, seuil ')}</td>
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

          <h3>Détecter l'ambiguïté, oui. Savoir si elle compte, non.</h3>
          <p>
            Les signaux calculés sans LLM détectent très bien qu'une question ne désigne aucun véhicule
            (détecteur : AUC <strong>{dec(e4.detection.classifier.roc_auc)}</strong>, rappel {pct(e4.detection.classifier['recall@0.5'])}).
            Mais parmi les {intFr(genericity.n_test)} requêtes ambiguës, ils ne savent pas dire si la réponse change
            d'un véhicule à l'autre : AUC <strong>{dec(genericity.classifier_auc)}</strong>, à peine mieux que le hasard.
            C'est la frontière où un LLM devient nécessaire.
          </p>
          <div className="panel">
            <div className="legend">
              <span><i style={{ background: SERIES[0] }} />Détecter qu'il manque le véhicule</span>
              <span><i style={{ background: SERIES[1] }} />Détecter si la réponse dépend du véhicule</span>
            </div>
            <SignalBars rows={e4.signals.filter((s) => s.generic_auc != null && SIGNAL_NAME[s.signal])} names={SIGNAL_NAME} />
          </div>

          <h3>Exemples de décision</h3>
          <p>{e4.examples.length} questions écrites à la main, avec la décision attendue. Le système décide juste dans <strong>{okExamples} cas sur {e4.examples.length}</strong>.</p>
          <div className="table-wrap">
            <table className="examples">
              <thead><tr><th>Question</th><th>Attendu</th><th>Décision</th><th>Question posée ou raison</th></tr></thead>
              <tbody>
                {e4.examples.map((example) => {
                  const ok = example.correct_action === true || example.correct_action === 'True'
                  return (
                    <tr key={example.id} className={ok ? '' : 'wrong'}>
                      <td>{example.query}</td>
                      <td><span className={`pill ${example.expected}`}>{ACTION_LABEL[example.expected]}</span></td>
                      <td><span className={`pill ${example.predicted}`}>{ACTION_LABEL[example.predicted]}</span>{!ok && <span className="wrong-flag">erreur</span>}</td>
                      <td>
                        {example.predicted === 'clarify' ? (
                          <>{example.question}<div className="options">{String(example.options).split(' | ').join(' · ')}</div></>
                        ) : example.predicted === 'answer' ? (
                          <span className="mono">{example.top_manual} · page {example.top_page}</span>
                        ) : translateReason(example.reason)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <h3>Dialogues simulés</h3>
          <div className="dialogues">
            {e4.dialogues.map((dialogue) => (
              <article key={dialogue.query}>
                <span className="kind">QUESTION {dialogue.variant === 'native_plain' ? 'SANS VÉHICULE' : dialogue.variant === 'native_brand' ? 'AVEC LA MARQUE' : 'AVEC LE MODÈLE'}</span>
                <p className="say user">{dialogue.query}</p>
                {dialogue.turns.map((turn) => (
                  <div key={turn.q}>
                    <p className="say bot">{turn.q}</p>
                    <div className="chips">{turn.options.map((option) => <span key={option}>{option}</span>)}</div>
                    <p className="say user">{turn.a}</p>
                  </div>
                ))}
                <p className="outcome">Passage retrouvé : <span className="mono">{dialogue.top_manual} · page {dialogue.top_page}</span>{dialogue.doc_ok ? ' — bon manuel' : ''}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section id="methode" tab="MÉTH" title="Méthode et limites">
          <ul className="method">
            <li><strong>Métriques.</strong> Bon manuel en 1<sup>re</sup> position, bon passage parmi les 5 premiers (ceux envoyés au LLM), nDCG@10, confusions avec un manuel de la même marque. Un passage est « bon » s'il contient la citation de référence ; le calcul est vérifié contre la bibliothèque <code>ranx</code>.</li>
            <li><strong>Statistiques.</strong> La question est l'unité statistique. Intervalles de confiance à 95 % (Wilson pour les proportions, bootstrap sinon), comparaisons par test de permutation apparié avec correction de Holm.</li>
            <li><strong>Protocole.</strong> Les réglages sont choisis sur le split <em>dev</em> ; les chiffres publiés viennent du split <em>test</em>.</li>
            <li><strong>Limites.</strong> Jeu de questions partiel et synthétique ; la recherche de production (embeddings Gemini) et l'étape de réponse du LLM restent à mesurer ; l'utilisateur simulé connaît toujours son véhicule.</li>
          </ul>
          <p className="footer-note">
            Page générée à partir de <code>research/results</code> · jeu <code>{dataset.name}</code> ·
            {' '}{intFr(corpus.chunks)} passages · chiffres provisoires.
          </p>
        </Section>
      </main>
    </div>
  )
}
