# Wallside — finding the right manual

An assistant that answers from a library of car owner's manuals has to solve two problems before it can say
anything useful: **which vehicle** the question is about, and **which page** of that vehicle's manual holds the
answer. Wallside started as that assistant (a RAG chatbot over manufacturer PDFs). It is now a study of how well
retrieval can do that job, and how accuracy degrades as the library grows.

The study runs on the real production data: **165 manuals, 62,712 pages, 138,087 passages**, 157 vehicles from
34 brands, extracted byte-for-byte from the chatbot's indexes.

## Research questions

| | Question | Where |
|---|---|---|
| E1 | How much accuracy does corpus size cost? The same question is searched over 1, 2, 5 … 165 manuals, with random or same-brand (lookalike) distractors. | `research/configs/e1_*.yaml` |
| E2 | Which retrieval methods survive at full scale? 18 configurations: BM25, dense (bge-m3, e5, Gemini), fusion, context headers, RM3, name routing, HNSW, cross-encoder reranking. | `research/configs/e2_*.yaml` |
| E4 | When no vehicle is named, should the system guess or ask? Detection of underspecified questions and clarification policies, measured as accuracy vs questions asked. | `research/configs/e4_*.yaml` |

## Provisional results

Computed on the partial question set (640 questions over 108 manuals, test split), so they may still move:

- **Size breaks plain retrieval.** Identifying the right manual falls from 100% on a single manual to roughly
  17–27% at 165 manuals for every standard retriever (lexical, dense and hybrid alike).
- **Metadata routing fixes document identification.** Routing on the vehicle named in the question, over a
  weighted BM25 + bge-m3 hybrid, brings top-1 back to about 98%. With a cross-encoder reranker, the right
  passage is in the top 5 about 93% of the time.
- **Asking beats guessing.** With no vehicle in the question, retrieval alone picks the right manual 18% of
  the time; asking about one clarifying question raises it to 97%.

The full numbers, with 95% confidence intervals, are on the results site and in `research/reports/report.html`.

## Method, in short

- **Gold questions** written by a different model generation than the system under test (`gemini-3.5-flash`
  vs production `gemini-2.5-flash`), each kept only if its verbatim evidence span is really in the passage.
  Eight query forms per question: French/English × no vehicle / brand / model / full name.
- **Two metrics**: right manual at rank 1 (`doc_hit@1`) and right passage in the top 5 (`chunk_hit@5`),
  strict and lenient (shared boilerplate across manuals).
- **Statistics**: question as the unit, dev/test split (configurations chosen on dev, reported on test),
  Wilson and bootstrap 95% CIs, paired randomization tests with Holm–Bonferroni correction.
- **Data defects found and documented**: 5 Kia manuals 91–98% unreadable (font-encoding failure), one
  manual indexed twice, 9% of passages identical across manuals.

Details: [`research/README.md`](research/README.md).

## Repository

```
.
├── research/     ragscale, the evaluation harness (Python, uv): corpus extraction, gold questions,
│                 retrievers, experiments E1–E4, statistics, figures, HTML report
├── frontend/     React + Vite site. "/" is the results site (overview, corpus, E1, E2, E4, protocol),
│                 every number read from public/research-results.json written by the pipeline.
│                 The original product pages remain at /produit, /ask, /guides, /chat/:slug
├── backend/      The original chatbot: Flask API, FAISS + BM25 hybrid retrieval, Gemini.
│                 Its indexes are the corpus the study measures
├── car data/     Manufacturer PDFs served in production
└── docs/         Pitch and business notes from the product phase
```

## Running

Research harness (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd research
make install install-local   # environments (local = torch, sentence-transformers)
make test                    # unit tests, no data or API needed
make corpus embed            # extract the corpus, compute local embeddings
make e1 e2                   # experiments -> data/runs, summaries and figures -> results/
```

Results site:

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

The chatbot backend (optional, needs a `GOOGLE_API_KEY` in `backend/.env`):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python api.py                # http://localhost:5002
```

## Not versioned

FAISS/BM25 indexes (`backend/data/guides/*/vector_store`), the extracted corpus, embeddings and raw runs
(`research/data/`), and secrets (`.env`). `make corpus` rebuilds the research data from the backend indexes.

## Author

Lakhdar Berache — [wallside.online](https://wallside.online)
