/**
 * Naming and prose for the research site. Every description here mirrors what the code in
 * research/src/ragscale/retrievers actually does, including the parameter values that were run.
 */

export const R = {
  bm25: 'bm25_stem',
  dense: 'dense:bge-m3',
  hybrid: 'wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)',
  ctx: 'wsum(bm25_stem+ctx,dense:bge-m3+ctx;w=0.3|0.7)',
  router: 'name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))',
  hnsw: 'hnsw(dense:bge-m3)',
}

/** family: lexical | dense | fusion | routing | rerank */
export const METHODS = {
  bm25: {
    label: 'BM25',
    family: 'lexical',
    how: 'Lucene BM25 (k1 = 1.2, b = 0.75) over accent-folded tokens with French and English stopwords removed. Matches words, not meaning.',
  },
  bm25_stem: {
    label: 'BM25 + stemming',
    family: 'lexical',
    how: 'The same BM25, plus Snowball stemming in the manual’s language for documents and in the question’s language for queries, so "pneus" matches "pneu".',
  },
  'bm25_stem+ctx': {
    label: 'BM25 + document headers',
    family: 'lexical',
    how: 'Every chunk is indexed with its identity prepended — "Peugeot 208 (2023) | Peugeot | page 157" — a rule-based form of contextual retrieval, so near-identical passages of sibling manuals stop being interchangeable.',
  },
  'rm3(bm25)': {
    label: 'BM25 + query expansion (RM3)',
    family: 'lexical',
    how: 'A first BM25 pass; its 10 best chunks supply the 10 strongest expansion terms, and the final query mixes them 50/50 with the original words (Lavrenko & Croft, 2001).',
  },
  'dense:bge-m3': {
    label: 'bge-m3 (meaning)',
    family: 'dense',
    how: 'BAAI/bge-m3 bi-encoder: the question and every chunk become one vector each, ranked by cosine similarity over an exact FAISS search. Multilingual, so a French question can match an English manual.',
  },
  'dense:bge-m3+ctx': {
    label: 'bge-m3 + document headers',
    family: 'dense',
    how: 'The same encoder, but each chunk is embedded together with its document header, so the vehicle name is part of the vector.',
  },
  'dense:multilingual-e5-large-instruct': {
    label: 'e5-large-instruct (meaning)',
    family: 'dense',
    how: 'intfloat/multilingual-e5-large-instruct, a second bi-encoder family, with the retrieval instruction prefixed to every question — a control for "is this specific to bge-m3?".',
  },
  'hnsw(dense:bge-m3)': {
    label: 'bge-m3, approximate index (HNSW)',
    family: 'dense',
    how: 'The same bge-m3 vectors in an approximate HNSW graph (M = 32, efConstruction = 64) with a filter bitmap for the corpus-size masks: what accuracy costs when search has to be fast.',
  },
  'rrf(bm25_stem,dense:bge-m3)': {
    label: 'RRF fusion — production today',
    family: 'fusion',
    how: 'Reciprocal Rank Fusion of the BM25 and bge-m3 rankings (k = 60, depth 100). It uses ranks only and throws the scores away — this is what the shipped product runs.',
  },
  'wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)': {
    label: 'Hybrid, weighted scores',
    family: 'fusion',
    how: 'Min-max normalised scores combined as 0.3 × BM25 + 0.7 × bge-m3. The weights were picked on the dev split and never touched again.',
  },
  'wsum(bm25_stem+ctx,dense:bge-m3+ctx;w=0.3|0.7)': {
    label: 'Hybrid + document headers',
    family: 'fusion',
    how: 'The same weighted fusion, with both sides indexed over header-prefixed chunks.',
  },
  'name_boost(dense:bge-m3;lam=0.5)': {
    label: 'bge-m3 + vehicle-name boost',
    family: 'routing',
    how: 'Dense score + 0.5 × cosine(question, embedding of the manual’s name): gives every chunk a document identity without re-embedding the corpus.',
  },
  'doc_router(dense:bge-m3+ctx)': {
    label: 'Pick the manual, then the passage',
    family: 'routing',
    how: 'Two stages: rank manuals by the mean of their 3 best chunk scores, keep the top 3 manuals, then rank chunks only inside them.',
  },
  'name_router(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': {
    label: 'Name routing (name kept in the query)',
    family: 'routing',
    how: 'If the question names a vehicle, the search is restricted to that vehicle’s manuals; otherwise it searches everything. Deterministic string matching against the manual names — no model, no latency.',
  },
  'name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': {
    label: 'Name routing + name stripped',
    family: 'routing',
    how: 'The same routing, and the words that named the vehicle are deleted from the question once the filter is applied — inside the right manual, "Peugeot 208 (2023)" only dilutes the passage match.',
  },
  'rerank(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': {
    label: 'Hybrid + cross-encoder rerank',
    family: 'rerank',
    how: 'The hybrid’s top 30 are re-scored by BAAI/bge-reranker-v2-m3, a cross-encoder that reads the question and the passage together instead of comparing two vectors. Costs about 1.5 s per question.',
  },
  'rerank(name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)))': {
    label: 'Routing + hybrid + cross-encoder rerank',
    family: 'rerank',
    how: 'Route on the vehicle name, strip it, search hybrid, then re-score the top 30 with the cross-encoder. The best configuration measured.',
  },
  'm3rerank(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))': {
    label: 'Hybrid + BGE-M3 rerank (multi-vector)',
    family: 'rerank',
    how: 'The hybrid’s top 30 re-scored by BGE-M3’s three heads at once — dense 0.4, sparse 0.2, multi-vector (ColBERT-style) 0.4.',
  },
}

export const FAMILY_LABEL = {
  lexical: 'Lexical',
  dense: 'Dense',
  fusion: 'Fusion',
  routing: 'Routing',
  rerank: 'Reranking',
}

export const FAMILIES = [
  {
    key: 'lexical',
    title: 'Lexical',
    line: 'BM25 over the words themselves — stemming, stopwords, optional document headers, optional RM3 expansion.',
  },
  {
    key: 'dense',
    title: 'Dense',
    line: 'Multilingual bi-encoders (bge-m3, e5-large) that turn question and passage into vectors compared by cosine similarity.',
  },
  {
    key: 'fusion',
    title: 'Fusion',
    line: 'Combining the two rankings: reciprocal rank fusion (today in production) against weighted score fusion.',
  },
  {
    key: 'routing',
    title: 'Routing',
    line: 'Using the vehicle named in the question as a filter before searching, rather than as extra words inside it.',
  },
  {
    key: 'rerank',
    title: 'Reranking',
    line: 'A cross-encoder re-reads the top 30 candidates with the question, trading ~1.5 s per query for precision.',
  },
]

export const labelOf = (spec) => METHODS[spec]?.label || spec
export const familyOf = (spec) => METHODS[spec]?.family
export const howOf = (spec) => METHODS[spec]?.how

export const SHORT = {
  [R.bm25]: 'BM25',
  [R.dense]: 'bge-m3',
  [R.hybrid]: 'hybrid',
  [R.ctx]: '+ headers',
  [R.router]: 'routing',
  [R.hnsw]: 'HNSW',
}

export const VARIANTS = [
  ['native_plain', 'No vehicle'],
  ['native_brand', 'Brand'],
  ['native_model', 'Model'],
  ['native_full', 'Full name'],
]

export const METRICS = [
  ['chunk_hit_5', 'Right passage (top 5)'],
  ['doc_hit_1', 'Right manual (rank 1)'],
]

export const POLICY_LABEL = {
  never: 'Never ask',
  always: 'Always ask',
  name_rule: 'Ask when no vehicle is named',
  oracle: 'Oracle',
}

export const SIGNAL_NAME = {
  vehicle_margin: 'gap between 1st and 2nd vehicle',
  passage_agreement: 'agreement between passages',
  top1_vehicle_share: 'share of the top vehicle',
  vehicle_entropy: 'spread across vehicles',
  n_vehicles_top10: 'vehicles in the top 10',
  n_brands_top10: 'brands in the top 10',
  query_tokens: 'question length',
  mentions_brand: 'brand mentioned',
}

export const ACTION_LABEL = { answer: 'answer', clarify: 'ask', abstain: 'abstain' }

/** The decision layer writes compact reasons; spell them out. */
export function readableReason(reason, dec) {
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
