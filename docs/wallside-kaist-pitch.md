---
marp: true
theme: default
size: 16:9
paginate: true
header: 'Wallside · Agentic Vehicle Assistant'
footer: 'Lakhdar Berache · April 2026'
style: |
  section {
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size: 24px;
    padding: 60px;
    background: #fafafa;
  }
  h1 {
    color: #0b2a4a;
    font-size: 44px;
    margin-bottom: 4px;
  }
  h2 {
    color: #0b2a4a;
    font-size: 28px;
    margin-top: 6px;
    border-bottom: 2px solid #cbd5e1;
    padding-bottom: 4px;
  }
  h3 { color: #1f3b63; font-size: 22px; }
  code, pre {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 18px;
  }
  pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 14px 18px;
    border-radius: 8px;
    line-height: 1.4;
  }
  table {
    font-size: 20px;
    border-collapse: collapse;
  }
  th, td {
    padding: 6px 12px;
    border-bottom: 1px solid #cbd5e1;
    text-align: left;
  }
  th { background: #e2e8f0; }
  strong { color: #0b2a4a; }
  section::after {
    color: #64748b;
    font-size: 16px;
  }
---

<!-- _class: lead -->

# Wallside

### A grounded, tool-calling vehicle assistant

**Lakhdar Berache** · April 2026
Technical overview prepared for KAIST

---

## 1 · System overview

Wallside turns **154 vehicle owner's manuals + 12 supplementary
sub-system manuals** (infotainment, multimedia, quick-reference,
maintenance logs) into a multilingual conversational assistant.
A user picks a vehicle and asks a technical question (maintenance,
warning lights, specifications, procedures); the system replies in
French, English or Korean, grounded on the manual text and
cross-checked against official manufacturer sites.

### Two-stage tool-calling agent

```
user question
      │
      ▼
   safety triage ─────► refuse (credentials / prompt injection /
      │                        safety-system tampering)
      ▼
   PLANNER  (Gemini Flash-Lite, ~700 ms)
      │      emits ≤ 4 tool calls via function_calling
      ▼
 ┌─────────────────────────────────────────────┐
 │  parallel dispatch                          │
 │  search_manual · search_web · search_youtube │
 └─────────────────────────────────────────────┘
      │
      ▼
   RESPONDER  (Gemini Flash, streamed SSE)
      │       grounded strictly on the evidence block
      ▼
   streamed answer + deterministic citations
```

Each stage lives in its own module (`planner.py`, `tools.py`,
`responder.py`, `orchestrator.py`, `safety.py`, `bridge.py`) with
~1 600 lines of Python and a 27-test pytest suite.

---

## 2 · Data pipeline — how the 166 knowledge sources were indexed

```
 Manufacturer PDF
 (car data/Renault/Clio 5.pdf)
        │
        ▼  ingest_vehicle.py / batch_ingest*.py
 ┌────────────────────────────────────┐
 │ page extraction (pypdf + OCR        │
 │   fallback via Tesseract for scans) │
 │ smart chunking  (section-aware,     │
 │   800 char window, 100 char overlap)│
 │ metadata (source_file, page,        │
 │   chunk_index)                      │
 └────────────────────────────────────┘
        │
        ├─► FAISS index  (Gemini embedding-001, 3 072 dim)
        │
        └─► BM25 index   (rank_bm25, per-chunk tokens)

 manifest.json  ──  slug · brand · segment · pdf_url · chunk_count
                    (external preview via inspirauto.fr)
```

### Numbers

| Metric | Value |
|---|---|
| Vehicle models surfaced | **154** across **35 brands** |
| + supplementary sub-system manuals | **12** (infotainment, multimedia, quick-reference, maintenance) |
| Total indexed knowledge sources | **166** |
| Total manual pages ingested | **62 712** |
| Total retrieval chunks | **138 087** |
| Languages supported | French · English · Korean |
| On-disk FAISS + BM25 store | **≈ 2.0 GB** |
| PDF preview coverage | 149 / 165 (90 %) via inspirauto URL |

### Retrieval at query time

`_hybrid_search()` runs FAISS (dense) and BM25 (sparse) in parallel,
then merges with **Reciprocal Rank Fusion**
(`score = Σ 1/(k + rank_i)`, k = 60). A soft relevance threshold
filters chunks below `0.1 × RELEVANCE_THRESHOLD` but always keeps the
top hit so the responder never starves.

---

## 3 · Agent tools — what the planner can call

### search_manual — hybrid retrieval, per-guide

Wrapper over `_hybrid_search`. Returns up to `TOP_K_RESULTS` chunks
with full metadata; the responder sees them as an EVIDENCE block with
clear `[manual source.pdf p.N]` headers.

### search_web — multi-site, multi-lingual, official-domain aware

The planner writes a generic query; the dispatcher **fires two
parallel DDGS queries** — the raw query **and** a
`site:<manufacturer-domain>` variant built from a curated 36-brand
map (audi.fr, bmw.com, hyundai.co.kr, renault.com…).

```python
_OFFICIAL_DOMAINS = {
    "audi":   ["audi.com", "audi.fr", "audiusa.com", "audi.co.kr"],
    "bmw":    ["bmw.com", "bmw.fr", "bmwusa.com", "bmw.co.uk", ...],
    "hyundai":["hyundai.com", "hyundai.fr", "hyundai.co.kr", ...],
    # 33 more
}
```

Results are merged with URL de-duplication + per-domain diversity
(max 2 per domain). Region switches per user language
(`fr→fr-fr`, `ko→kr-kr`). The planner may emit two `search_web`
calls with different `language` arguments when that widens coverage.

### search_youtube — worldwide

Six query variants probed (EN / FR / KO + "tutorial" / "tutoriel" /
"튜토리얼" / "how to" / "review"). Default region is `wt-wt`
(worldwide) so a French user still reaches high-quality English or
Korean walkthroughs when no French one exists.

---

## 4 · Safety · Grounding · Production

### Three-layer safety

1. **Input triage** (pre-LLM, 0 ms). Accent-folded regex catches
   credential extraction (`GOOGLE_API_KEY`, `secret`, `.env`),
   prompt injection ("ignore previous instructions", role-play
   jailbreaks), infra probing, SSRF / path traversal, and
   safety-system tampering requests (disabling airbags, ECU
   rollback). Hard-blocked with a localised refusal — zero tokens
   spent.
2. **Tool-output sanitisation**. HTML tags, `javascript:` URIs, and
   embedded "ignore previous instructions" phrases stripped from
   every web / manual snippet before it reaches the responder.
3. **Model guardrail**. A `SAFETY_GUARDRAIL` system string appended
   to planner + responder prompts forbids revealing internal config
   and instructs the model to treat evidence strictly as data.

### Grounding rules baked into the responder prompt

- Never invent numerical values (torques, pressures, capacities).
- Prefer manual evidence; fall back to web only when the manual is
  silent. Prefer **official manufacturer domains** over aggregators;
  flag disagreements.
- Units match the user's language: metric first for French and
  Korean (e.g. "2 000 kg (4 400 lbs)"), imperial only when the
  source has nothing else.
- **No inline page references** (`selon la page 370`) — the UI renders
  clickable citations in a separate block.

### Observability & control

- Timing logger (`auris.agent.*`) per stage: `plan_ms`, `tools_ms`,
  `respond_ms`, `total_ms`.
- Feature flag `AGENT_ENABLED=0|1` — falls back to the legacy linear
  pipeline instantly.
- Streaming via Flask SSE; the bridge translates agent events into
  the legacy wire format so the React frontend needs zero changes.

---

## 5 · Results & research questions

### Live example — *"Quelle est la capacité de remorquage de l'Audi Q5 2019 ?"*

**Before (linear RAG):** *"According to CarsCounsel.com, 4 400 lbs.
Information for 2018–2020 is not available."* — single aggregator,
imperial only, fake gap.

**After (agentic):** *"La capacité de remorquage freinée de l'Audi
Q5 (2017–2020) est de **2 000 kg (4 400 lbs)** pour une pente allant
jusqu'à 12 %."* — grounded on **manual page 370**, cross-checked
against **9 distinct web domains** including `media.audi.com` and
`audiusa.com`, metric first.

### Benchmarks

| Metric | Value |
|---|---|
| Planner | 700–1 200 ms |
| Parallel tools | 250–700 ms |
| Responder stream (first token) | 2–3 s |
| Total end-to-end | 3–5 s |
| Refusal short-circuit | **0 ms** (no tokens spent) |
| Unit + safety tests | **27 / 27** |
| Live smoke (4 brands × 8 scenarios × sync + stream) | **32 / 32** |

### Research directions I would like to pursue with your group

1. **Reflection loops** — a critique agent that re-reads the answer
   and triggers additional tool calls when evidence is weak.
   Trade-off: +2-3 s latency for how much faithfulness gain?
2. **Multi-agent decomposition** — specialised sub-agents per
   sub-domain (diagnostics, maintenance, infotainment) with
   distinct tool sets and benchmarks.
3. **Planner robustness under `mode=ANY`** — current pre-filter is
   a regex; scaling this to open-domain small-talk detection is
   an interesting supervision problem.
4. **Grounding evaluation at scale** — automatable metric beyond
   my heuristic `looks_unavailable_answer` regex; probably
   requires a labelled benchmark.
5. **Provenance-preserving RRF** — keeping per-engine rank after
   fusion so the responder can weight BM25 vs dense signals.

---

<!-- _class: lead -->

# Thank you

Deployed: **[wallside.online](https://wallside.online)**
Source: **[github.com/aminssutt/AurisTraining](https://github.com/aminssutt/AurisTraining)**
Contact: **lakhdarberache@gmail.com**

Happy to walk you through the live system, the codebase,
or any design decision in depth.
