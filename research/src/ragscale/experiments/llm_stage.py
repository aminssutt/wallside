"""E3 - The LLM stage: given retrieved passages, does the model cite the right document and answer correctly?

Conditions (all on the same stratified question sample):
  context_k   the top-k passages of a first-stage retriever (k in 1,3,5,10,20), searched over the full corpus
  labels      "anonymous" passages ([S1]...) vs "labelled" with manual name + page (what production sends)
  position    oracle context: the gold passage + (k-1) hardest non-relevant passages, gold placed
              first / middle / last (Lost in the Middle, Liu et al. 2023)

System under test answers with JSON {answer, cited_sources, abstain}. A separate grader model (a newer
Gemini generation, reference-based: it sees the gold answer and evidence) labels correctness; citation
and abstention metrics are computed deterministically from the gold rows.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .. import paths
from ..corpus import Corpus
from ..dataset.generate import read_jsonl
from ..llm import Gemini
from .runner import make_query

log = logging.getLogger(__name__)

ANSWER_SYSTEM = """You are the technical assistant of a car owner's-manual chatbot.
Answer the user's question using ONLY the numbered sources provided. Rules:
- If the sources do not contain the answer, set abstain=true and answer "NOT_FOUND".
- Otherwise answer concisely (max 80 words) in the language of the question.
- cited_sources: the ids (e.g. "S2") of the sources that directly support your answer, most important first.
- Do not use outside knowledge, do not guess values."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_sources": {"type": "array", "items": {"type": "string"}},
        "abstain": {"type": "boolean"},
    },
    "required": ["answer", "cited_sources", "abstain"],
}

GRADER_SYSTEM = """You grade answers of a car-manual chatbot against a reference.
You get the question, the reference answer, the verbatim evidence from the correct manual, and the
chatbot's answer. Label:
- "correct": contains the key information of the reference, no contradiction.
- "partial": some key information is right but important parts are missing or vague.
- "incorrect": wrong, contradicts the reference, or answers about something else.
- "abstained": the chatbot said it could not find the answer.
Numbers, units and procedure steps must match the reference to count as correct. Judge meaning, not wording."""

GRADER_SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": ["correct", "partial", "incorrect", "abstained"]},
                   "rationale": {"type": "string"}},
    "required": ["label", "rationale"],
}


@dataclass
class LLMStageSpec:
    name: str = "e3_llm_stage"
    dataset: str = "questions_v1"
    split: str = "test"
    n_questions: int = 300
    variant: str = "native_plain"
    retrieval_run: str = "e2_techniques"
    retriever: str = "rrf(bm25_stem,dense:bge-m3)"
    scope: str = "global"
    context_ks: list[int] = field(default_factory=lambda: [1, 3, 5, 10, 20])
    position_k: list[int] = field(default_factory=lambda: [5, 20])
    positions: list[str] = field(default_factory=lambda: ["first", "middle", "last"])
    answer_model: str = "gemini-2.5-flash"   # the production model = system under test
    grader_model: str = "gemini-3.5-flash"   # newer generation than the SUT; agreement audited on a sample
    seed: int = 7


def _stratified_sample(records: list[dict], n: int, seed: int) -> list[dict]:
    """Round-robin over manuals so every manual is represented before any gets a second question."""
    rng = np.random.default_rng(seed)
    by_manual: dict[str, list[dict]] = {}
    for r in records:
        by_manual.setdefault(r["manual"], []).append(r)
    for lst in by_manual.values():
        rng.shuffle(lst)
    manuals = sorted(by_manual)
    rng.shuffle(manuals)
    out, depth = [], 0
    while len(out) < n and any(len(v) > depth for v in by_manual.values()):
        for m in manuals:
            if len(by_manual[m]) > depth and len(out) < n:
                out.append(by_manual[m][depth])
        depth += 1
    return out


class LLMStage:
    def __init__(self, spec: LLMStageSpec, corpus: Corpus | None = None, gemini: Gemini | None = None):
        self.spec = spec
        self.corpus = corpus or Corpus.load()
        self.gemini = gemini or Gemini(max_workers=12)
        records = [r for r in read_jsonl(paths.DATASETS_DIR / f"{spec.dataset}.jsonl") if r["split"] == spec.split]
        self.records = _stratified_sample(records, spec.n_questions, spec.seed)
        self.out_dir = paths.RUNS_DIR / spec.name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.texts = self.corpus.chunks["text"].to_numpy()
        self.pages = self.corpus.chunks["page_label"].to_numpy()
        self.row_manual = self.corpus.chunks["manual"].to_numpy()

    def _rankings(self) -> dict[str, list[int]]:
        from .runner import _safe

        run_dir = paths.RUNS_DIR / self.spec.retrieval_run
        stem = f"{_safe(self.spec.retriever)}__{self.spec.variant}"
        metrics = pd.read_parquet(run_dir / f"metrics__{stem}.parquet", columns=["qid", "scope", "mask_idx"])
        rankings = pd.read_parquet(run_dir / f"rankings__{stem}.parquet")
        keep = metrics[metrics["scope"] == self.spec.scope][["qid", "mask_idx"]].drop_duplicates()
        merged = keep.merge(rankings, on=["qid", "mask_idx"])
        return {q: list(map(int, rows)) for q, rows in zip(merged["qid"], merged["rows"])}

    def _context(self, rows: list[int], labelled: bool) -> str:
        parts = []
        for i, r in enumerate(rows, 1):
            if labelled:
                name = self.corpus.manual_meta[self.row_manual[r]]["name"]
                header = f"[S{i}] (Manual: {name}, page {self.pages[r]})"
            else:
                header = f"[S{i}]"
            parts.append(f"{header}\n{self.texts[r]}")
        return "\n\n---\n\n".join(parts)

    def build_conditions(self) -> list[dict]:
        rankings = self._rankings()
        conds = []
        for r in self.records:
            ranked = rankings.get(r["qid"])
            if ranked is None:
                continue
            q = make_query(r, self.spec.variant)
            relevant = set(r["relevant_rows"]) | set(r["equivalent_rows"])
            for k in self.spec.context_ks:
                for labelled in (False, True):
                    conds.append({"qid": r["qid"], "kind": "context_k", "k": k, "labelled": labelled,
                                  "position": "", "rows": ranked[:k], "query": q.text})
            distractors = [x for x in ranked if x not in relevant]
            gold_row = r["source_row"]
            for k in self.spec.position_k:
                others = distractors[: k - 1]
                if len(others) < k - 1:
                    continue
                for pos in self.spec.positions:
                    idx = {"first": 0, "middle": (k - 1) // 2, "last": k - 1}[pos]
                    rows = others[:idx] + [gold_row] + others[idx:]
                    conds.append({"qid": r["qid"], "kind": "position", "k": k, "labelled": False,
                                  "position": pos, "rows": rows, "query": q.text})
        return conds

    def run(self) -> pd.DataFrame:
        conds = self.build_conditions()
        log.info("%d LLM conditions over %d questions", len(conds), len(self.records))
        answer_prompts = [dict(prompt=f"Sources:\n{self._context(c['rows'], c['labelled'])}\n\nQuestion: {c['query']}",
                               model=self.spec.answer_model, system=ANSWER_SYSTEM, temperature=0.0,
                               json_schema=ANSWER_SCHEMA, max_output_tokens=2048) for c in conds]
        answers = self.gemini.map_generate(answer_prompts, desc="answers")
        by_qid = {r["qid"]: r for r in self.records}
        grade_prompts = []
        for c, a in zip(conds, answers):
            r = by_qid[c["qid"]]
            ans = (a.get("json") or {}).get("answer", a.get("text", "")) if "error" not in a else "ERROR"
            grade_prompts.append(dict(
                prompt=json.dumps({"question": c["query"], "reference_answer": r["answer"], "evidence": r["evidence"],
                                   "chatbot_answer": ans}, ensure_ascii=False),
                model=self.spec.grader_model, system=GRADER_SYSTEM, temperature=0.0, json_schema=GRADER_SCHEMA,
                max_output_tokens=4096))
        grades = self.gemini.map_generate(grade_prompts, desc="grading")
        rows = [self._score(c, a, g, by_qid[c["qid"]]) for c, a, g in zip(conds, answers, grades)]
        df = pd.DataFrame(rows)
        df.to_parquet(self.out_dir / "llm_stage.parquet", index=False)
        (self.out_dir / "spec.json").write_text(json.dumps(asdict(self.spec), indent=2))
        (self.out_dir / "usage.json").write_text(json.dumps(self.gemini.usage.summary(), indent=2))
        return df

    def _score(self, c: dict, a: dict, g: dict, r: dict) -> dict:
        data = a.get("json") or {}
        cited = []
        for sid in data.get("cited_sources", []) or []:
            s = str(sid).strip().upper().lstrip("[").rstrip("]")
            if s.startswith("S") and s[1:].isdigit() and 1 <= int(s[1:]) <= len(c["rows"]):
                cited.append(c["rows"][int(s[1:]) - 1])
        strict = set(r["relevant_rows"])
        lenient = strict | set(r["equivalent_rows"])
        gold_in_context = bool(lenient & set(c["rows"]))
        abstain = bool(data.get("abstain")) or data.get("answer", "").strip().upper() == "NOT_FOUND"
        label = (g.get("json") or {}).get("label", "error")
        return {
            "qid": r["qid"], "manual": r["manual"], "kind": c["kind"], "k": c["k"], "labelled": c["labelled"],
            "position": c["position"], "gold_in_context": gold_in_context, "abstain": abstain,
            "answer_error": "error" in a or a.get("json") is None,
            "n_cited": len(cited),
            "cite_doc_correct": float(bool(cited) and self.row_manual[cited[0]] == r["manual"]),
            "cite_chunk_strict": float(bool(set(cited) & strict)),
            "cite_chunk_lenient": float(bool(set(cited) & lenient)),
            "grade": label,
            "correct": float(label == "correct"),
            "correct_or_partial": float(label in ("correct", "partial")),
            "answer": data.get("answer", ""),
            "grader_rationale": (g.get("json") or {}).get("rationale", ""),
            "specificity": r["specificity"], "question_type": r["question_type"],
        }
