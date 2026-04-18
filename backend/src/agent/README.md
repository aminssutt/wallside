# Agentic chat

Tool-calling agent that powers `GuideChatbot.chat()` and
`GuideChatbot.chat_stream()`. It replaces the previous "linear pipeline"
(classify → retrieve → maybe web → generate) with a two-stage LLM loop
that lets the model decide **which** tools to call and **with what
arguments**.

## Pipeline

```
user question
      │
      ▼
┌─────────────┐
│  planner    │  small / fast Gemini model, forced function-call mode
│             │  returns up to 3 ToolCall(name, args)
└──────┬──────┘
       │
       ▼
┌───────────────────────────────────────┐
│  ThreadPoolExecutor (max 3 workers)   │
│  search_manual │ search_web │ youtube │
└──────┬────────────────────────────────┘
       │
       ▼
┌─────────────┐
│ responder   │  main Gemini model, streamed
│             │  receives EVIDENCE block + history + question
└──────┬──────┘
       │
       ▼
  final answer + deterministic Sources block
```

Every stage is its own module so tracing, testing and swapping stays
simple.

## Files

| File | Responsibility |
|------|----------------|
| `schemas.py` | Gemini `FunctionDeclaration`s for `search_manual`, `search_web`, `search_youtube`. |
| `tools.py` | `ToolResult`/`Citation` dataclasses + parallel dispatcher (`run_tools_in_parallel`). |
| `planner.py` | `plan_tool_calls` — picks tools via Gemini function-calling with `mode=ANY`. Includes a deterministic fallback so the pipeline never stalls. |
| `responder.py` | Builds the evidence block, calls Gemini (sync or streaming) and flattens citations (`collect_citations`, `render_sources_block`). |
| `orchestrator.py` | Ties everything together. Exposes `run_agent` and `stream_agent`. Emits timing metrics and logs. |
| `safety.py` | Pre-LLM input triage, tool-output sanitisation and the `SAFETY_GUARDRAIL` string appended to every system prompt. |

## Safety layers

The agent is hardened against prompt injection, credential extraction and
unsafe advice through three independent layers:

1. **Input triage** (`assess_input_safety`) runs before the planner. It
   folds accents, then matches against a hard blocklist (API keys, system
   prompt dumps, "ignore previous instructions", infra probing, dangerous
   safety-system tampering). A hit short-circuits the pipeline with a
   deterministic localised refusal — no tokens are spent.

2. **Tool-output sanitisation** (`sanitize_tool_text`) strips HTML tags,
   `javascript:` URIs and literal "ignore previous instructions" phrases
   from every piece of tool output. Long outputs are truncated so the
   responder prompt stays bounded.

3. **Model guardrails** — `SAFETY_GUARDRAIL` is appended to the planner
   and responder system instructions. It tells Gemini to refuse to
   reveal internal configuration, to treat evidence blocks strictly as
   data (never instructions), and to refuse requests that would bypass
   a vehicle safety system.

Unit tests in `backend/tests/test_agent_safety.py` cover each refusal
path in FR / EN / KO, soft-injection detection, and tool-output sanitiser
edge cases.

## Latency budget

| Stage | Target | Notes |
|-------|--------|-------|
| Planner | ~600–1200 ms | Short prompt, tool-call-only output. Set `LLM_PLANNER_MODEL` to a faster Gemini variant to cut this. |
| Tools (parallel) | ~500–2000 ms | Manual search is sub-100 ms locally; web + YouTube dominate. |
| Responder | ~1.5–3.5 s (stream) | First token shows up within a few hundred ms of the tool results landing. |
| **End-to-end** | **~3–5 s** | ~1–2 s more than the old linear pipeline, in exchange for real tool autonomy and citation honesty. |

All stage timings are logged under the `auris.agent.*` logger and
attached to the `AgentAnswer.timings_ms` dict for observability.

## Error handling

* Tools never raise: they return `ToolResult(ok=False, error=...)` which
  the responder treats as "this source was unavailable".
* If the planner call itself errors out, a deterministic fallback plan
  searches the manual with the raw question so the user still gets an
  answer.
* If the responder errors, the orchestrator returns a short localized
  error string without citations.

## Citation rule

Only citations carried by **successful** tool results are shown to the
user. A failed web search never produces "Aucune page précise…" noise,
and a manual search that returned zero chunks contributes nothing to
the Sources block.

## Extending the agent

* **New tool**: add a `FunctionDeclaration` in `schemas.py`, a handler in
  `tools.py` (registered in `_DISPATCH`), and describe it in the
  planner system prompt so Gemini knows when to pick it.
* **Reflection loop**: wrap `run_agent` in a second pass that re-reads
  the answer and can request more tool calls. Keep it opt-in behind an
  env flag — it roughly doubles latency.
* **Smaller planner**: set `LLM_PLANNER_MODEL=gemini-2.5-flash-lite`
  (or equivalent) in the environment.
