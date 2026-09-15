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
    """Average seeds within each question so the question is the statistical unit.

    Corpus size is a condition only for tier scopes; a vehicle scope has 1-3 manuals depending on the
    question and must be aggregated as one condition."""
    df = df.assign(n_manuals=np.where(df["scope"] == "tier", df["n_manuals"], 0))
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


def scaling_figure(summary: pd.DataFrame, metric: str, variant: str, out: Path, title: str = "",
                   retrievers: list[str] | None = None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from . import plotstyle as ps

    tiers = summary[(summary["scope"] == "tier") & (summary["variant"] == variant)]
    if retrievers:
        tiers = tiers[tiers["retriever"].isin(retrievers)]
    names = sorted(tiers["retriever"].unique())[: ps.MAX_SERIES]
    strategies = sorted(tiers["strategy"].dropna().unique())
    fig, axes = plt.subplots(1, len(strategies), figsize=(6 * len(strategies), 4.6), sharey=True, squeeze=False)
    for ax, strat in zip(axes[0], strategies):
        ps.apply(ax)
        for retr in names:
            g = tiers[(tiers["strategy"] == strat) & (tiers["retriever"] == retr)].sort_values("n_manuals")
            col = ps.color_for(retr)
            ax.fill_between(g["n_manuals"], g[f"{metric}_lo"], g[f"{metric}_hi"], color=col, alpha=0.12, linewidth=0)
            ax.plot(g["n_manuals"], g[metric], "-o", color=col, label=retr, **ps.LINE)
        ax.set_xscale("log")
        ax.set_xticks(sorted(tiers["n_manuals"].unique()))
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("manuals in the searched corpus (log scale)")
        ax.set_title(f"{strat} distractors", fontsize=10)
    axes[0][0].set_ylabel(metric)
    handles, labels = axes[0][-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(4, len(labels)), fontsize=8, frameon=False)
    fig.suptitle(title or f"{metric} vs corpus size - {variant}", color=ps.INK)
    fig.tight_layout(rect=(0, 0.08 + 0.04 * (len(labels) > 4), 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, facecolor=ps.SURFACE)
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
    if (summary["scope"] == "tier").any():
        for variant in summary.loc[summary["scope"] == "tier", "variant"].unique():
            for metric in ("doc_hit@1", "chunk_hit@5"):
                scaling_figure(summary, metric, variant, out_dir / f"scaling_{metric.replace('@', '_at_')}_{variant}.png")
    return summary


def best_retrievers(summary: pd.DataFrame, metric: str, scope: str, variant: str, n_manuals: int = 0,
                    strategy: str = "") -> pd.DataFrame:
    """Rank retrievers on one condition (use on the dev split to pick configurations before testing)."""
    sub = summary[(summary["scope"] == scope) & (summary["variant"] == variant) & (summary["n_manuals"] == n_manuals)]
    if strategy:
        sub = sub[sub["strategy"] == strategy]
    cols = ["retriever", metric, f"{metric}_lo", f"{metric}_hi", "n_questions"]
    return sub.sort_values(metric, ascending=False)[cols].reset_index(drop=True)


def question_features(dataset: str) -> pd.DataFrame:
    """Per-question covariates for stratified analysis."""
    from ..dataset.generate import read_jsonl

    rows = []
    for r in read_jsonl(paths.DATASETS_DIR / f"{dataset}.jsonl"):
        overlap = r["lexical_overlap_plain"]
        rows.append({
            "qid": r["qid"], "manual": r["manual"], "manual_lang": r["manual_lang"],
            "question_type": r["question_type"], "specificity": r["specificity"],
            "overlap_bin": "low (<0.34)" if overlap < 0.34 else ("mid" if overlap < 0.67 else "high (>=0.67)"),
            "has_equivalents": bool(r["equivalent_rows"]),
        })
    return pd.DataFrame(rows)


def breakdown(run: str, by: str, metric: str, where: dict, dataset: str | None = None) -> pd.DataFrame:
    """Metric per retriever x stratum (e.g. by specificity) on one condition, with 95% CIs."""
    df = load_run(run)
    for k, v in where.items():
        df = df[df[k] == v]
    if dataset is None:
        spec = json.loads((paths.RUNS_DIR / run / "spec.json").read_text())
        dataset = spec.get("dataset", "questions_v1")
    pq = per_question(df, [metric]).merge(question_features(dataset), on="qid")
    out = []
    for (retriever, stratum), g in pq.groupby(["retriever", by]):
        ci = mean_ci(g[metric].to_numpy())
        out.append({"retriever": retriever, by: stratum, metric: ci["mean"], "ci_low": ci["ci_low"],
                    "ci_high": ci["ci_high"], "n": ci["n"]})
    return pd.DataFrame(out).sort_values(["retriever", by]).reset_index(drop=True)
