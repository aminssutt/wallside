"""Assemble a Markdown research report from the results directory (tables, figures, examples, diagrams).

Every number in the report is read from results/*.csv|json written by the experiments; nothing is typed in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import paths

ARCHITECTURE = """```mermaid
flowchart LR
    Q[User question] --> D{Decision agent}
    D -->|off-topic or unknown brand| A[Abstain: no manual]
    D -->|several vehicles, answer depends on vehicle| C[Clarifying question + options]
    C -->|user picks a vehicle| F[Filter to that vehicle's manuals]
    D -->|one vehicle named| F
    D -->|generic question| G[Search all manuals]
    F --> S[Strip vehicle name from query]
    S --> R[Hybrid retrieval: 0.3 BM25 + 0.7 bge-m3]
    G --> R
    R --> L[LLM answer with cited pages]
```"""

DECISION_FLOW = """```mermaid
flowchart TD
    start([Question]) --> brand{Names a brand with no manual?}
    brand -->|yes| abstain1[ABSTAIN: manual not available]
    brand -->|no| topic{Max similarity to corpus below in-domain 1st percentile?}
    topic -->|yes| abstain2[ABSTAIN: off-topic]
    topic -->|no| named{How many vehicles does the query name?}
    named -->|exactly one| answer1[ANSWER inside that vehicle]
    named -->|several versions| ask1[CLARIFY: which version?]
    named -->|none| detector{Detector: needs clarification?}
    detector -->|no| answer2[ANSWER over all manuals]
    detector -->|yes| ask2[CLARIFY: which vehicle? top-3 options]
```"""


def _fmt_ci(row: pd.Series, metric: str) -> str:
    return f"{100 * row[metric]:.1f} [{100 * row[metric + '_lo']:.1f}-{100 * row[metric + '_hi']:.1f}]"


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def technique_table(run: str, retrievers: list[str], scope: str, metric: str, variants: list[str]) -> str:
    s = pd.read_csv(paths.RESULTS_DIR / run / "summary.csv", keep_default_na=False)
    s = s[s["scope"] == scope]
    rows = []
    for r in retrievers:
        row = {"retriever": f"`{r}`"}
        for v in variants:
            hit = s[(s["retriever"] == r) & (s["variant"] == v)]
            row[v] = _fmt_ci(hit.iloc[0], metric) if len(hit) else "-"
        rows.append(row)
    return _table(pd.DataFrame(rows))


def scaling_table(run: str, retrievers: list[str], variant: str, metric: str, strategy: str) -> str:
    s = pd.read_csv(paths.RESULTS_DIR / run / "summary.csv", keep_default_na=False)
    s["n_manuals"] = s["n_manuals"].astype(int)
    t = s[(s["scope"] == "tier") & (s["variant"] == variant) & (s["strategy"] == strategy) & s["retriever"].isin(retrievers)]
    p = (100 * t.pivot_table(index="retriever", columns="n_manuals", values=metric)).round(1)
    p = p.reindex([r for r in retrievers if r in p.index])
    p.index = [f"`{i}`" for i in p.index]
    return _table(p.reset_index().rename(columns={"index": "retriever"}))


def policy_table(run: str) -> str:
    p = pd.read_csv(paths.RESULTS_DIR / run / "policies.csv")
    keep = p[p["strategy"].isin(["none", "direct", "hierarchical"]) & ~p["policy"].isin(["classifier@0.2"])]
    out = pd.DataFrame({
        "question strategy": keep["strategy"], "policy": keep["policy"],
        "right manual @1 [95% CI]": [_fmt_ci(r, "doc_hit@1") for _, r in keep.iterrows()],
        "right passage @5 [95% CI]": [_fmt_ci(r, "chunk_hit@5") for _, r in keep.iterrows()],
        "questions / query": keep["avg_turns"].round(2),
        "missed clarifications %": (100 * keep["missed_clarification"]).round(1),
        "unneeded clarifications %": (100 * keep["unnecessary_clarification"]).round(1),
    })
    return _table(out)


def example_dialogues(run: str, n: int = 4) -> str:
    dialogues = [json.loads(l) for l in open(paths.RESULTS_DIR / run / "dialogues.jsonl", encoding="utf-8")]
    picked, seen = [], set()
    for d in dialogues:
        key = (d["variant"], bool(d["turns"]), d["metrics"].get("doc_hit@1", 0) == 1)
        if d["policy"] == "name_rule" and d.get("strategy") == "direct" and key not in seen and d["turns"]:
            seen.add(key)
            picked.append(d)
        if len(picked) >= n:
            break
    blocks = []
    for d in picked:
        lines = [f"**Query ({d['variant']})**: {d['initial_query']}"]
        for t in d["turns"]:
            lines.append(f"- *Assistant*: {t['question']} Options: {' / '.join(t['options'])}")
            lines.append(f"- *User*: {t['user_answer']}")
        ok = "right manual" if d["metrics"].get("doc_hit@1") else "wrong manual"
        lines.append(f"- *Retrieved*: `{d['top_manual']}` page {d['top_page']} ({ok}; passage in top-5: {bool(d['metrics'].get('chunk_hit@5'))})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def examples_table(run: str) -> str:
    ex = pd.read_csv(paths.RESULTS_DIR / run / "examples.csv", keep_default_na=False)
    out = pd.DataFrame({
        "id": ex["id"], "query": ex["query"], "expected": ex["expected"], "decision": ex["predicted"],
        "ok": ex["correct_action"].map({True: "yes", False: "**no**"}),
        "clarifying question / reason": [q if q else r for q, r in zip(ex["question"], ex["reason"])],
        "options": ex["options"],
    })
    return _table(out)


def write_report(sections: dict[str, str], out: Path) -> Path:
    body = []
    for title, content in sections.items():
        body.append(f"## {title}\n\n{content}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(body), encoding="utf-8")
    return out
