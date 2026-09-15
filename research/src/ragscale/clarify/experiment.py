"""E4 driver: signals -> detector (trained on dev) -> detection metrics and policy simulation on test."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
import yaml

from .. import paths
from ..corpus import Corpus
from ..dataset.generate import read_jsonl
from ..experiments.registry import Registry
from ..experiments.runner import ExperimentSpec, Runner, make_query
from ..stats import mean_ci
from .labels import VehicleCatalog, label_query
from .signals import FEATURES, SignalExtractor
from .simulate import ClarificationSimulator, Detector

log = logging.getLogger(__name__)


@dataclass
class ClarifySpec:
    name: str = "e4_clarification"
    dataset: str = "questions_v1"
    retriever: str = "bm25_stem"  # searched with the original question; names/answers become a manual filter
    variants: list[str] = field(default_factory=lambda: ["native_plain", "native_brand", "native_model", "native_full"])
    thresholds: list[float] = field(default_factory=lambda: [0.2, 0.35, 0.5, 0.65, 0.8, 0.9])
    question_strategies: list[str] = field(default_factory=lambda: ["direct", "hierarchical", "max_entropy"])
    max_turns: int = 3
    max_questions: int | None = None

    @classmethod
    def from_yaml(cls, path) -> "ClarifySpec":
        return cls(**yaml.safe_load(open(path, encoding="utf-8")))


class ClarifyExperiment:
    def __init__(self, spec: ClarifySpec):
        self.spec = spec
        self.corpus = Corpus.load()
        self.registry = Registry(self.corpus)
        self.catalog = VehicleCatalog(self.corpus)
        self.signals = SignalExtractor(self.corpus, self.catalog)
        self.sim = ClarificationSimulator(self.corpus, self.catalog, self.registry.get(spec.retriever), self.signals,
                                          max_turns=spec.max_turns)
        records = read_jsonl(paths.DATASETS_DIR / f"{spec.dataset}.jsonl")
        if spec.max_questions:
            records = records[: spec.max_questions]
        self.records = records
        self.gold_runner = Runner(ExperimentSpec(name=f"{spec.name}_gold", retrievers=[], variants=[], dataset=spec.dataset,
                                                 split="all"), corpus=self.corpus, registry=self.registry)
        self.out_dir = paths.RESULTS_DIR / spec.name
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def signal_table(self) -> pd.DataFrame:
        from tqdm import tqdm

        rows = []
        for r in tqdm(self.records, desc="signals"):
            for variant in self.spec.variants:
                q = make_query(r, variant)
                feats, _, _ = self.sim.observe(q, known="")
                lab = label_query(self.catalog, r, variant)
                rows.append({"qid": r["qid"], "split": r["split"], "variant": variant, "query": q.text,
                             "ambiguity_type": lab.ambiguity_type, "n_candidates": len(lab.candidate_vehicles),
                             "answer_depends": lab.answer_depends_on_vehicle,
                             "needs_clarification": lab.needs_clarification, **feats})
        return pd.DataFrame(rows)

    def detection(self, table: pd.DataFrame) -> tuple[Detector, dict, pd.DataFrame]:
        from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score

        dev, test = table[table["split"] == "dev"], table[table["split"] == "test"]
        y_dev, y_test = dev["needs_clarification"].astype(int), test["needs_clarification"].astype(int)
        detector = Detector().fit(dev[FEATURES].to_numpy(), y_dev.to_numpy())
        p_test = detector.model.predict_proba(test[FEATURES].to_numpy())[:, 1]

        per_signal = []
        for f in FEATURES:
            x = test[f].to_numpy()
            auc = roc_auc_score(y_test, x) if y_test.nunique() > 1 else float("nan")
            per_signal.append({"signal": f, "auc": max(auc, 1 - auc), "direction": "+" if auc >= 0.5 else "-",
                               "coef": detector.coefficients()[f]})
        # Sub-task: among queries that ARE ambiguous, can model-free signals tell a generic answer from a
        # vehicle-specific one (i.e. whether asking is worth it)?
        amb_dev, amb_test = dev[dev["n_candidates"] > 1], test[test["n_candidates"] > 1]
        generic_feats = [f for f in FEATURES if f not in ("router_n_vehicles", "router_unique")]
        genericity = {"n_test": int(len(amb_test)), "vehicle_specific_share": float(amb_test["answer_depends"].mean())}
        if amb_test["answer_depends"].nunique() > 1 and amb_dev["answer_depends"].nunique() > 1:
            gdet = Detector()
            gdet.model.fit(amb_dev[generic_feats].to_numpy(), amb_dev["answer_depends"].astype(int).to_numpy())
            gp = gdet.model.predict_proba(amb_test[generic_feats].to_numpy())[:, 1]
            genericity["classifier_auc"] = float(roc_auc_score(amb_test["answer_depends"].astype(int), gp))
            genericity["signal_auc"] = {
                f: float(max(a, 1 - a)) for f in generic_feats if amb_test[f].nunique() > 1
                for a in [roc_auc_score(amb_test["answer_depends"].astype(int), amb_test[f])]
            }
        rule = (test["router_unique"] == 0).astype(int)
        summary = {
            "n_dev": int(len(dev)), "n_test": int(len(test)), "positive_rate_test": float(y_test.mean()),
            "classifier": {"roc_auc": float(roc_auc_score(y_test, p_test)), "avg_precision": float(average_precision_score(y_test, p_test)),
                           "precision@0.5": float(precision_score(y_test, p_test >= 0.5)),
                           "recall@0.5": float(recall_score(y_test, p_test >= 0.5)), "f1@0.5": float(f1_score(y_test, p_test >= 0.5))},
            "name_rule": {"precision": float(precision_score(y_test, rule)), "recall": float(recall_score(y_test, rule)),
                          "f1": float(f1_score(y_test, rule))},
            "coefficients": detector.coefficients(),
            "genericity_among_ambiguous": genericity,
        }
        return detector, summary, pd.DataFrame(per_signal).sort_values("auc", ascending=False)

    def simulate(self, detector: Detector) -> tuple[pd.DataFrame, list[dict]]:
        from tqdm import tqdm

        asking = [("always", None), ("name_rule", None), ("oracle", None)] + [("classifier", t) for t in self.spec.thresholds]
        rows, dialogues = [], []
        test = [r for r in self.records if r["split"] == "test"]
        for r in tqdm(test, desc="dialogues"):
            gold = self.gold_runner.gold(r)
            for variant in self.spec.variants:
                q = make_query(r, variant)
                runs = [("never", None, "none")]
                runs += [(pol, thr, strat) for strat in self.spec.question_strategies for pol, thr in asking]
                for policy, thr, strategy in runs:
                    self.sim.question_strategy = strategy if strategy != "none" else "direct"
                    d = self.sim.run(r, variant, q, gold, policy, detector=detector, threshold=thr or 0.5)
                    rows.append({"qid": r["qid"], "variant": variant, "policy": d.policy, "strategy": strategy,
                                 "turns": len(d.turns), "first_turn_asked": d.first_turn_asked,
                                 "needs": d.gold_needs_clarification, "specificity": r["specificity"], **d.metrics})
                    dialogues.append({**asdict(d), "strategy": strategy})
        return pd.DataFrame(rows), dialogues

    @staticmethod
    def policy_summary(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
        out = []
        for key, g in df.groupby(by):
            key = key if isinstance(key, tuple) else (key,)
            row = dict(zip(by, key))
            row["n"] = len(g)
            for m in ("doc_hit@1", "chunk_hit@5", "answer_found@5"):
                ci = mean_ci(g[m].to_numpy())
                row[m], row[f"{m}_lo"], row[f"{m}_hi"] = ci["mean"], ci["ci_low"], ci["ci_high"]
            row["avg_turns"] = g["turns"].mean()
            asked = g[g["turns"] > 0]
            row["gold_in_options@3"] = float(asked["gold_in_options"].mean()) if "gold_in_options" in g and len(asked) else np.nan
            row["ask_rate"] = g["first_turn_asked"].mean()
            needed, not_needed = g[g["needs"]], g[~g["needs"]]
            row["missed_clarification"] = float((~needed["first_turn_asked"]).mean()) if len(needed) else np.nan
            row["unnecessary_clarification"] = float(not_needed["first_turn_asked"].mean()) if len(not_needed) else np.nan
            out.append(row)
        return pd.DataFrame(out)

    def run(self) -> dict:
        table = self.signal_table()
        table.to_csv(self.out_dir / "signals.csv", index=False)
        detector, det_summary, per_signal = self.detection(table)
        per_signal.to_csv(self.out_dir / "signal_auc.csv", index=False)
        sims, dialogues = self.simulate(detector)
        sims.to_csv(self.out_dir / "dialogue_outcomes.csv", index=False)
        with open(self.out_dir / "dialogues.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in dialogues)
        overall = self.policy_summary(sims, ["strategy", "policy"])
        by_variant = self.policy_summary(sims, ["strategy", "policy", "variant"])
        overall.to_csv(self.out_dir / "policies.csv", index=False)
        by_variant.to_csv(self.out_dir / "policies_by_variant.csv", index=False)
        (self.out_dir / "detection.json").write_text(json.dumps(det_summary, indent=2))
        signal_figure(det_summary, per_signal, self.out_dir / "signal_auc.png")
        (self.out_dir / "spec.json").write_text(json.dumps(asdict(self.spec), indent=2))
        for strategy in self.spec.question_strategies:
            sub = pd.concat([overall[overall["strategy"] == "none"], overall[overall["strategy"] == strategy]])
            pareto_figure(sub, self.out_dir / f"pareto_accuracy_vs_turns_{strategy}.png", title=f"question strategy: {strategy}")
        return {"detection": det_summary, "policies": overall}


def pareto_figure(overall: pd.DataFrame, out, title: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ..experiments import plotstyle as ps

    fig, ax = plt.subplots(figsize=(7, 4.6))
    ps.apply(ax)
    clf = overall[overall["policy"].str.startswith("classifier")].sort_values("avg_turns")
    col = ps.color_for("classifier (threshold sweep)")
    ax.plot(clf["avg_turns"], clf["doc_hit@1"], "-o", color=col, label="classifier (threshold sweep)", **ps.LINE)
    for pol, marker in (("never", "s"), ("always", "^"), ("name_rule", "D"), ("oracle", "*")):
        r = overall[overall["policy"] == pol]
        if not len(r):
            continue
        c = ps.color_for(pol)
        lo, hi = r["doc_hit@1"] - r["doc_hit@1_lo"], r["doc_hit@1_hi"] - r["doc_hit@1"]
        ax.errorbar(r["avg_turns"].to_numpy(), r["doc_hit@1"].to_numpy(), yerr=[lo.to_numpy(), hi.to_numpy()], fmt=marker, color=c, markersize=9,
                    markeredgecolor=ps.SURFACE, capsize=3, label=pol)
        ax.annotate(pol, (float(r["avg_turns"].iloc[0]), float(r["doc_hit@1"].iloc[0])), textcoords="offset points",
                    xytext=(8, 4), fontsize=8, color=ps.INK_SECONDARY)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("clarifying questions per query (average)")
    ax.set_ylabel("right manual at rank 1 (doc_hit@1)")
    ax.set_title("Accuracy vs. clarification cost" + (f" - {title}" if title else ""), fontsize=10)
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=160, facecolor=ps.SURFACE)
    plt.close(fig)


def signal_figure(detection: dict, per_signal: pd.DataFrame, out) -> None:
    """Paired bars: AUC of each signal for detecting ambiguity vs. detecting a vehicle-specific answer."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ..experiments import plotstyle as ps

    gen = detection.get("genericity_among_ambiguous", {}).get("signal_auc", {})
    sig = per_signal.set_index("signal")["auc"]
    names = [s for s in sig.index if s in gen]
    y = range(len(names))
    fig, ax = plt.subplots(figsize=(7, 0.42 * len(names) + 1.4))
    ps.apply(ax)
    h = 0.38
    c1, c2 = ps.color_for("needs clarification (ambiguity)"), ps.color_for("answer is vehicle-specific (among ambiguous)")
    ax.barh([i - h / 2 for i in y], [sig[n] for n in names], height=h - 0.04, color=c1, label="ambiguity detection")
    ax.barh([i + h / 2 for i in y], [gen[n] for n in names], height=h - 0.04, color=c2, label="generic vs vehicle-specific")
    for i, n in enumerate(names):
        ax.text(sig[n] + 0.005, i - h / 2, f"{sig[n]:.2f}", va="center", fontsize=7, color=ps.INK_SECONDARY)
        ax.text(gen[n] + 0.005, i + h / 2, f"{gen[n]:.2f}", va="center", fontsize=7, color=ps.INK_SECONDARY)
    ax.axvline(0.5, color=ps.BASELINE, linewidth=1)
    ax.set_yticks(list(y), names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0.45, 1.0)
    ax.set_xlabel("ROC-AUC on test (0.5 = chance)")
    ax.set_title("Which signals detect what?", fontsize=10)
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=160, facecolor=ps.SURFACE)
    plt.close(fig)


def run_examples(run_name: str, retriever_spec: str, dense_model: str | None = None,
                 examples_file: str = "clarification_examples.jsonl", dataset: str | None = None) -> pd.DataFrame:
    """Evaluate the answer/clarify/abstain agent on handcrafted examples, with the detector trained on the
    dev signals of `run_name` and (optionally) a dense model for off-topic detection calibrated on dev questions."""
    from ..retrievers.base import Query
    from .decide import ClarifyAgent, evaluate_examples

    out_dir = paths.RESULTS_DIR / run_name
    signals_df = pd.read_csv(out_dir / "signals.csv")
    dev = signals_df[signals_df["split"] == "dev"]
    detector = Detector().fit(dev[FEATURES].to_numpy(), dev["needs_clarification"].astype(int).to_numpy())
    corpus = Corpus.load()
    registry = Registry(corpus)
    catalog = VehicleCatalog(corpus)
    dense, ood = None, None
    if dense_model:
        dense = registry.get(f"dense:{dense_model}")
        dev_queries = [Query(f"dev{i}", t, "fr") for i, t in enumerate(dev["query"].unique())]
        ood = ClarifyAgent.calibrate_ood(dense, dev_queries, percentile=1.0)
    agent = ClarifyAgent(corpus, catalog, registry.get(retriever_spec), SignalExtractor(corpus, catalog), detector,
                         dense=dense, ood_similarity=ood)
    examples = read_jsonl(paths.DATASETS_DIR / examples_file)
    table = pd.DataFrame(evaluate_examples(agent, examples))
    table.to_csv(out_dir / "examples.csv", index=False)
    (out_dir / "examples_meta.json").write_text(json.dumps({"retriever": retriever_spec, "dense_ood_model": dense_model,
                                                            "ood_similarity_threshold": ood,
                                                            "action_accuracy": float(table["correct_action"].mean())}, indent=2))
    return table
