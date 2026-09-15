"""Synthetic gold question set.

For each manual we sample source chunks spread over the whole document, ask a *different* Gemini
generation than the system under test to write an owner-style question answerable from that chunk,
and keep it only if the model's verbatim evidence span is really in the chunk. Gold relevance is then
defined at the text level: every chunk (in any manual) containing the evidence span is recorded, so
duplicated boilerplate is scored fairly (strict = right manual, lenient = any manual with the text).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..corpus import Corpus
from ..llm import Gemini
from ..text import content_tokens, lexical_overlap, normalize_for_match
from .names import fill, name_forms

log = logging.getLogger(__name__)

PROMPT_VERSION = "qgen-v1"

SYSTEM = """You build evaluation data for a retrieval benchmark over car owner's manuals.
You receive one passage from the manual of a specific vehicle. Write ONE question that a real owner of
that vehicle could plausibly type into a chatbot, and whose answer is contained in this passage.

Rules:
- The question must be answerable from the passage alone, with a precise answer (a value, a location, a
  procedure, the meaning of an indicator, a condition, a limitation...).
- Write it the way owners talk: everyday words, short, no references to "the passage", "the manual",
  "this section", page numbers or figure numbers.
- Do NOT copy distinctive wording from the passage. Paraphrase rare or technical terms with common words
  when a normal owner would (keep official feature names only if an owner would know them).
- Give the question in French and in English, each in two forms:
  * plain: no mention of the vehicle at all ("Comment régler l'heure de l'horloge ?")
  * named: the same question mentioning the vehicle with the literal placeholder {VEHICLE}
    exactly once, where the vehicle name naturally goes ("Comment régler l'heure sur ma {VEHICLE} ?")
- evidence: copy VERBATIM a contiguous span of 8 to 40 words from the passage that supports the answer.
- answer: short answer (max 40 words), in the language of the passage.
- specificity: "vehicle_specific" if the answer depends on this vehicle/model (values, locations, named
  systems, model-specific procedures); "generic" if nearly any car manual would give the same answer.
- Set usable=false (and leave other fields empty) if the passage is a table of contents, an index,
  legal/copyright text, garbled/unreadable text, a bare list of headings, or has no question-worthy fact."""

SCHEMA = {
    "type": "object",
    "properties": {
        "usable": {"type": "boolean"},
        "reason_if_unusable": {"type": "string"},
        "question_fr_plain": {"type": "string"},
        "question_fr_named": {"type": "string"},
        "question_en_plain": {"type": "string"},
        "question_en_named": {"type": "string"},
        "answer": {"type": "string"},
        "evidence": {"type": "string"},
        "question_type": {
            "type": "string",
            "enum": ["value", "procedure", "location", "indicator_meaning", "feature_usage", "safety_warning",
                     "maintenance", "condition_or_limit", "other"],
        },
        "specificity": {"type": "string", "enum": ["vehicle_specific", "generic"]},
    },
    "required": ["usable", "question_fr_plain", "question_fr_named", "question_en_plain", "question_en_named",
                 "answer", "evidence", "question_type", "specificity"],
}


@dataclass
class GenConfig:
    model: str = "gemini-3.5-flash"
    per_manual: int = 6
    oversample: float = 1.8
    min_chars: int = 350
    max_chars: int = 2200
    seed: int = 20260915
    test_share: float = 0.7


def sample_source_chunks(corpus: Corpus, cfg: GenConfig) -> pd.DataFrame:
    """Spread candidates over each manual: split eligible chunks into equal position bins and draw one per bin."""
    rng = np.random.default_rng(cfg.seed)
    chunks = corpus.chunks
    duplicate_manuals = {m for m, meta in corpus.manual_meta.items() if meta["duplicate_of"]}
    originals = chunks[~chunks["manual"].isin(duplicate_manuals)]
    # Text shared with another (non-duplicate) manual cannot identify a single gold document.
    manuals_per_hash = originals.groupby("norm_hash")["manual"].nunique()
    eligible = originals[
        (originals["n_chars"].between(cfg.min_chars, cfg.max_chars))
        & (~originals["garbled"])
        & (originals["norm_hash"].map(manuals_per_hash) == 1)
        & (originals["page_start"].notna())
    ]
    picks = []
    n_draw = int(round(cfg.per_manual * cfg.oversample))
    for manual, meta in corpus.manual_meta.items():
        if meta["duplicate_of"]:
            continue  # identical PDF indexed twice (mazda-cx-5 == mazda-3): keep only the first as a question source
        pool = eligible[eligible["manual"] == manual]
        if len(pool) < cfg.per_manual:
            log.warning("%s: only %d eligible chunks", manual, len(pool))
        if pool.empty:
            continue
        bins = np.array_split(pool.index.to_numpy(), min(n_draw, len(pool)))
        drawn = [int(rng.choice(b)) for b in bins if len(b)]
        rng.shuffle(drawn)
        for rank, idx in enumerate(drawn):
            picks.append({"row": idx, "draw_rank": rank})
    out = chunks.loc[[p["row"] for p in picks]].copy()
    out["draw_rank"] = [p["draw_rank"] for p in picks]
    return out


def _prompt(vehicle_name: str, lang: str, text: str) -> str:
    return (
        f"Vehicle: {vehicle_name}\n"
        f"Passage language: {'French' if lang == 'fr' else 'English'}\n"
        f"Passage:\n<<<\n{text}\n>>>"
    )


def evidence_coverage(evidence: str, passage: str) -> float:
    """Share of evidence tokens found in order in the passage (1.0 = exact verbatim match after normalization)."""
    ev, ps = normalize_for_match(evidence), normalize_for_match(passage)
    if not ev:
        return 0.0
    if ev in ps:
        return 1.0
    a, b = ev.split(), ps.split()
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(a)


def _valid(item: dict | None) -> tuple[bool, str]:
    if not item:
        return False, "no_json"
    if not item.get("usable"):
        return False, "unusable:" + (item.get("reason_if_unusable") or "")[:80]
    for key in ("question_fr_named", "question_en_named"):
        if item.get(key, "").count("{VEHICLE}") != 1:
            return False, f"placeholder:{key}"
    for key in ("question_fr_plain", "question_en_plain"):
        if "{VEHICLE}" in item.get(key, "") or len(item.get(key, "")) < 8:
            return False, f"plain:{key}"
    if len(item.get("evidence", "").split()) < 5:
        return False, "short_evidence"
    return True, ""


def generate_questions(corpus: Corpus, cfg: GenConfig, gemini: Gemini | None = None, limit_manuals: int | None = None):
    gemini = gemini or Gemini(max_workers=12)
    sources = sample_source_chunks(corpus, cfg)
    if limit_manuals:
        keep = sorted(sources["manual"].unique())[:limit_manuals]
        sources = sources[sources["manual"].isin(keep)]
    requests = []
    for rec in sources.itertuples():
        meta = corpus.manual_meta[rec.manual]
        requests.append(
            dict(
                prompt=_prompt(meta["name"], meta["lang"], rec.text),
                model=cfg.model,
                system=SYSTEM,
                temperature=0.4,
                json_schema=SCHEMA,
                max_output_tokens=2048,
                cache_tag=f"{PROMPT_VERSION}:{cfg.seed}",
            )
        )
    responses = gemini.map_generate(requests, desc="question generation")

    norm_texts = [normalize_for_match(t) for t in corpus.chunks["text"]]
    kept, rejected = [], []
    per_manual_count: dict[str, int] = {}
    for rec, resp in zip(sources.itertuples(), responses):
        item = resp.get("json")
        ok, why = _valid(item)
        coverage = evidence_coverage(item["evidence"], rec.text) if ok else 0.0
        if ok and coverage < 0.9:
            ok, why = False, f"evidence_not_in_passage:{coverage:.2f}"
        if ok and per_manual_count.get(rec.manual, 0) >= cfg.per_manual:
            ok, why = False, "manual_quota_full"
        if not ok:
            rejected.append({"manual": rec.manual, "chunk_id": rec.chunk_id, "reason": why or resp.get("error", "")})
            continue
        per_manual_count[rec.manual] = per_manual_count.get(rec.manual, 0) + 1
        kept.append(_build_record(corpus, rec, item, coverage, norm_texts, cfg))
    return kept, rejected, gemini.usage.summary()


def _build_record(corpus: Corpus, rec, item: dict, coverage: float, norm_texts: list[str], cfg: GenConfig) -> dict:
    meta = corpus.manual_meta[rec.manual]
    forms = name_forms(meta["name"], meta["brand"])
    ev_norm = normalize_for_match(item["evidence"])
    matches = [i for i, t in enumerate(norm_texts) if ev_norm in t] if coverage == 1.0 else []
    if rec.row not in matches:
        matches.append(int(rec.row))
    match_manuals = corpus.chunks["manual"].to_numpy()[matches]
    relevant = sorted(int(r) for r, m in zip(matches, match_manuals) if m == rec.manual)
    equivalent = sorted(int(r) for r, m in zip(matches, match_manuals) if m != rec.manual)

    qid = "q" + hashlib.sha1(f"{rec.chunk_id}|{PROMPT_VERSION}|{cfg.seed}".encode()).hexdigest()[:10]
    split = "test" if int(qid[1:9], 16) / 0xFFFFFFFF < cfg.test_share else "dev"
    queries = {}
    for lang in ("fr", "en"):
        queries[f"{lang}_plain"] = item[f"question_{lang}_plain"].strip()
        for form, value in forms.items():
            queries[f"{lang}_{form}"] = fill(item[f"question_{lang}_named"], value)
    return {
        "qid": qid,
        "split": split,
        "manual": rec.manual,
        "vehicle": meta["vehicle"],
        "brand_key": meta["brand_key"],
        "manual_lang": meta["lang"],
        "source_chunk_id": rec.chunk_id,
        "source_row": int(rec.row),
        "page_label": rec.page_label,
        "queries": queries,
        "answer": item["answer"].strip(),
        "evidence": item["evidence"].strip(),
        "evidence_coverage": round(coverage, 4),
        "question_type": item["question_type"],
        "specificity": item["specificity"],
        "relevant_rows": relevant,
        "equivalent_rows": equivalent,
        "equivalent_manuals": sorted(set(corpus.chunks["manual"].to_numpy()[equivalent].tolist())),
        "lexical_overlap_plain": round(lexical_overlap(queries[f"{meta['lang']}_plain"], rec.text), 4),
        "n_query_content_tokens": len(content_tokens(queries[f"{meta['lang']}_plain"])),
        "generator": {"model": cfg.model, "prompt_version": PROMPT_VERSION, "seed": cfg.seed},
    }


def write_jsonl(records: list[dict], path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
