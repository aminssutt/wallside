"""E4b - LLM judgements of whether a clarification is worth asking (needs the Gemini API).

Model-free signals detect *that* a query is ambiguous (AUC ~0.86) but not *whether the answer changes*
across vehicles (AUC ~0.54). Two LLM detectors address the second question:
  prior        the LLM reads only the question: "does the answer depend on the vehicle model?"
               (CLAMBER-style direct ambiguity judgement; Zhang et al. 2024 report LLMs are weak at it)
  invariance   the LLM reads the best passage of each of the top-3 retrieved vehicles and says whether they
               give the same answer (answer-consistency signal, cf. Cole et al. 2023; CondAmbigQA 2025)
Outputs are cached like every other call, so the experiment is re-runnable at no cost.
"""
from __future__ import annotations

from ..llm import Gemini

PRIOR_SYSTEM = """You help a car owner's-manual assistant decide whether to ask which vehicle the user has.
Given a question that does not identify the vehicle, answer whether the correct answer would normally
DIFFER between car models (locations, procedures, values, controls, warning lights, features) or be the
SAME for essentially any car (generic safety advice, general driving knowledge)."""

PRIOR_SCHEMA = {
    "type": "object",
    "properties": {"depends_on_vehicle": {"type": "boolean"}, "confidence": {"type": "number"}, "reason": {"type": "string"}},
    "required": ["depends_on_vehicle", "confidence", "reason"],
}

INVARIANCE_SYSTEM = """You compare excerpts from the owner's manuals of different vehicles.
For the user's question, decide whether the excerpts give the SAME practical answer (same procedure, value,
location or advice) or DIFFERENT answers. If an excerpt does not address the question, ignore it."""

INVARIANCE_SCHEMA = {
    "type": "object",
    "properties": {"same_answer": {"type": "boolean"}, "n_relevant_excerpts": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["same_answer", "n_relevant_excerpts", "reason"],
}


class LLMClarificationDetector:
    def __init__(self, gemini: Gemini, model: str = "gemini-2.5-flash"):
        self.gemini, self.model = gemini, model

    def prior_requests(self, questions: list[str]) -> list[dict]:
        return [dict(prompt=f"Question: {q}", model=self.model, system=PRIOR_SYSTEM, temperature=0.0,
                     json_schema=PRIOR_SCHEMA, max_output_tokens=1024) for q in questions]

    def invariance_requests(self, questions: list[str], excerpts: list[list[tuple[str, str]]]) -> list[dict]:
        reqs = []
        for q, ex in zip(questions, excerpts):
            body = "\n\n".join(f"[{name}]\n{text[:1500]}" for name, text in ex)
            reqs.append(dict(prompt=f"Question: {q}\n\nExcerpts:\n{body}", model=self.model, system=INVARIANCE_SYSTEM,
                             temperature=0.0, json_schema=INVARIANCE_SCHEMA, max_output_tokens=1024))
        return reqs

    def p_depends_prior(self, questions: list[str]) -> list[float | None]:
        out = []
        for r in self.gemini.map_generate(self.prior_requests(questions), desc="LLM prior"):
            j = r.get("json") or {}
            if "depends_on_vehicle" not in j:
                out.append(None)
                continue
            c = min(max(float(j.get("confidence", 0.5)), 0.0), 1.0)
            out.append(c if j["depends_on_vehicle"] else 1.0 - c)
        return out

    def p_depends_invariance(self, questions: list[str], excerpts: list[list[tuple[str, str]]]) -> list[float | None]:
        out = []
        for r in self.gemini.map_generate(self.invariance_requests(questions, excerpts), desc="LLM invariance"):
            j = r.get("json") or {}
            out.append(None if "same_answer" not in j else (0.0 if j["same_answer"] else 1.0))
        return out
