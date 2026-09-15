import numpy as np
import pytest

from conftest import FixedScores
from ragscale.clarify.labels import VehicleCatalog, label_query
from ragscale.clarify.signals import FEATURES, SignalExtractor
from ragscale.clarify.simulate import ClarificationSimulator, Detector
from ragscale.retrievers.base import Query


def _record(manual, specificity="vehicle_specific"):
    q = "Où est la batterie ?"
    return {"qid": "q", "manual": manual, "specificity": specificity, "manual_lang": "fr", "source_row": 0,
            "queries": {"fr_plain": q, "fr_brand": "Où est la batterie de ma Renault ?",
                        "fr_model": "Où est la batterie de ma Clio 5 ?", "fr_full": "Où est la batterie de ma Renault Clio 5 (2025) ?"}}


def test_labels_follow_information_in_the_query(tiny_corpus):
    cat = VehicleCatalog(tiny_corpus)
    rec = _record("renault-clio")
    plain = label_query(cat, rec, "native_plain")
    assert plain.needs_clarification and plain.ambiguity_type == "vehicle" and len(plain.candidate_vehicles) == 3
    brand = label_query(cat, rec, "native_brand")  # Renault has one vehicle (two manuals) in the tiny corpus
    assert brand.candidate_vehicles == ("renault-clio",) and not brand.needs_clarification
    generic = label_query(cat, _record("renault-clio", "generic"), "native_plain")
    assert generic.ambiguity_type == "vehicle" and not generic.needs_clarification


def test_peugeot_brand_query_is_ambiguous_between_models(tiny_corpus):
    cat = VehicleCatalog(tiny_corpus)
    lab = label_query(cat, _record("peugeot-208"), "native_brand")
    assert lab.ambiguity_type == "model" and set(lab.candidate_vehicles) == {"peugeot-208", "peugeot-2008"}


def _simulator(tiny_corpus, strategy="direct"):
    cat = VehicleCatalog(tiny_corpus)
    vectors = np.eye(len(tiny_corpus), dtype=np.float32)
    table = {t: [1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3] for t in ["Où est la batterie ?"]}
    retr = FixedScores(tiny_corpus, table)
    return ClarificationSimulator(tiny_corpus, cat, retr, SignalExtractor(tiny_corpus, cat, doc_vectors=vectors),
                                  question_strategy=strategy)


def test_signals_on_unnamed_query(tiny_corpus):
    sim = _simulator(tiny_corpus)
    feats, dist, ranking = sim.observe(Query("q", "Où est la batterie ?", "fr"), known="")
    assert set(FEATURES) == set(feats)
    assert feats["router_n_vehicles"] == 0 and feats["n_vehicles_top10"] == 3
    assert pytest.approx(sum(p for _, p in dist)) == 1.0


def test_answer_becomes_a_manual_filter(tiny_corpus):
    sim = _simulator(tiny_corpus)
    _, _, ranking = sim.observe(Query("q", "Où est la batterie ?", "fr"), known="Peugeot 2008 (2019)")
    assert set(tiny_corpus.chunks.loc[ranking.rows, "manual"]) == {"peugeot-2008"}


@pytest.mark.parametrize("strategy,expected_turns", [("direct", 1), ("hierarchical", 2)])
def test_name_rule_dialogue_reaches_the_gold_manual(tiny_corpus, strategy, expected_turns):
    sim = _simulator(tiny_corpus, strategy)
    rec = _record("peugeot-2008")
    rec["relevant_rows"], rec["equivalent_rows"] = [2], []
    from ragscale.metrics import Gold

    gold = Gold(tiny_corpus.manual_index["peugeot-2008"], frozenset({2}), frozenset(), frozenset(), 10, 10, "peugeot-2008", "peugeot")
    d = sim.run(rec, "native_plain", Query("q", "Où est la batterie ?", "fr"), gold, "name_rule")
    assert d.first_turn_asked and len(d.turns) == expected_turns
    assert d.metrics["doc_hit@1"] == 1.0
    never = sim.run(rec, "native_plain", Query("q", "Où est la batterie ?", "fr"), gold, "never")
    assert never.metrics["doc_hit@1"] == 0.0 and not never.turns


def test_detector_learns_router_signal():
    rng = np.random.default_rng(0)
    X = rng.random((200, len(FEATURES)))
    y = (X[:, FEATURES.index("router_unique")] < 0.5).astype(int)
    det = Detector().fit(X, y)
    assert det.coefficients()["router_unique"] < 0
