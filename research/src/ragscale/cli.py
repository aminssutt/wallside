"""Command-line entry point: `ragscale <command>`."""
from __future__ import annotations

import argparse
import logging


def _cmd_corpus(args: argparse.Namespace) -> None:
    from .corpus import build_corpus

    manuals, chunks = build_corpus(with_embeddings=not args.no_embeddings)
    dup = chunks[chunks["dup_count"] > 1]
    print(f"manuals={len(manuals)} chunks={len(chunks)} pages={manuals['page_count'].sum()}")
    print(f"langs={manuals['lang'].value_counts().to_dict()} duplicate manuals={manuals['duplicate_of'].notna().sum()}")
    print(f"chunks sharing text with another chunk={len(dup)} (across manuals: {(chunks['dup_manuals'] > 1).sum()})")
    bad = manuals[manuals["garbled_share"] > 0.2].sort_values("garbled_share", ascending=False)
    print(f"garbled chunks={int(chunks['garbled'].sum())}; manuals >20% garbled: "
          + ", ".join(f"{m} ({s:.0%})" for m, s in zip(bad["manual"], bad["garbled_share"])))


def _cmd_embed(args: argparse.Namespace) -> None:
    from .corpus import Corpus
    from .retrievers.dense import build_local_embeddings

    corpus = Corpus.load()
    for name in args.models:
        matrix = build_local_embeddings(corpus, name, limit=args.limit)
        print(f"{name}: {matrix.shape}")


def _cmd_dataset(args: argparse.Namespace) -> None:
    import collections
    import json

    from . import paths
    from .corpus import Corpus
    from .dataset.generate import GenConfig, generate_questions, write_jsonl

    cfg = GenConfig(model=args.model, per_manual=args.per_manual, seed=args.seed)
    kept, rejected, usage = generate_questions(Corpus.load(), cfg, limit_manuals=args.limit_manuals)
    out = paths.DATASETS_DIR / f"{args.name}.jsonl"
    write_jsonl(kept, out)
    write_jsonl(rejected, paths.DATASETS_DIR / f"{args.name}.rejected.jsonl")
    meta = {
        "config": cfg.__dict__,
        "n_questions": len(kept),
        "n_rejected": len(rejected),
        "rejection_reasons": collections.Counter(r["reason"].split(":")[0] for r in rejected),
        "splits": collections.Counter(r["split"] for r in kept),
        "manuals_covered": len({r["manual"] for r in kept}),
        "usage": usage,
    }
    (paths.DATASETS_DIR / f"{args.name}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in meta.items() if k != "usage"}, indent=2, ensure_ascii=False))


def _cmd_run(args: argparse.Namespace) -> None:
    from .experiments.runner import ExperimentSpec, Runner

    spec = ExperimentSpec.from_yaml(args.config)
    if args.max_questions:
        spec.max_questions = args.max_questions
    if args.name:
        spec.name = args.name
    for path in Runner(spec).run(overwrite=args.overwrite):
        print(path)


def _cmd_import_prod(args: argparse.Namespace) -> None:
    from . import paths
    from .experiments.runner import ExperimentSpec, Runner

    spec = ExperimentSpec(name=args.name, retrievers=[], variants=[], split=args.split)
    df = Runner(spec).import_external(paths.RUNS_DIR / args.name / "prod_rankings.jsonl", "production_legacy_hybrid")
    print(df.groupby("variant")[["doc_hit@1", "chunk_hit@1", "chunk_hit@5", "page_hit@5", "n_retrieved"]].mean().round(3))
    print("questions whose manual is not reachable in the app:", int((~df["guide_available"]).sum() / max(1, df["variant"].nunique())))


def _cmd_analyze(args: argparse.Namespace) -> None:
    from .experiments.analysis import write_summary

    summary = write_summary(args.name)
    cols = ["retriever", "variant", "scope", "n_manuals", "strategy", "n_questions", "doc_hit@1", "chunk_hit@5", "ndcg@10"]
    with __import__("pandas").option_context("display.width", 250, "display.max_rows", 500, "display.max_colwidth", 60):
        print(summary[cols].round(3).to_string(index=False))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ragscale")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("corpus", help="Extract chunks + gemini vectors from the production indexes")
    p.add_argument("--no-embeddings", action="store_true")
    p.set_defaults(func=_cmd_corpus)

    p = sub.add_parser("embed", help="Encode the corpus with local embedding models (MPS/CUDA/CPU)")
    p.add_argument("models", nargs="+")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=_cmd_embed)

    p = sub.add_parser("dataset", help="Generate the synthetic gold question set with Gemini")
    p.add_argument("--name", default="questions_v1")
    p.add_argument("--model", default="gemini-3.5-flash")
    p.add_argument("--per-manual", type=int, default=6)
    p.add_argument("--seed", type=int, default=20260915)
    p.add_argument("--limit-manuals", type=int, default=None)
    p.set_defaults(func=_cmd_dataset)

    p = sub.add_parser("run", help="Run an experiment config (retrievers x query variants x scopes)")
    p.add_argument("config")
    p.add_argument("--name", default=None)
    p.add_argument("--max-questions", type=int, default=None)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("import-prod", help="Score rankings written by scripts/prod_replica.py")
    p.add_argument("--name", default="e0_production")
    p.add_argument("--split", default="test")
    p.set_defaults(func=_cmd_import_prod)

    p = sub.add_parser("analyze", help="Summarize a run with 95%% confidence intervals")
    p.add_argument("name")
    p.set_defaults(func=_cmd_analyze)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
