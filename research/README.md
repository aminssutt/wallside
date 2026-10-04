# ragscale — how accurately does a RAG pipeline find the right document as the corpus grows?

Research harness of the Wallside project, built on its corpus (car owner's manuals). It measures, with exact
numbers and confidence intervals, whether a retrieval pipeline (and the LLM on top of it) identifies the
**right manual** and the **right passage/page** for a question, as a function of how much data it searches.

## Research questions

| | Question | Experiment |
|---|---|---|
| RQ1 | How does document-identification accuracy fall when the searched corpus grows from 1 to 165 manuals, with random vs hard (same-brand / most similar) distractors? | E1 `configs/e1_scaling.yaml` |
| RQ2 | Which retrieval techniques resist that degradation (lexical, dense, hybrid, routing, contextual headers, reranking, ANN)? | E2 `configs/e2_techniques.yaml` |
| RQ3 | How much does naming the vehicle in the query (none / brand / model / full name) help? | query variants in E1/E2 |
| RQ4 | Given retrieved passages, does the LLM cite the right document and answer correctly; how do context size and gold position matter? | E3 `experiments/llm_stage.py` |
| RQ5 | How accurate is the retrieval currently in production? | E0 `scripts/prod_replica.py` |

Hypotheses from the literature: dense retrievers lose ground to BM25 as distractors grow (Reimers & Gurevych 2021,
arXiv:2012.14210); more documents hurt RAG and metadata scoping helps (arXiv:2606.11350); near-duplicate
documents need document-aware retrieval (HiQA, arXiv:2402.01767); LLM accuracy depends on context size and the
gold passage's position (Liu et al. 2023, arXiv:2307.03172; Cuconasu et al. 2024, arXiv:2401.14887).

## Corpus (`ragscale corpus`)

Extracted **byte-for-byte from the production indexes** (`backend/data/guides/*/vector_store`): the chunk texts
of the BM25 pickles and, in the same order, their `gemini-embedding-001` vectors from FAISS (verified: re-encoding
a chunk with task type `RETRIEVAL_DOCUMENT` gives cosine 1.0). No PDF re-processing, so results describe the
data the chatbot really searches.

- 165 manuals, 138,087 chunks, 62,712 pages; 138 French / 27 English manuals; 154 vehicles (app grouping).
- Data defects found and flagged (`chunks.garbled`, `manuals.duplicate_of`):
  - 5 Kia manuals are 91–98% unreadable (font-encoding failure at extraction: `UUIFPDDVQBOU` = `theoccupant`),
    Subaru Forester 34%. 6,465 garbled chunks overall; they stay in the corpus (realistic noise) but never
    serve as question sources.
  - `mazda-cx-5` and `mazda-3` are the same PDF indexed twice.
  - 12,522 chunks (9%) have text identical to a chunk of another manual (shared boilerplate).

## Gold question set (`ragscale dataset`)

- Source chunks: up to 6 per manual, spread over the whole document (position bins), 350–2,200 characters,
  not garbled, text unique to that manual.
- A **different Gemini generation than the system under test** (`gemini-3.5-flash` vs production
  `gemini-2.5-flash`) writes an owner-style question, a short answer and a **verbatim evidence span**. Records
  are kept only if the evidence is really in the chunk (≥ 90% token coverage).
- Anti-leakage: the prompt forbids copying distinctive wording; the lexical overlap between question and
  passage is stored per record so results can be stratified by it.
- Each question has 8 query texts: FR/EN × {plain (no vehicle), brand, model, full name}.
- **Gold relevance is text-level**: `relevant_rows` = chunks of the gold manual containing the evidence
  (overlapping chunks count); `equivalent_rows` = the same evidence text in other manuals. Metrics report
  *strict* (right manual) and *lenient* (any manual containing the evidence) variants.
- Deterministic 70/30 test/dev split by question id. Configurations are chosen on **dev**, reported on **test**.
- Independent audit: 40 random records checked by a non-Gemini model against the evidence
  (`datasets/*.audit.json`).

> Status: `questions_v1_partial.jsonl` (640 questions, 108 manuals) was built from cached generations after the
> Gemini prepaid credits ran out. It is biased towards the first manuals in alphabetical order and is used for
> development only. `ragscale dataset` regenerates `questions_v1` (cached calls are free and identical).

## Retrieval scopes

| scope | manuals searched |
|---|---|
| `manual` | the gold manual only (upper bound for passage retrieval) |
| `vehicle` | the gold vehicle's manuals — what the app does after the user picks a car |
| `global` | all 165 manuals — the system must find the document by itself |
| `tierN-{random,hard}-sS` | gold + N−1 distractors, nested over N per seed; hard = same brand first, then most similar manuals (mean-embedding cosine) |

One global index is masked per condition, so dozens of corpus sizes cost one scoring pass. For BM25 this means
IDF comes from the full collection (documented choice; dense scores are unaffected).

## Retrievers (`experiments/registry.py`)

| spec | technique | runs on |
|---|---|---|
| `bm25`, `bm25_stem` | BM25 (bm25s, Lucene), accent folding, FR/EN stopwords, Snowball stemming | CPU |
| `bm25+ctx` | chunks indexed with a document header (manual name, brand, page) | CPU |
| `rm3(bm25)` | RM3 pseudo-relevance feedback | CPU |
| `dense:gemini-embedding-001` | production embeddings (query side needs the API) | API + CPU |
| `dense:bge-m3`, `dense:multilingual-e5-large-instruct`, `dense:bge-m3+ctx` | local multilingual bi-encoders | MPS/CPU |
| `rrf(a,b;k=60)`, `wsum(a,b;w=..,norm=..)`, `combmnz(...)` | rank / score fusion | CPU |
| `name_router(a)` | metadata routing: restrict to manuals named in the query | CPU |
| `doc_router(a;n=3)` | two-stage manual → chunk retrieval | CPU |
| `name_boost(dense:m)` | dense + λ·cos(query, manual name) | as dense |
| `hnsw(dense:m)` | filtered approximate search (FAISS HNSW + ID bitmap) | CPU |
| `rerank(a)` | cross-encoder `BAAI/bge-reranker-v2-m3` | MPS/CPU |
| `m3rerank(a)` | BGE-M3 dense+sparse+ColBERT scoring (FlagEmbedding) | MPS/CPU |

## Metrics (`metrics.py`, cross-checked against `ranx`)

- Document level: `doc_hit@{1,3,5}` (manuals in order of first appearance), `doc_rr`, `doc_hit@1_lenient`.
- Confusions of the top-1 manual: `confusion_same_vehicle`, `confusion_same_brand`, `confusion_other_brand`.
- Passage level: `chunk_hit@{1,3,5,10,20}` (+ lenient), `chunk_rr@10`, `ndcg@10`, `page_hit@{1,5}`.

## Statistics (`stats.py`)

- Question = statistical unit (seeds averaged per question first).
- 95% CIs: Wilson for proportions, percentile bootstrap (10k) otherwise.
- System comparisons: paired randomization test (Smucker et al., CIKM 2007), Holm–Bonferroni correction.

## Running

```bash
make install install-local   # uv environments
make test                    # unit tests, no data/API
make corpus                  # extract corpus + Gemini vectors
make embed                   # local embeddings (~1-2 h per model on Apple Silicon)
make dataset                 # gold questions (Gemini API)
make smoke                   # 40-question end-to-end check (API-free)
make e1 e2                   # experiments -> data/runs, summaries/figures -> results/
uv run ragscale best e2_techniques --metric doc_hit@1 --scope global --variant native_plain
```

Docker (CPU, same code): `make docker-build docker-test`, `make docker-run CONFIG=configs/e1_scaling.yaml`.
Set `RAGSCALE_OFFLINE=1` to forbid API calls (cached responses only).

## Layout

```
research/
  src/ragscale/      corpus, text, llm (cached Gemini client), metrics, stats
    retrievers/      base, lexical, dense, composite, rerank
    dataset/         question generation, vehicle name forms
    experiments/     scopes, registry, runner, analysis, llm_stage (E3)
  configs/           experiment specs (YAML)
  datasets/          gold question sets (versioned)
  scripts/           prod_replica.py (runs the backend's retrieval code)
  results/           summaries and figures (versioned)
  data/              corpus, embeddings, indexes, caches, raw runs (not versioned)
```
