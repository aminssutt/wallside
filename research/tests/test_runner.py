import json

import numpy as np

from ragscale import paths
from ragscale.experiments.analysis import summarize
from ragscale.experiments.runner import ExperimentSpec, Runner


def _question(qid, manual, row, query_fr, lang="fr"):
    return {"qid": qid, "split": "test", "manual": manual, "vehicle": manual.replace("-media", ""), "brand_key": "x",
            "manual_lang": lang, "source_chunk_id": f"{manual}::00000", "source_row": row, "page_label": "10",
            "queries": {"fr_plain": query_fr, "en_plain": query_fr, "fr_model": query_fr, "en_model": query_fr,
                        "fr_full": query_fr, "en_full": query_fr, "fr_brand": query_fr, "en_brand": query_fr},
            "answer": "", "evidence": "", "evidence_coverage": 1.0, "question_type": "value",
            "specificity": "vehicle_specific", "relevant_rows": [row], "equivalent_rows": [], "equivalent_manuals": [],
            "lexical_overlap_plain": 0.5, "n_query_content_tokens": 2}


def test_runner_end_to_end_on_tiny_corpus(tiny_corpus):
    records = [
        _question("q1", "peugeot-2008", 2, "capacité du réservoir 52 litres"),
        _question("q2", "renault-clio-media", 6, "connexion bluetooth du téléphone"),
    ]
    with open(paths.DATASETS_DIR / "tiny.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in records)
    spec = ExperimentSpec(name="tiny", dataset="tiny", retrievers=["bm25"], variants=["native_plain"],
                          scopes=["manual", "vehicle", "global", "tiers"], tiers=[1, 2, 4], strategies=["random"],
                          seeds=2, k=5, batch=1)
    runner = Runner(spec, corpus=tiny_corpus)
    metrics_df, rankings_df = runner._run_one("bm25", "native_plain", spec.scope_list())
    assert len(metrics_df) == 2 * (3 + 3 * 2)  # (manual, vehicle, global + 3 tiers x 2 seeds) per question
    q1 = metrics_df[metrics_df["qid"] == "q1"].set_index("scope_label")
    assert q1.loc["global", "doc_hit@1"] == 1 and q1.loc["global", "chunk_hit@1"] == 1
    assert (metrics_df["n_manuals"][metrics_df["scope"] == "tier"].isin([1, 2, 4])).all()
    # identical manual sets (tier1 == manual, tier4 == global) are computed once per question
    assert rankings_df.groupby("qid")["mask_idx"].nunique().max() <= 1 + 1 + 2 + 1
    summary = summarize(metrics_df)
    vehicle = summary[summary["scope"] == "vehicle"]
    assert len(vehicle) == 1 and vehicle["n_questions"].iloc[0] == 2
    assert np.isclose(summary[summary["scope"] == "manual"]["chunk_hit@5"].iloc[0], 1.0)
