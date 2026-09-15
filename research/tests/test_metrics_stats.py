import math

import numpy as np
import pytest

from ragscale.metrics import Gold, query_metrics
from ragscale.stats import holm, mean_ci, paired_permutation_test, wilson

# 3 manuals: 0 = gold (vehicle "v0", brand "b"), 1 = same brand, 2 = other brand; 2 chunks each
ROW_MANUAL = np.array([0, 0, 1, 1, 2, 2])
PAGE_START = np.array([10, 20, 10, 20, 10, 20])
PAGE_END = np.array([11, 21, 11, 21, 11, 21])
VEHICLES = ["v0", "v1", "v2"]
BRANDS = ["b", "b", "c"]
GOLD = Gold(0, frozenset({1}), frozenset({3}), frozenset({1}), 20, 20, "v0", "b")


def metrics(rows):
    return query_metrics(np.array(rows), GOLD, ROW_MANUAL, PAGE_START, PAGE_END, VEHICLES, BRANDS)


def test_perfect_ranking():
    m = metrics([1, 0, 2])
    assert m["doc_hit@1"] == 1 and m["chunk_hit@1"] == 1 and m["chunk_rr@10"] == 1 and m["ndcg@10"] == 1
    assert m["top1_error"] == 0 and m["page_hit@1"] == 1


def test_same_brand_confusion_and_lenient_credit():
    m = metrics([3, 1, 4])
    assert m["doc_hit@1"] == 0 and m["doc_hit@3"] == 1 and m["doc_rr"] == pytest.approx(0.5)
    assert m["confusion_same_brand"] == 1 and m["confusion_other_brand"] == 0
    assert m["doc_hit@1_lenient"] == 1  # manual 1 holds the same evidence text
    assert m["chunk_hit@1"] == 0 and m["chunk_hit@1_lenient"] == 1
    assert m["chunk_rr@10"] == pytest.approx(0.5)
    assert m["ndcg@10"] == pytest.approx(1 / math.log2(3))


def test_page_hit_accepts_neighbouring_chunk_on_gold_page():
    gold = Gold(0, frozenset({1}), frozenset(), frozenset(), 10, 11, "v0", "b")
    m = query_metrics(np.array([0]), gold, ROW_MANUAL, PAGE_START, PAGE_END, VEHICLES, BRANDS)
    assert m["chunk_hit@1"] == 0 and m["page_hit@1"] == 1


def test_empty_ranking_is_an_error_not_a_crash():
    m = metrics([])
    assert m["doc_hit@1"] == 0 and m["top1_error"] == 1 and m["ndcg@10"] == 0


def test_metrics_match_ranx():
    ranx = pytest.importorskip("ranx")
    rng = np.random.default_rng(1)
    qrels, run, ours = {}, {}, []
    for q in range(50):
        rel = set(rng.choice(6, size=rng.integers(1, 3), replace=False).tolist())
        ranking = rng.permutation(6)[:5]
        gold = Gold(0, frozenset(rel), frozenset(), frozenset(), None, None, "v0", "b")
        ours.append(query_metrics(ranking, gold, ROW_MANUAL, PAGE_START, PAGE_END, VEHICLES, BRANDS))
        qrels[f"q{q}"] = {f"d{r}": 1 for r in rel}
        run[f"q{q}"] = {f"d{r}": float(10 - i) for i, r in enumerate(ranking)}
    res = ranx.evaluate(ranx.Qrels(qrels), ranx.Run(run), ["ndcg@10", "mrr@10", "hit_rate@5"])
    assert np.mean([m["ndcg@10"] for m in ours]) == pytest.approx(res["ndcg@10"], abs=1e-9)
    assert np.mean([m["chunk_rr@10"] for m in ours]) == pytest.approx(res["mrr@10"], abs=1e-9)
    assert np.mean([m["chunk_hit@5"] for m in ours]) == pytest.approx(res["hit_rate@5"], abs=1e-9)


def test_wilson_known_value():
    lo, hi = wilson(81, 100)  # textbook example
    assert lo == pytest.approx(0.7222, abs=1e-3) and hi == pytest.approx(0.8749, abs=1e-3)


def test_mean_ci_picks_wilson_for_binary():
    out = mean_ci(np.array([1, 0, 1, 1]))
    assert out["mean"] == 0.75 and (out["ci_low"], out["ci_high"]) == pytest.approx(wilson(3, 4))


def test_permutation_detects_real_difference_and_not_noise():
    rng = np.random.default_rng(0)
    a = rng.random(400)
    assert paired_permutation_test(a + 0.1, a)["p_value"] < 0.001
    assert paired_permutation_test(a, a)["p_value"] == 1.0
    b = a + rng.normal(0, 0.05, 400)
    assert paired_permutation_test(a, b - b.mean() + a.mean())["p_value"] > 0.05


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
