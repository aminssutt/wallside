"""Build the HTML research report from results/ (every number comes from the experiment outputs).

    uv run python scripts/build_report.py --e1 e1_scaling_partial --e2 e2_techniques_partial \
        --e4 e4_clarification_partial --dataset questions_v1_partial --out reports/rapport.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ragscale import paths
from ragscale.experiments.plotstyle import label

TEMPLATE = Path(__file__).resolve().parents[1] / "reports" / "report_template.html"

E1_RETRIEVERS = [
    "bm25_stem", "dense:bge-m3", "wsum(bm25_stem,dense:bge-m3;w=0.3|0.7)",
    "wsum(bm25_stem+ctx,dense:bge-m3+ctx;w=0.3|0.7)", "name_router_strip(wsum(bm25_stem,dense:bge-m3;w=0.3|0.7))",
    "hnsw(dense:bge-m3)",
]
E1_METRICS = ["doc_hit@1", "chunk_hit@5"]


def _num(x):
    return None if pd.isna(x) else round(float(x), 4)


def corpus_block() -> dict:
    manuals = pd.read_parquet(paths.MANUALS_PATH)
    chunks = pd.read_parquet(paths.CHUNKS_PATH, columns=["manual", "garbled", "dup_manuals"])
    bad = manuals[manuals["garbled_share"] > 0.2].sort_values("garbled_share", ascending=False)
    return {
        "manuals": int(len(manuals)), "chunks": int(len(chunks)), "pages": int(manuals["page_count"].sum()),
        "vehicles": int(manuals["vehicle"].nunique()), "brands": int(manuals["brand_key"].nunique()),
        "lang_fr": int((manuals["lang"] == "fr").sum()), "lang_en": int((manuals["lang"] == "en").sum()),
        "garbled_chunks": int(chunks["garbled"].sum()), "shared_text_chunks": int((chunks["dup_manuals"] > 1).sum()),
        "garbled_manuals": [{"manual": m, "name": n, "share": round(float(s), 3)}
                            for m, n, s in zip(bad["manual"], bad["name"], bad["garbled_share"])],
        "duplicates": [{"manual": m, "of": d} for m, d in zip(manuals["manual"], manuals["duplicate_of"]) if d],
    }


def dataset_block(name: str) -> dict:
    meta = json.loads((paths.DATASETS_DIR / f"{name}.meta.json").read_text())
    audit_path = paths.DATASETS_DIR / f"{name}.audit.json"
    audit = json.loads(audit_path.read_text())["result"] if audit_path.exists() else None
    recs = [json.loads(l) for l in open(paths.DATASETS_DIR / f"{name}.jsonl", encoding="utf-8")]
    sample = recs[0]
    return {
        "name": name, "questions": meta["n_questions"], "manuals": meta["manuals_covered"], "splits": meta["splits"],
        "generator": meta["config"]["model"], "audit": audit,
        "specific_share": round(sum(r["specificity"] == "vehicle_specific" for r in recs) / len(recs), 3),
        "sample": {"manual": sample["manual"], "page": sample["page_label"], "queries": sample["queries"],
                   "answer": sample["answer"], "evidence": sample["evidence"]},
    }


def e1_block(run: str) -> dict:
    s = pd.read_csv(paths.RESULTS_DIR / run / "summary.csv", keep_default_na=False)
    s = s[(s["scope"] == "tier") & s["retriever"].isin(E1_RETRIEVERS)]
    out = []
    for _, r in s.iterrows():
        row = {"retriever": r["retriever"], "variant": r["variant"], "strategy": r["strategy"], "n": int(r["n_manuals"]),
               "questions": int(r["n_questions"])}
        for m in E1_METRICS:
            k = m.replace("@", "_")
            row[k], row[k + "_lo"], row[k + "_hi"] = _num(r[m]), _num(r[m + "_lo"]), _num(r[m + "_hi"])
        out.append(row)
    return {"rows": out, "retrievers": [{"spec": x, "label": label(x)} for x in E1_RETRIEVERS]}


def e2_block(run: str | None) -> dict | None:
    if not run or not (paths.RESULTS_DIR / run / "summary.csv").exists():
        return None
    s = pd.read_csv(paths.RESULTS_DIR / run / "summary.csv", keep_default_na=False)
    s = s[s["scope"].isin(["vehicle", "global"])]
    rows = []
    for _, r in s.iterrows():
        row = {"retriever": r["retriever"], "label": label(r["retriever"]), "variant": r["variant"], "scope": r["scope"],
               "questions": int(r["n_questions"])}
        for m in ("doc_hit@1", "chunk_hit@5", "ndcg@10"):
            k = m.replace("@", "_")
            row[k], row[k + "_lo"], row[k + "_hi"] = _num(r[m]), _num(r[m + "_lo"]), _num(r[m + "_hi"])
        rows.append(row)
    return {"rows": rows}


def e4_block(run: str) -> dict:
    d = paths.RESULTS_DIR / run
    pol = pd.read_csv(d / "policies.csv")
    by_var = pd.read_csv(d / "policies_by_variant.csv")
    det = json.loads((d / "detection.json").read_text())
    sig = pd.read_csv(d / "signal_auc.csv")
    ex = pd.read_csv(d / "examples.csv", keep_default_na=False)
    ex_meta = json.loads((d / "examples_meta.json").read_text())

    def policy_rows(df):
        rows = []
        for _, r in df.iterrows():
            row = {k: (r[k] if isinstance(r[k], str) else _num(r[k])) for k in df.columns if not k.endswith(("_lo", "_hi"))}
            for m in ("doc_hit@1", "chunk_hit@5"):
                row[m.replace("@", "_") + "_lo"], row[m.replace("@", "_") + "_hi"] = _num(r[m + "_lo"]), _num(r[m + "_hi"])
            rows.append({k.replace("@", "_"): v for k, v in row.items()})
        return rows

    dialogues, seen = [], set()
    for line in open(d / "dialogues.jsonl", encoding="utf-8"):
        g = json.loads(line)
        if g["policy"] != "name_rule" or g.get("strategy") != "direct" or not g["turns"]:
            continue
        key = g["variant"]
        if key in seen or not g["metrics"].get("chunk_hit@5"):
            continue
        seen.add(key)
        dialogues.append({"variant": g["variant"], "query": g["initial_query"], "top_manual": g["top_manual"],
                          "top_page": g["top_page"], "doc_ok": bool(g["metrics"].get("doc_hit@1")),
                          "turns": [{"q": t["question"], "options": t["options"], "a": t["user_answer"]} for t in g["turns"]]})
        if len(dialogues) == 3:
            break
    return {
        "policies": policy_rows(pol), "by_variant": policy_rows(by_var), "detection": det,
        "signals": [{"signal": r["signal"], "auc": _num(r["auc"]),
                     "generic_auc": _num(det.get("genericity_among_ambiguous", {}).get("signal_auc", {}).get(r["signal"]))}
                    for _, r in sig.iterrows()],
        "examples": ex[["id", "query", "expected", "predicted", "correct_action", "question", "options", "reason",
                        "top_manual", "top_page", "why_expected"]].to_dict("records"),
        "examples_meta": ex_meta, "dialogues": dialogues,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e1", default="e1_scaling_partial")
    ap.add_argument("--e2", default="e2_techniques_partial")
    ap.add_argument("--e4", default="e4_clarification_partial")
    ap.add_argument("--dataset", default="questions_v1_partial")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports" / "rapport.html"))
    ap.add_argument("--json", default=None, help="also write the raw data (used by the results website)")
    args = ap.parse_args()
    data = {"corpus": corpus_block(), "dataset": dataset_block(args.dataset), "e1": e1_block(args.e1),
            "e2": e2_block(args.e2), "e4": e4_block(args.e4)}
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html) / 1024:.0f} KB)")
    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False)
        target.write_text(payload, encoding="utf-8")
        print(f"wrote {target} ({len(payload) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
