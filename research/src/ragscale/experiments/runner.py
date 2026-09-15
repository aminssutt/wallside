"""Run retrieval conditions over the gold set and store per-query metrics + rankings.

Output (one directory per experiment under data/runs/<experiment>/):
  metrics__<retriever>__<variant>.parquet   one row per (question, scope) with every metric
  rankings__<retriever>__<variant>.parquet  top-`store_top` rows per (question, scope) for error analysis / E3
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
import yaml

from .. import paths
from ..corpus import Corpus
from ..dataset.generate import read_jsonl
from ..metrics import Gold, query_metrics
from ..retrievers.base import Query
from .registry import Registry
from .scopes import DEFAULT_TIERS, Scope, ScopeBuilder, tier_scopes

log = logging.getLogger(__name__)

def make_query(record: dict, variant: str) -> Query:
    lang = record["manual_lang"]
    kind, form = variant.split("_", 1)
    if kind == "cross":
        lang = "en" if lang == "fr" else "fr"
    return Query(f"{record['qid']}:{variant}", record["queries"][f"{lang}_{form}"], lang)


@dataclass
class ExperimentSpec:
    name: str
    retrievers: list[str]
    variants: list[str]
    scopes: list[str] = field(default_factory=lambda: ["vehicle", "global"])
    tiers: list[int] = field(default_factory=lambda: list(DEFAULT_TIERS))
    strategies: list[str] = field(default_factory=lambda: ["random", "hard"])
    seeds: int = 5
    dataset: str = "questions_v1"
    split: str = "test"
    k: int = 100
    store_top: int = 20
    batch: int = 48
    max_questions: int | None = None

    @classmethod
    def from_yaml(cls, path) -> "ExperimentSpec":
        return cls(**yaml.safe_load(open(path, encoding="utf-8")))

    def scope_list(self) -> list[Scope]:
        out = []
        for s in self.scopes:
            if s == "tiers":
                out.extend(tier_scopes(self.tiers, self.strategies, range(self.seeds)))
            else:
                out.append(Scope(s))
        return out


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


class Runner:
    def __init__(self, spec: ExperimentSpec, corpus: Corpus | None = None, registry: Registry | None = None):
        self.spec = spec
        self.corpus = corpus or Corpus.load()
        self.registry = registry or Registry(self.corpus)
        self.scopes = ScopeBuilder(self.corpus)
        records = read_jsonl(paths.DATASETS_DIR / f"{spec.dataset}.jsonl")
        records = [r for r in records if spec.split in ("all", r["split"])]
        if spec.max_questions:
            records = records[: spec.max_questions]
        self.records = records
        self.out_dir = paths.RUNS_DIR / spec.name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        ch = self.corpus.chunks
        self._page_start = ch["page_start"].fillna(-1).to_numpy(np.int64)
        self._page_end = ch["page_end"].fillna(-1).to_numpy(np.int64)
        self._manual_vehicle = [self.corpus.manual_meta[m]["vehicle"] for m in self.corpus.manual_ids]
        self._manual_brand = [self.corpus.manual_meta[m]["brand_key"] for m in self.corpus.manual_ids]

    def gold(self, r: dict) -> Gold:
        mi = self.corpus.manual_index
        pages = self.corpus.chunks.loc[r["source_row"], ["page_start", "page_end"]]
        return Gold(
            manual_idx=mi[r["manual"]],
            relevant_rows=frozenset(r["relevant_rows"]),
            equivalent_rows=frozenset(r["equivalent_rows"]),
            equivalent_manual_idx=frozenset(mi[m] for m in r["equivalent_manuals"]),
            page_start=None if pd.isna(pages["page_start"]) else int(pages["page_start"]),
            page_end=None if pd.isna(pages["page_end"]) else int(pages["page_end"]),
            vehicle=r["vehicle"],
            brand_key=r["brand_key"],
        )

    def run(self, overwrite: bool = False) -> list[str]:
        (self.out_dir / "spec.json").write_text(json.dumps(asdict(self.spec), indent=2))
        written = []
        scope_list = self.spec.scope_list()
        for retriever_spec in self.spec.retrievers:
            for variant in self.spec.variants:
                stem = f"{_safe(retriever_spec)}__{variant}"
                metrics_path = self.out_dir / f"metrics__{stem}.parquet"
                if metrics_path.exists() and not overwrite:
                    log.info("skip existing %s", metrics_path.name)
                    written.append(str(metrics_path))
                    continue
                t0 = time.time()
                metrics_df, rankings_df = self._run_one(retriever_spec, variant, scope_list)
                metrics_df.to_parquet(metrics_path, index=False)
                rankings_df.to_parquet(self.out_dir / f"rankings__{stem}.parquet", index=False)
                log.info("%s %s: %d rows in %.0fs", retriever_spec, variant, len(metrics_df), time.time() - t0)
                written.append(str(metrics_path))
        return written

    def import_external(self, rankings_path, retriever_name: str) -> pd.DataFrame:
        """Score rankings produced outside the harness (e.g. the production backend) in the vehicle scope."""
        by_qid = {r["qid"]: r for r in self.records}
        row_of = {cid: i for i, cid in enumerate(self.corpus.chunk_ids)}
        rows = []
        for line in open(rankings_path, encoding="utf-8"):
            ext = json.loads(line)
            r = by_qid.get(ext["qid"])
            if r is None:
                continue
            ranked = np.array([row_of[c] for c in ext["chunk_ids"] if c in row_of], dtype=np.int64)
            m = query_metrics(ranked, self.gold(r), self.corpus.row_manual_idx, self._page_start, self._page_end,
                              self._manual_vehicle, self._manual_brand)
            rows.append({"qid": r["qid"], "retriever": retriever_name, "variant": ext["variant"], "query": ext["query"],
                         "scope": "vehicle", "scope_label": "vehicle", "n_manuals": 0, "strategy": "", "seed": -1,
                         "mask_idx": 0, "guide_available": ext["available"], **m})
        df = pd.DataFrame(rows)
        for variant, g in df.groupby("variant"):
            g.to_parquet(self.out_dir / f"metrics__{_safe(retriever_name)}__{variant}.parquet", index=False)
        return df

    def _run_one(self, retriever_spec: str, variant: str, scope_list: list[Scope]):
        from tqdm import tqdm

        retriever = self.registry.get(retriever_spec)
        queries = [make_query(r, variant) for r in self.records]
        self.registry.prepare(retriever_spec, queries)
        metric_rows, ranking_rows = [], []
        row_manual = self.corpus.row_manual_idx
        for start in tqdm(range(0, len(self.records), self.spec.batch), desc=f"{retriever_spec} {variant}"):
            recs = self.records[start : start + self.spec.batch]
            qs = queries[start : start + self.spec.batch]
            batch_masks, batch_maps = [], []
            for r in recs:
                unique: dict[tuple, int] = {}
                masks, mapping = [], []
                for scope in scope_list:
                    manuals = tuple(sorted(self.scopes.manuals_for(scope, r["manual"])))
                    if manuals not in unique:
                        unique[manuals] = len(masks)
                        masks.append(None if len(manuals) == len(self.corpus.manual_ids)
                                     else self.corpus.mask_for_manuals(manuals))
                    mapping.append((scope, unique[manuals], len(manuals)))
                batch_masks.append(masks)
                batch_maps.append(mapping)
            results = retriever.search(qs, batch_masks, self.spec.k)
            for r, q, mapping, per_mask in zip(recs, qs, batch_maps, results):
                gold = self.gold(r)
                computed: dict[int, dict] = {}
                for scope, mask_idx, n_manuals in mapping:
                    if mask_idx not in computed:
                        rows = per_mask[mask_idx].rows
                        computed[mask_idx] = query_metrics(rows, gold, row_manual, self._page_start, self._page_end,
                                                           self._manual_vehicle, self._manual_brand)
                        ranking_rows.append({"qid": r["qid"], "mask_idx": mask_idx, "n_manuals": n_manuals,
                                             "rows": rows[: self.spec.store_top].tolist(),
                                             "scores": per_mask[mask_idx].scores[: self.spec.store_top].tolist()})
                    metric_rows.append({
                        "qid": r["qid"], "retriever": retriever_spec, "variant": variant, "query": q.text,
                        "scope": scope.kind, "scope_label": scope.label, "n_manuals": n_manuals,
                        "strategy": scope.strategy, "seed": scope.seed, "mask_idx": mask_idx,
                        **computed[mask_idx],
                    })
        return pd.DataFrame(metric_rows), pd.DataFrame(ranking_rows)
