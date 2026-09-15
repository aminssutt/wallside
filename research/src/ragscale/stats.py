"""Confidence intervals and significance tests for per-query IR metrics.

- Proportions (hit@k): Wilson score interval.
- Means over questions (MRR, nDCG): percentile bootstrap over questions.
- When a condition has several random seeds, values are first averaged per question, so the question is
  the resampling unit (seeds are not independent observations).
- System comparisons: paired randomization (sign-flip) test on per-question differences
  (Smucker, Allan & Carterette, CIKM 2007), Holm-Bonferroni correction for multiple comparisons.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


def wilson(successes: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z = norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values: np.ndarray, n_resamples: int = 10000, confidence: float = 0.95, seed: int = 0) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(n_resamples, values.size))
    means = values[idx].mean(axis=1)
    alpha = (1 - confidence) / 2
    return (float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha)))


def mean_ci(values: np.ndarray, binary: bool | None = None, seed: int = 0) -> dict[str, float]:
    """Mean with the appropriate 95% CI. Binary metrics on integer counts use Wilson, others bootstrap."""
    values = np.asarray(values, dtype=float)
    n = int(values.size)
    mean = float(values.mean()) if n else float("nan")
    if binary is None:
        binary = bool(n) and bool(np.isin(values, (0.0, 1.0)).all())
    lo, hi = wilson(values.sum(), n) if binary else bootstrap_ci(values, seed=seed)
    return {"mean": mean, "ci_low": lo, "ci_high": hi, "n": n}


def paired_permutation_test(a: np.ndarray, b: np.ndarray, n_resamples: int = 20000, seed: int = 0) -> dict[str, float]:
    """Two-sided sign-flip randomization test for mean(a - b) == 0 on paired per-question scores."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("paired arrays must have the same shape")
    d = a - b
    observed = float(d.mean()) if d.size else 0.0
    if d.size == 0 or not np.any(d):
        return {"diff": observed, "p_value": 1.0, "n": int(d.size)}
    rng = np.random.default_rng(seed)
    signs = rng.choice((-1.0, 1.0), size=(n_resamples, d.size))
    null = (signs * d).mean(axis=1)
    p = (np.sum(np.abs(null) >= abs(observed) - 1e-12) + 1) / (n_resamples + 1)
    lo, hi = bootstrap_ci(d, seed=seed)
    return {"diff": observed, "diff_ci_low": lo, "diff_ci_high": hi, "p_value": float(p), "n": int(d.size)}


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()
