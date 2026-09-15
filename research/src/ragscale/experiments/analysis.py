"""Aggregate run metrics into tables with 95% CIs, significance tests and figures."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .. import paths
from ..stats import holm, mean_ci, paired_permutation_test

log = logging.getLogger(__name__)

HEADLINE = ["doc_hit@1", "doc_hit@3", "doc_rr", "chunk_hit@1", "chunk_hit@5", "chunk_hit@10", "chunk_rr@10",
            "ndcg@10", "page_hit@1", "page_hit@5", "doc_hit@1_lenient", "chunk_hit@5_lenient",
            "confusion_same_vehicle", "confusion_same_brand", "confusion_other_brand"]
CONDITION = ["retriever", "variant", "scope", "n_manuals", "strategy"]


def load_run(name: str) -> pd.DataFrame:
    files = sorted((paths.RUNS_DIR / name).glob("metrics__*.parquet"))
    if not files:
        raise FileNotFoundError(f"no metrics in {paths.RUNS_DIR / name}")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def per_question(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    """Average seeds within each question so the question is the statistical unit."""
    return df.groupby(CONDITION + ["qid"], dropna=False)[metrics].mean().reset_index()


def summarize(df: pd.DataFrame, metrics: list[str] = HEADLINE) -> pd.DataFrame:
    pq = per_question(df, metrics)
    rows = []
    for cond, g in pq.groupby(CONDITION, dropna=False):
        row = dict(zip(CONDITION, cond))
        row["n_questions"] = len(g)
        for m in metrics:
            vals = g[m].to_numpy()
            ci = mean_ci(vals, binary=bool(np.isin(vals, (0.0, 1.0)).all()))
            row[m] = ci["mean"]
            row[f"{m}_lo"] = ci["ci_low"]
            row[f"{m}_hi"] = ci["ci_high"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values(CONDITION).reset_index(drop=True)


def compare(df: pd.DataFrame, baseline: str, metric: str, where: dict) -> pd.DataFrame:
    """Paired permutation tests of every retriever against `baseline` on one condition (Holm-corrected)."""
    sub = df
    for k, v in where.items():
        sub = sub[sub[k] == v]
    pq = per_question(sub, [metric]).pivot_table(index="qid", columns="retriever", values=metric)
    if baseline not in pq.columns:
        raise ValueError(f"baseline {baseline} not in run")
    out = []
    for r in pq.columns:
        if r == baseline:
            continue
        pair = pq[[r, baseline]].dropna()
        test = paired_permutation_test(pair[r].to_numpy(), pair[baseline].to_numpy())
        out.append({"retriever": r, "baseline": baseline, "metric": metric, **where,
                    "mean": pair[r].mean(), "baseline_mean": pair[baseline].mean(), **test})
    res = pd.DataFrame(out)
    if not res.empty:
        res["p_holm"] = holm(res["p_value"].tolist())
    return res


def scaling_figure(summary: pd.DataFrame, metric: str, variant: str, out: Path, title: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tiers = summary[(summary["scope"] == "tier") & (summary["variant"] == variant)]
    strategies = sorted(tiers["strategy"].dropna().unique())
    fig, axes = plt.subplots(1, len(strategies), figsize=(6 * len(strategies), 4.5), sharey=True, squeeze=False)
    for ax, strat in zip(axes[0], strategies):
        for retr, g in tiers[tiers["strategy"] == strat].groupby("retriever"):
            g = g.sort_values("n_manuals")
            ax.plot(g["n_manuals"], g[metric], marker="o", label=retr)
            ax.fill_between(g["n_manuals"], g[f"{metric}_lo"], g[f"{metric}_hi"], alpha=0.15)
        ax.set_xscale("log")
        ax.set_xticks(sorted(tiers["n_manuals"].unique()))
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.set_xlabel("manuals in the searched corpus")
        ax.set_title(f"{strat} distractors")
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel(metric)
    axes[0][-1].legend(fontsize=7, loc="lower left")
    fig.suptitle(title or f"{metric} vs corpus size ({variant})")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def write_summary(name: str) -> pd.DataFrame:
    df = load_run(name)
    summary = summarize(df)
    out_dir = paths.RESULTS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "summary.csv", index=False)
    (out_dir / "summary_meta.json").write_text(json.dumps({
        "n_metric_rows": len(df), "retrievers": sorted(df["retriever"].unique()),
        "variants": sorted(df["variant"].unique()), "questions": int(df["qid"].nunique()),
    }, indent=2))
    return summary
