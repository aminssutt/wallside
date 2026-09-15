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
        rule = (test["router_unique"] == 0).astype(int)
        summary = {
            "n_dev": int(len(dev)), "n_test": int(len(test)), "positive_rate_test": float(y_test.mean()),
            "classifier": {"roc_auc": float(roc_auc_score(y_test, p_test)), "avg_precision": float(average_precision_score(y_test, p_test)),
                           "precision@0.5": float(precision_score(y_test, p_test >= 0.5)),
                           "recall@0.5": float(recall_score(y_test, p_test >= 0.5)), "f1@0.5": float(f1_score(y_test, p_test >= 0.5))},
            "name_rule": {"precision": float(precision_score(y_test, rule)), "recall": float(recall_score(y_test, rule)),
                          "f1": float(f1_score(y_test, rule))},
            "coefficients": detector.coefficients(),
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
        (self.out_dir / "spec.json").write_text(json.dumps(asdict(self.spec), indent=2))
        for strategy in self.spec.question_strategies:
            sub = pd.concat([overall[overall["strategy"] == "none"], overall[overall["strategy"] == strategy]])
            pareto_figure(sub, self.out_dir / f"pareto_accuracy_vs_turns_{strategy}.png", title=f"question strategy: {strategy}")
        return {"detection": det_summary, "policies": overall}


def pareto_figure(overall: pd.DataFrame, out, title: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    clf = overall[overall["policy"].str.startswith("classifier")].sort_values("avg_turns")
    ax.plot(clf["avg_turns"], clf["doc_hit@1"], "-o", color="#4C72B0", label="classifier (threshold sweep)")
    for _, r in clf.iterrows():
        ax.annotate(r["policy"].split("@")[1], (r["avg_turns"], r["doc_hit@1"]), textcoords="offset points", xytext=(4, -10), fontsize=7)
    markers = {"never": ("s", "#C44E52"), "always": ("^", "#8172B2"), "name_rule": ("D", "#55A868"), "oracle": ("*", "#222222")}
    for pol, (mk, col) in markers.items():
        r = overall[overall["policy"] == pol]
        if len(r):
            ax.errorbar(r["avg_turns"], r["doc_hit@1"], yerr=[r["doc_hit@1"] - r["doc_hit@1_lo"], r["doc_hit@1_hi"] - r["doc_hit@1"]],
                        fmt=mk, color=col, markersize=9, label=pol, capsize=3)
    ax.set_xlabel("average clarifying questions per query")
    ax.set_ylabel("right manual at rank 1 (doc_hit@1)")
    ax.set_title("Accuracy vs. clarification cost" + (f" ({title})" if title else ""))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
