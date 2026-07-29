# Wallside — Numbers & Architecture Cheat-Sheet

Source material for slides / reports. Every figure below was pulled
directly from the repository and the deployed system on
**2026-04-18**. Re-running the measurement commands at the bottom of
the file will refresh them.

---

## 1 · Data & scale

| Metric | Value | Source |
|---|---|---|
| Distinct vehicle models surfaced | **154** | `guide_manager.list_guides()` |
| Supplementary sub-system manuals | **12** | infotainment / multimedia / quick-reference entries not listed as stand-alone vehicles |
| **Total knowledge sources in the corpus** | **166** | 154 + 12, all with FAISS + BM25 |
| Manifest entries (raw) | **165** | `backend/data/guides/manifest.json` (one duplicate slug filtered out by list_guides) |
| Distinct brands covered | **35** | set of `brand` in manifest |
| Total manual pages ingested | **62 712** | sum of `page_count` |
| Total retrieval chunks stored | **138 087** | sum of `chunk_count` |
| Pre-built FAISS + BM25 index size on disk | **≈ 2.0 GB** | `du -sh backend/data/guides` |
| Guides with external PDF preview URL | **149 / 165** (90 %) | inspirauto.fr `pdf_url` field |
| Languages supported (user-facing) | **3** — French · English · Korean | `LANG_INSTRUCTIONS` / `LANG_OFF_TOPIC` / `LANG_QUESTION_RESPONSE` |
| Vehicle brands with dedicated official-domain map | **36** | `_OFFICIAL_DOMAINS` in `backend/src/agent/tools.py` |

Brands covered (non-exhaustive): Alfa Romeo · Alpine · Audi · BMW ·
Chevrolet · Citroën · Cupra · Dacia · DS · Fiat · Ford · Genesis ·
Honda · Hyundai · Jaguar · Jeep · Kia · Lancia · Land Rover · Lexus ·
Maserati · Mazda · Mercedes-Benz · Mini · Mitsubishi · Nissan · Opel ·
Peugeot · Renault · Seat · Skoda · Subaru · Suzuki · Tesla · Toyota ·
Volkswagen · Volvo.

---

## 2 · System architecture (agentic workflow)

```
  user question (FR / EN / KO)
         │
         ▼
 ┌───────────────────────┐
 │  SAFETY TRIAGE         │  pre-LLM regex (accent-folded)
 │  - credential patterns │  ────► REFUSE in 0 ms
 │  - jailbreak / role-play│         localised response, no tokens
 │  - infra probing       │
 │  - safety-system tamper│
 └──────────┬────────────┘
            │ allow
            ▼
 ┌───────────────────────────────────────────┐
 │  GREETING / META-QUESTION FILTER           │
 │  ("ça va ?", "merci", "do you speak KO ?") │  ────► canned reply, 0 ms
 └──────────┬────────────────────────────────┘
            │ real question
            ▼
 ┌───────────────────────────────────────────────────┐
 │  PLANNER   (Gemini 2.5 Flash-Lite, temperature 0) │
 │  function_calling_config.mode = ANY               │
 │  emits ≤ 4 tool calls from 3 declared tools       │
 │                                                   │
 │  [{name:"search_manual", args:{query:...}},       │
 │   {name:"search_web",    args:{query:..., lang}}, │
 │   {name:"search_youtube",args:{query:...}}, ...]  │
 └──────────┬────────────────────────────────────────┘
            │ tool calls
            ▼
 ┌─────────────────────────────────────────────────────────┐
 │  PARALLEL DISPATCH  (ThreadPoolExecutor, up to 3 workers) │
 │                                                          │
 │  search_manual       search_web              search_youtube│
 │  └─► FAISS (3072-d) + BM25 fused via Reciprocal Rank    │
 │      Fusion (k = 60)                                     │
 │  └─► 2 parallel DDGS queries: raw + site:<official>      │
 │      URL+domain de-dup, ≤ 2 per domain                  │
 │  └─► 6 language variants (EN / FR / KO)                 │
 │                                                          │
 │  Every tool output is sanitised (HTML stripped,          │
 │  injection phrases redacted, 1 600-char cap).            │
 └──────────┬───────────────────────────────────────────────┘
            │ evidence block
            ▼
 ┌───────────────────────────────────────────────────┐
 │  RESPONDER   (Gemini 2.5 Flash, temperature 0.15) │
 │  streamed over SSE                                │
 │  grounded strictly on the evidence                │
 │  rules: no fabricated numbers · metric-first unit │
 │  conversion · no inline "selon la page X"         │
 │  · standard automotive checklist fallback for     │
 │    general procedural questions                   │
 └──────────┬────────────────────────────────────────┘
            │ tokens + end payload
            ▼
     ChatPage (React 19, SSE consumer)
     status chips :  manual_search → web_search → generating
     message      :  streamed tokens
     sources      :  clickable citations (inspirauto #page=N)
```

### Three tools exposed to the planner

| Tool | Backend | Key property |
|---|---|---|
| `search_manual` | Hybrid FAISS + BM25 over the selected guide | Returns up to `TOP_K_RESULTS` chunks with `(source_file, page)` metadata; dedup keeps diverse pages |
| `search_web` | `ddgs` (DuckDuckGo + Brave + Yandex + Wikipedia + Grokipedia) | Fires the planner's query **and** a parallel `site:<manufacturer>` query. Region switches per user language (`fr→fr-fr`, `ko→kr-kr`, `en→us-en`). May emit two `search_web` with different languages. |
| `search_youtube` | `ddgs` → YouTube | Worldwide by default (`wt-wt`). Probes 6 query variants to reach EN, FR and KO tutorials. |

---

## 3 · Safety, three defence layers

| Layer | Where | What it blocks |
|---|---|---|
| **Input triage** | `backend/src/agent/safety.py::assess_input_safety` — regex, accent-folded, pre-LLM | Credential extraction (`API key`, `GOOGLE_API_KEY`, `.env`, `secret`, `password`), prompt injection (`ignore previous instructions`, role-play jailbreaks, developer-mode), infra probing (`list all guides`, `dump database`), SSRF + `file://` + `../` + `/etc/passwd`, safety-system tampering (disable airbag / ABS / SRS / immobiliser / seatbelt, roll back odometer or ECU). Refusal in **0 ms**, no tokens spent. |
| **Tool output sanitisation** | `safety.py::sanitize_tool_text` | Strips HTML tags, `javascript:` URIs, redacts embedded "ignore previous instructions" text, caps snippet length to 1 600 chars before the responder sees it. |
| **Model guardrail** | `SAFETY_GUARDRAIL` system-prompt string appended to planner + responder | Forbids revealing system prompts / tool schemas / environment variables / API keys. Instructs the model to treat EVIDENCE strictly as data. Refuses safety-system tampering requests and redirects to a professional. |

---

## 4 · Performance (measured on production)

| Stage | Latency |
|---|---|
| Safety refusal (adversarial input) | **0 ms** (no LLM call) |
| Greeting short-circuit ("ça va ?", "salut") | **0 ms** (pre-LLM regex) |
| Planner (Gemini 2.5 Flash-Lite) | 700 – 1 200 ms |
| Parallel tool dispatch | 250 – 700 ms |
| Responder first token (streamed) | **2 – 3 s** |
| Full end-to-end stream | **3 – 5 s** typical, up to 10 s on heavy procedural queries |

Every stage timing is logged under `auris.agent.*` so per-query
performance is traceable in prod.

---

## 5 · Code structure & test coverage

| Component | Path | Python LOC |
|---|---|---|
| Agent package (7 modules) | `backend/src/agent/` | **1 949** |
| ↳ `orchestrator.py` | run_agent + stream_agent | 312 |
| ↳ `tools.py` | 3 tools + parallel dispatch + official-domain map | 466 |
| ↳ `responder.py` | evidence builder + streaming composer | 315 |
| ↳ `safety.py` | 3-layer safety + localised refusals | 277 |
| ↳ `bridge.py` | legacy SSE wire adapter | 232 |
| ↳ `planner.py` | Gemini function-calling planner | 176 |
| ↳ `schemas.py` | function declarations | 148 |
| Agent unit + safety tests | `backend/tests/test_agent_*.py` | 356 |
| Flask API (routes, SSE, CORS, rate limit) | `backend/api.py` | 912 |
| Core chatbot + retrieval engine | `backend/src/guide_chatbot.py` | 2 716 |
| **Total agent-related Python** | | **≈ 5 900 LOC** |

Tests:

- `pytest backend/tests/test_agent_units.py` — 9 passed
- `pytest backend/tests/test_agent_safety.py` — 18 passed
- Live smoke `backend/tests/smoke_agent.py` on 4 brands × 8 scenarios
  × sync + stream — **32 / 32 passed**

---

## 6 · Stack summary

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.5 Flash (responder) + Flash-Lite (planner) |
| Embeddings | `gemini-embedding-001` (3 072-d) |
| Dense retrieval | FAISS with L2 |
| Sparse retrieval | BM25 via `rank_bm25` |
| Fusion | Reciprocal Rank Fusion (k = 60) |
| Web search | `ddgs` library → DuckDuckGo, Wikipedia, Brave, Yandex, Grokipedia, Mojeek |
| Backend framework | Flask 3 + Gunicorn (gthread) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | React 19 · Vite · React Router · Framer Motion |
| Rate limiting | Flask-Limiter (15 requests / minute per IP) |
| Deploy | Docker Compose on Dokploy behind Traefik |
| Live URL | [wallside.online](https://wallside.online) |

---

## 7 · Headline figures to use on slides

If you only want a handful of bullets:

- **154 vehicle models + 12 sub-system manuals = 166 indexed sources** across **35 brands**, 3 languages
- **62 712 pages / 138 087 chunks** in the hybrid FAISS + BM25 store
- **Two-stage agentic loop** — planner (Gemini Flash-Lite) +
  parallel tool dispatcher + streamed responder (Gemini Flash)
- **3 autonomous tools**: manual retrieval, multi-site web search
  with official-domain boost, worldwide YouTube
- **3-layer safety**: pre-LLM triage (0 ms refusal), tool output
  sanitisation, system-prompt guardrail
- **3–5 s** end-to-end latency, **2–3 s** first token, **0 ms** on
  refusals and greetings
- **27 / 27** unit + safety tests, **32 / 32** live smoke across
  4 brands, sync + stream

---

## 8 · How to refresh these numbers

```bash
# Data metrics
python - <<'PY'
import json
with open('backend/data/guides/manifest.json') as f:
    data = json.load(f)
print("entries :", len(data))
print("brands  :", len({e['brand'] for e in data if e.get('brand')}))
print("pages   :", sum(int(e.get('page_count') or 0) for e in data))
print("chunks  :", sum(int(e.get('chunk_count') or 0) for e in data))
print("pdf_url :", sum(1 for e in data if e.get('pdf_url')))
PY

# Code size
wc -l backend/src/agent/*.py backend/api.py \
      backend/src/guide_chatbot.py backend/tests/test_agent_*.py

# Tests
cd backend && python -m pytest tests/test_agent_units.py \
    tests/test_agent_safety.py -q

# Live smoke (needs GOOGLE_API_KEY)
cd backend && SMOKE_GUIDE_LIMIT=4 SMOKE_STREAM=1 \
    python tests/smoke_agent.py
```
