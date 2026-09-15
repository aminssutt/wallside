"""Build retrievers from compact spec strings, sharing heavy components between them.

Grammar:  spec := name | name "(" item ("," item)* ")"      item := spec | key "=" value
Values with several numbers use "|" (w=0.3|0.7). Examples:
  bm25 | bm25_stem | bm25+ctx | bm25_stem+ctx          lexical (optionally with contextual headers)
  dense:<model>                                         gemini-embedding-001, bge-m3, bge-m3+ctx, ...
  rm3(bm25; fb_docs=10, fb_terms=10, orig_weight=0.5)   pseudo-relevance feedback
  rrf(a, b, ...; k=60, depth=100)                       reciprocal rank fusion
  wsum(a, b; w=0.3|0.7, norm=minmax)                    normalized score fusion (also combmnz(...))
  name_router(a)                                        restrict to manuals named in the query
  doc_router(a; n=3, agg=3)                             two-stage manual -> chunk retrieval
  name_boost(dense:<m>; lam=0.5)                        dense + lam * cos(query, manual name)
  hnsw(dense:<m>; m=32, ef=64)                          filtered approximate search
  rerank(a; depth=30, model=bge-reranker-v2-m3)         cross-encoder reranking
  m3rerank(a; depth=30, w=0.4|0.2|0.4)                  BGE-M3 dense+sparse+multi-vector reranking
"""
from __future__ import annotations

from ..corpus import Corpus
from ..retrievers.base import Retriever


def _split_top(body: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch in ",;" and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def parse(spec: str) -> tuple[str, list[str], dict[str, str]]:
    spec = spec.strip()
    if "(" not in spec:
        return spec, [], {}
    head, body = spec.split("(", 1)
    if not body.endswith(")"):
        raise ValueError(f"unbalanced spec: {spec}")
    args, params = [], {}
    for item in _split_top(body[:-1]):
        if "=" in item and "(" not in item.split("=", 1)[0]:
            key, value = item.split("=", 1)
            params[key.strip()] = value.strip()
        else:
            args.append(item)
    return head.strip(), args, params


def _floats(value: str) -> list[float]:
    return [float(x) for x in value.split("|")]


class Registry:
    def __init__(self, corpus: Corpus, offline: bool | None = None):
        self.corpus = corpus
        self.offline = offline
        self._cache: dict[str, Retriever] = {}
        self._gemini = None

    @property
    def gemini(self):
        if self._gemini is None:
            from ..llm import Gemini

            self._gemini = Gemini(max_workers=8, offline=self.offline)
        return self._gemini

    def get(self, spec: str) -> Retriever:
        key = spec.replace(" ", "")
        if key not in self._cache:
            self._cache[key] = self._build(key)
        return self._cache[key]

    def _build(self, spec: str) -> Retriever:
        head, args, p = parse(spec)
        c = self.corpus
        if head in ("bm25", "bm25_stem", "bm25+ctx", "bm25_stem+ctx"):
            from ..retrievers.lexical import BM25

            return BM25(c, stem=head.startswith("bm25_stem"), contextual=head.endswith("+ctx"))
        if head.startswith("dense:"):
            from ..retrievers.dense import DenseRetriever

            return DenseRetriever(c, head.split(":", 1)[1], gemini=self.gemini)
        if head == "rm3":
            from ..retrievers.lexical import RM3

            return RM3(c, self.get(args[0]), fb_docs=int(p.get("fb_docs", 10)), fb_terms=int(p.get("fb_terms", 10)),
                       orig_weight=float(p.get("orig_weight", 0.5)))
        if head == "rrf":
            from ..retrievers.composite import RRFFusion

            return RRFFusion(c, [self.get(a) for a in args], k_rrf=int(p.get("k", 60)), depth=int(p.get("depth", 100)),
                             weights=_floats(p["w"]) if "w" in p else None)
        if head in ("wsum", "combmnz"):
            from ..retrievers.composite import ScoreFusion

            return ScoreFusion(c, [self.get(a) for a in args], weights=_floats(p["w"]) if "w" in p else None,
                               norm=p.get("norm", "minmax"), method=head, depth=int(p.get("depth", 100)))
        if head == "name_router":
            from ..retrievers.composite import NameRouter

            return NameRouter(c, self.get(args[0]))
        if head == "doc_router":
            from ..retrievers.composite import DocRouter

            return DocRouter(c, self.get(args[0]), n_docs=int(p.get("n", 3)), agg=int(p.get("agg", 3)))
        if head == "name_boost":
            from ..retrievers.composite import NameBoost

            return NameBoost(c, self.get(args[0]), lam=float(p.get("lam", 0.5)))
        if head == "hnsw":
            from ..retrievers.dense import FilteredANN

            return FilteredANN(c, self.get(args[0]), m=int(p.get("m", 32)), ef_search=int(p.get("ef", 64)))
        if head == "rerank":
            from ..retrievers.rerank import CrossEncoderRerank

            return CrossEncoderRerank(c, self.get(args[0]), model=p.get("model", "bge-reranker-v2-m3"),
                                      depth=int(p.get("depth", 30)))
        if head == "m3rerank":
            from ..retrievers.rerank import M3Rerank

            return M3Rerank(c, self.get(args[0]), depth=int(p.get("depth", 30)),
                            weights=_floats(p["w"]) if "w" in p else None)
        raise ValueError(f"unknown retriever spec: {spec}")

    def prepare(self, spec: str, queries) -> None:
        """Pre-encode queries for every dense component (one parallel API pass)."""
        head, args, _ = parse(spec.replace(" ", ""))
        if head.startswith("dense:"):
            self.get(head).prepare(queries)
        for a in args:
            self.prepare(a, queries)
