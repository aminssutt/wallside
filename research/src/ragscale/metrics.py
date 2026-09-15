"""Per-query retrieval metrics at document (manual) level and passage (chunk / page) level."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CHUNK_KS = (1, 3, 5, 10, 20)
DOC_KS = (1, 3, 5)
NDCG_K = 10


@dataclass(frozen=True)
class Gold:
    manual_idx: int
    relevant_rows: frozenset[int]         # chunks of the gold manual containing the evidence
    equivalent_rows: frozenset[int]       # same evidence text in other manuals
    equivalent_manual_idx: frozenset[int]
    page_start: int | None
    page_end: int | None
    vehicle: str
    brand_key: str


def distinct_in_order(values: np.ndarray) -> np.ndarray:
    _, first = np.unique(values, return_index=True)
    return values[np.sort(first)]


def query_metrics(
    rows: np.ndarray,
    gold: Gold,
    row_manual_idx: np.ndarray,
    row_page_start: np.ndarray,
    row_page_end: np.ndarray,
    manual_vehicle: list[str],
    manual_brand: list[str],
) -> dict[str, float]:
    """rows: ranked corpus rows (best first). Returns a flat dict of 0/1 hits, reciprocal ranks and nDCG."""
    m: dict[str, float] = {"n_retrieved": float(len(rows))}
    manuals = row_manual_idx[rows] if len(rows) else np.empty(0, dtype=np.int64)

    # ---- document level: manuals in order of first appearance
    doc_order = distinct_in_order(manuals)
    hit_pos = np.flatnonzero(doc_order == gold.manual_idx)
    doc_rank = int(hit_pos[0]) + 1 if hit_pos.size else 0
    for k in DOC_KS:
        m[f"doc_hit@{k}"] = float(0 < doc_rank <= k)
    m["doc_rr"] = 1.0 / doc_rank if doc_rank else 0.0
    lenient_docs = {gold.manual_idx} | set(gold.equivalent_manual_idx)
    m["doc_hit@1_lenient"] = float(len(doc_order) > 0 and int(doc_order[0]) in lenient_docs)

    # ---- confusion analysis for the top-1 manual
    if len(doc_order) == 0:
        m["top1_error"] = 1.0
        m["confusion_same_vehicle"] = m["confusion_same_brand"] = m["confusion_other_brand"] = 0.0
    else:
        top = int(doc_order[0])
        wrong = top != gold.manual_idx
        same_vehicle = wrong and manual_vehicle[top] == gold.vehicle
        same_brand = wrong and not same_vehicle and manual_brand[top] == gold.brand_key
        m["top1_error"] = float(wrong)
        m["confusion_same_vehicle"] = float(same_vehicle)
        m["confusion_same_brand"] = float(same_brand)
        m["confusion_other_brand"] = float(wrong and not same_vehicle and not same_brand)

    # ---- passage level
    strict = np.fromiter((r in gold.relevant_rows for r in rows), dtype=bool, count=len(rows))
    lenient = strict | np.fromiter((r in gold.equivalent_rows for r in rows), dtype=bool, count=len(rows))
    if gold.page_start is not None and len(rows):
        ps, pe = row_page_start[rows], row_page_end[rows]
        page = (manuals == gold.manual_idx) & (ps <= gold.page_end) & (pe >= gold.page_start)
    else:
        page = strict
    for k in CHUNK_KS:
        m[f"chunk_hit@{k}"] = float(strict[:k].any())
        m[f"chunk_hit@{k}_lenient"] = float(lenient[:k].any())
    for k in (1, 5):
        m[f"page_hit@{k}"] = float(page[:k].any())
    first = np.flatnonzero(strict[:NDCG_K])
    m["chunk_rr@10"] = 1.0 / (first[0] + 1) if first.size else 0.0
    gains = strict[:NDCG_K].astype(float)
    dcg = float((gains / np.log2(np.arange(2, len(gains) + 2))).sum())
    n_ideal = min(len(gold.relevant_rows), NDCG_K)
    idcg = float((1.0 / np.log2(np.arange(2, n_ideal + 2))).sum())
    m["ndcg@10"] = dcg / idcg if idcg else 0.0
    return m
