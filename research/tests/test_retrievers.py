import numpy as np
import pytest

from conftest import FixedScores
from ragscale.dataset.names import fill, name_forms
from ragscale.experiments.registry import parse
from ragscale.experiments.scopes import Scope, ScopeBuilder
from ragscale.retrievers.base import Query, Ranking, topk_in_mask
from ragscale.retrievers.composite import DocRouter, NameRouter, RRFFusion, ScoreFusion
from ragscale.retrievers.lexical import BM25, RM3, contextual_texts
from ragscale.text import content_tokens, fold, normalize_for_match

Q = Query("q1", "capacité du reservoir", "fr")


def test_text_normalization_is_accent_and_stopword_insensitive():
    assert fold("Réservoir Élevé") == "reservoir eleve"
    assert content_tokens("Quelle est la capacité du réservoir ?") == ["capacite", "reservoir"]
    assert normalize_for_match("pro- gressivement, 15 s!") == "pro gressivement 15 s"


def test_topk_respects_mask_and_drops_masked_rows():
    scores = np.array([0.1, 0.9, 0.5, 0.7], dtype=np.float32)
    r = topk_in_mask(scores, np.array([True, False, True, True]), 10)
    assert r.rows.tolist() == [3, 2, 0]


def test_bm25_finds_unaccented_query_in_accented_text(tiny_corpus):
    bm25 = BM25(tiny_corpus)
    [[ranking]] = bm25.search([Q], [[None]], 3)
    assert tiny_corpus.chunks.loc[ranking.rows[0], "manual"] in ("peugeot-208", "peugeot-2008")
    assert set(ranking.rows[:2].tolist()) == {0, 2}  # both fuel-tank chunks


def test_contextual_headers_let_bm25_identify_the_named_vehicle(tiny_corpus):
    assert contextual_texts(tiny_corpus)[0].startswith("Peugeot 208 (2023) | Peugeot | page 10")
    q = Query("q", "capacité du réservoir de la 2008", "fr")
    plain = BM25(tiny_corpus).search([q], [[None]], 1)[0][0]
    ctx = BM25(tiny_corpus, contextual=True).search([q], [[None]], 1)[0][0]
    assert tiny_corpus.chunks.loc[ctx.rows[0], "manual"] == "peugeot-2008"
    assert ctx.rows[0] in (2,) and plain.rows.size == 1


def test_rm3_keeps_original_terms_and_adds_feedback_terms(tiny_corpus):
    rm3 = RM3(tiny_corpus, BM25(tiny_corpus), fb_docs=2, fb_terms=5)
    tokens, weights = rm3.expand(Q)
    assert {"capacite", "reservoir"} <= set(tokens) and len(tokens) > 2
    assert sum(weights) == pytest.approx(1.0)


def test_scopes_are_nested_and_contain_gold(tiny_corpus):
    sb = ScopeBuilder(tiny_corpus)
    sb.__dict__["centroid_similarity"] = np.eye(4)  # avoid loading real embeddings
    assert sb.manuals_for(Scope("vehicle"), "renault-clio") == ["renault-clio", "renault-clio-media"]
    for strat in ("random", "hard"):
        t2 = sb.manuals_for(Scope("tier", 2, strat, 0), "peugeot-208")
        t3 = sb.manuals_for(Scope("tier", 3, strat, 0), "peugeot-208")
        assert t2[0] == "peugeot-208" and t3[:2] == t2
    assert sb.manuals_for(Scope("tier", 2, "hard", 0), "peugeot-208")[1] == "peugeot-2008"  # same brand first
    assert sb.mask(Scope("global"), "peugeot-208") is None


def test_rrf_fusion_order(tiny_corpus):
    a = FixedScores(tiny_corpus, {Q.text: [8, 7, 6, 5, 4, 3, 2, 1]}, "a")
    b = FixedScores(tiny_corpus, {Q.text: [1, 7, 6, 5, 4, 3, 2, 8]}, "b")
    [[r]] = RRFFusion(tiny_corpus, [a, b], k_rrf=60).search([Q], [[None]], 3)
    assert r.rows.tolist()[:2] == [1, 2]  # ranked 2nd and 3rd by both beat 1st-in-one/last-in-other


def test_score_fusion_weights_and_missing_candidates(tiny_corpus):
    f = ScoreFusion(tiny_corpus, [FixedScores(tiny_corpus, {}, "a"), FixedScores(tiny_corpus, {}, "b")], weights=[0.8, 0.2], norm="minmax")
    out = f.fuse([Ranking(np.array([0, 1]), np.array([10.0, 0.0])), Ranking(np.array([1, 2]), np.array([5.0, 1.0]))], 3)
    assert out.rows.tolist() == [0, 1, 2]
    assert out.scores.tolist() == pytest.approx([0.8, 0.2, 0.0])  # a missing chunk gets the component's floor (0)
    mnz = ScoreFusion(tiny_corpus, [FixedScores(tiny_corpus, {}, "a"), FixedScores(tiny_corpus, {}, "b")], weights=[0.5, 0.5], method="combmnz")
    runs = [Ranking(np.array([0, 1, 3]), np.array([10.0, 8.0, 0.0])), Ranking(np.array([1, 2]), np.array([5.0, 1.0]))]
    out = mnz.fuse(runs, 4)
    assert out.rows[0] == 1 and out.scores[0] == pytest.approx(2 * (0.5 * 0.8 + 0.5 * 1.0))


def test_doc_router_keeps_best_manuals_only(tiny_corpus):
    s = FixedScores(tiny_corpus, {Q.text: [0.9, 0.0, 0.8, 0.85, 0.1, 0.1, 0.2, 0.2]})
    [[r]] = DocRouter(tiny_corpus, s, n_docs=1, agg=2).search([Q], [[None]], 8)
    assert set(tiny_corpus.chunks.loc[r.rows, "manual"]) == {"peugeot-2008"}  # mean top-2: 0.825 > 0.45


def test_name_router_restricts_to_named_manual_and_falls_back(tiny_corpus):
    s = FixedScores(tiny_corpus, {"réservoir de ma 2008": [9, 0, 1, 0, 0, 0, 0, 0], "réservoir": [9, 0, 1, 0, 0, 0, 0, 0]})
    router = NameRouter(tiny_corpus, s)
    assert router.route("réservoir de ma 2008") == ["peugeot-2008"]
    assert router.route("réservoir de ma 208") == ["peugeot-208"]
    # "Renault Clio 5 Easy Link Multimedia" reduces to the same model: both manuals of the vehicle are kept
    assert router.route("sur ma Clio 5") == ["renault-clio", "renault-clio-media"]
    [[named]], [[plain]] = (router.search([Query("a", t, "fr")], [[None]], 2) for t in ("réservoir de ma 2008", "réservoir"))
    assert tiny_corpus.chunks.loc[named.rows, "manual"].unique().tolist() == ["peugeot-2008"]
    assert plain.rows[0] == 0


def test_name_forms():
    assert name_forms("Peugeot 2008 (2019)", "Peugeot")["model"] == "2008"
    assert name_forms("Renault 5 (1972-1996)", "Renault")["model"] == "Renault 5"
    assert name_forms("Hyundai Tucson 2024 Infotainment System", "Hyundai")["model"] == "Tucson"
    assert name_forms("Mercedes Classe A (2018)", "Mercedes-Benz")["model"] == "Classe A"
    assert fill("Sur ma {VEHICLE} ?", "208") == "Sur ma 208 ?"


def test_spec_parser():
    assert parse("wsum(bm25,dense:bge-m3;w=0.3|0.7,norm=zscore)") == ("wsum", ["bm25", "dense:bge-m3"], {"w": "0.3|0.7", "norm": "zscore"})
    assert parse("rerank(name_router(rrf(a,b));depth=50)") == ("rerank", ["name_router(rrf(a,b))"], {"depth": "50"})


def _names_corpus(names: list[tuple[str, str, str]]):
    import pandas as pd

    from ragscale.corpus import Corpus

    manuals = pd.DataFrame([{"manual": m, "name": n, "brand": b, "brand_key": b.lower(), "vehicle": m, "lang": "fr",
                             "duplicate_of": None} for m, n, b in names])
    chunks = pd.DataFrame([{"row": i, "chunk_id": f"{m}::00000", "manual": m, "text": "x", "page_label": "1"}
                           for i, (m, _, _) in enumerate(names)])
    return Corpus(chunks, manuals)


@pytest.mark.parametrize("query,expected", [
    ("USB on my Hyundai Palisade 2024 Infotainment System?", ["palisade-info"]),
    ("comment régler le siège de ma Palisade", ["palisade", "palisade-info"]),  # no hint: whole vehicle
    ("sur ma Honda Civic (2022-2025) ?", ["civic-11"]),
    ("ma Honda Civic (1972-2021)", ["civic"]),
    ("ma Renault 5", ["r5"]),
    ("le clignotant clignote 5 fois", []),
    ("réservoir de la Peugeot 2008 (2019)", ["p2008"]),
    ("ma Alfa Romeo", []),
    ("bluetooth Alfa Romeo Infotainment System", ["alfa-info"]),
    ("comment ouvrir le capot", []),
])
def test_name_router_regressions(query, expected):
    corpus = _names_corpus([
        ("palisade", "Hyundai Palisade (2024)", "Hyundai"),
        ("palisade-info", "Hyundai Palisade 2024 Infotainment System", "Hyundai"),
        ("civic", "Honda Civic (1972-2021)", "Honda"),
        ("civic-11", "Honda Civic (2022-2025)", "Honda"),
        ("r5", "Renault 5 (1972-1996)", "Renault"),
        ("p2008", "Peugeot 2008 (2019)", "Peugeot"),
        ("alfa-info", "Alfa Romeo Infotainment System", "Alfa Romeo"),
    ])
    assert NameRouter(corpus, FixedScores(corpus, {})).route(query) == expected


@pytest.mark.parametrize("text,brand,expected", [
    ("Should I wear my seat belt?", "seat", False),
    ("Seat belts must be worn", "seat", False),
    ("Où est la roue de secours de ma Seat Ibiza ?", "seat", True),
    ("comment utiliser la smart key", "smart", False),
    ("ma peugeot 208", "peugeot", True),
    ("ma Alfa Romeo Giulia", "alfa romeo", True),
])
def test_common_word_brands_need_capitalization(text, brand, expected):
    from ragscale.text import mentions_name

    assert mentions_name(text, brand) is expected


@pytest.mark.parametrize("query,expected", [
    ("Où ranger la plage arrière sur ma Formentor ?", ["formentor"]),
    ("Comment régler le siège de mon Ford Ranger ?", ["ranger"]),
    ("Le Ranger a-t-il une prise 12 V ?", ["ranger"]),
])
def test_common_word_models_are_not_routed_from_verbs(query, expected):
    corpus = _names_corpus([("formentor", "Cupra Formentor (2021)", "Cupra"), ("ranger", "Ford Ranger (2023)", "Ford")])
    assert NameRouter(corpus, FixedScores(corpus, {})).route(query) == expected
