"""Build retrievers from compact spec strings, sharing heavy components between them.

Grammar:  spec := name | name "(" spec ("," spec)* ")"
  bm25 | bm25_stem | dense:<model>
  rrf(a, b, ...)            reciprocal rank fusion
  name_router(a)            restrict to manuals named in the query
  doc_router(a)             two-stage: top-3 manuals, then chunks (a must be a scoring retriever)
  name_boost(dense:<m>)     dense score + 0.5 * cos(query, manual name)
  rerank(a)                 bge-reranker-v2-m3 over the top-30 of a
"""
from __future__ import annotations

from ..corpus import Corpus
from ..retrievers.base import Retriever


def parse(spec: str) -> tuple[str, list[str]]:
    spec = spec.strip()
    if "(" not in spec:
        return spec, []
    head, body = spec.split("(", 1)
    if not body.endswith(")"):
        raise ValueError(f"unbalanced spec: {spec}")
    body = body[:-1]
    args, depth, cur = [], 0, ""
    for ch in body:
        if ch == "," and depth == 0:
            args.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    if cur.strip():
        args.append(cur)
    return head.strip(), [a.strip() for a in args]


class Registry:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self._cache: dict[str, Retriever] = {}
        self._gemini = None

    @property
    def gemini(self):
        if self._gemini is None:
            from ..llm import Gemini

            self._gemini = Gemini(max_workers=8)
        return self._gemini

    def get(self, spec: str) -> Retriever:
        key = spec.replace(" ", "")
        if key not in self._cache:
            self._cache[key] = self._build(key)
        return self._cache[key]

    def _build(self, spec: str) -> Retriever:
        head, args = parse(spec)
        c = self.corpus
        if head in ("bm25", "bm25_stem"):
            from ..retrievers.lexical import BM25

            return BM25(c, stem=head == "bm25_stem")
        if head.startswith("dense:"):
            from ..retrievers.dense import DenseRetriever

            return DenseRetriever(c, head.split(":", 1)[1], gemini=self.gemini)
        if head == "rrf":
            from ..retrievers.composite import RRFFusion

            return RRFFusion(c, [self.get(a) for a in args])
        if head == "name_router":
            from ..retrievers.composite import NameRouter

            return NameRouter(c, self.get(args[0]))
        if head == "doc_router":
            from ..retrievers.composite import DocRouter

            return DocRouter(c, self.get(args[0]))
        if head == "name_boost":
            from ..retrievers.composite import NameBoost

            return NameBoost(c, self.get(args[0]))
        if head == "rerank":
            from ..retrievers.rerank import CrossEncoderRerank

            return CrossEncoderRerank(c, self.get(args[0]))
        raise ValueError(f"unknown retriever spec: {spec}")

    def prepare(self, spec: str, queries) -> None:
        """Pre-encode queries for every dense component (one parallel API pass)."""
        head, args = parse(spec.replace(" ", ""))
        if head.startswith("dense:"):
            self.get(head).prepare(queries)
        for a in args:
            self.prepare(a, queries)
