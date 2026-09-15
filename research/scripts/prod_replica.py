"""Run the PRODUCTION retrieval code (backend GuideChatbot._hybrid_search) on the gold questions.

Must run with the backend environment, not the research one:
    backend/.venv/bin/python research/scripts/prod_replica.py --variants native_plain native_full

It exercises the exact code path used by the Wallside chat (vehicle-scoped FAISS + BM25, RRF, relevance
threshold, lexical-overlap filter, top-5) and writes the retrieved chunk ids to
research/data/runs/<name>/prod_rankings.jsonl; `ragscale import-prod` turns that into metrics.
Web enrichment is not involved: only the manual retrieval step is called.
"""
from __future__ import annotations

import argparse
import functools
import json
import logging
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from src.guide_chatbot import TOP_K_RESULTS, GuideChatbot  # noqa: E402
from src.guide_manager import guide_manager  # noqa: E402
from src.vector_store import get_embeddings  # noqa: E402

log = logging.getLogger("prod_replica")


def make_query_text(record: dict, variant: str) -> str:
    lang = record["manual_lang"]
    kind, form = variant.split("_", 1)
    if kind == "cross":
        lang = "en" if lang == "fr" else "fr"
    return record["queries"][f"{lang}_{form}"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="questions_v1")
    parser.add_argument("--split", default="test")
    parser.add_argument("--variants", nargs="+", default=["native_plain"])
    parser.add_argument("--name", default="e0_production")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Same model + task type as production (langchain embed_query -> RETRIEVAL_QUERY); memoize repeated texts,
    # because production embeds the question once per FAISS store of the vehicle.
    embeddings = get_embeddings()
    embeddings.embed_query = functools.lru_cache(maxsize=None)(embeddings.embed_query)

    records = [json.loads(l) for l in open(REPO / "research" / "datasets" / f"{args.dataset}.jsonl", encoding="utf-8")]
    records = [r for r in records if args.split in ("all", r["split"])]
    out_dir = REPO / "research" / "data" / "runs" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "prod_rankings.jsonl"

    manual_to_guide = {s: g.slug for g in guide_manager.guides.values() for s in g.source_slugs}
    bots: dict[str, GuideChatbot] = {}
    n_done = 0
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out:
        for r in records:
            guide_slug = manual_to_guide.get(r["manual"])
            for variant in args.variants:
                row = {"qid": r["qid"], "variant": variant, "query": make_query_text(r, variant),
                       "guide": guide_slug, "chunk_ids": [], "available": guide_slug is not None}
                if guide_slug is not None:
                    if guide_slug not in bots:
                        bots[guide_slug] = GuideChatbot(guide_manager.get_guide(guide_slug))
                    bot = bots[guide_slug]
                    lookup = {}
                    for source_slug, (_, chunks) in zip(bot.guide.source_slugs, bot.bm25_indices):
                        for i, doc in enumerate(chunks):
                            lookup.setdefault(doc.page_content, f"{source_slug}::{i:05d}")
                    docs, stats = bot._hybrid_search(row["query"], k=TOP_K_RESULTS)
                    row["chunk_ids"] = [lookup.get(d.page_content) for d in docs]
                    row["quality_stats"] = stats
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_done += 1
                if n_done % 100 == 0:
                    log.info("%d queries in %.0fs", n_done, time.time() - t0)
    log.info("wrote %s (%d queries)", out_path, n_done)


if __name__ == "__main__":
    main()
