"""Decision layer: answer / clarify / abstain before searching a manual."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.clarify import decide, mentioned_brand, mentions, route  # noqa: E402


def slugs(text):
    return [k["slug"] for k in route(text)]


@pytest.mark.parametrize("text,expected", [
    ("Quelle huile moteur pour ma Peugeot 208 ?", "peugeot-208-2023"),
    ("Comment ouvrir le capot de la Dacia Duster 2024 ?", "dacia-duster-2024"),
    ("Que signifie le voyant ESP sur ma Clio 4 ?", "clio-4"),
    ("Comment recharger ma Tesla Model Y ?", "tesla-model-y"),
    ("Where is the jack stored in my Ford Mustang?", "ford-mustang"),
])
def test_named_vehicle_is_identified(text, expected):
    assert slugs(text) == [expected]


@pytest.mark.parametrize("text", [
    "Comment changer ma batterie ?",
    "Où se trouve la roue de secours ?",
    "Should I wear my seat belt during short trips?",   # "seat" is not SEAT here
    "Où ranger la plage arrière du coffre ?",            # "ranger" is not a Ford Ranger
    "Comment utiliser la smart key ?",
])
def test_questions_without_a_vehicle_route_nowhere(text):
    assert slugs(text) == []


def test_several_versions_of_a_model_ask_for_the_version():
    out = decide("Comment activer le régulateur de vitesse sur ma Honda Civic ?")
    assert out["action"] == "clarify" and out["reason"] == "several_versions"
    assert len(out["options"]) > 1 and all("Civic" in o["name"] for o in out["options"])


def test_brand_only_offers_that_brand():
    out = decide("Quelle pression pour les pneus de ma Peugeot ?")
    assert out["action"] == "clarify" and out["reason"] == "brand_only"
    assert out["brand"] == "Peugeot" and out["options"]
    assert all(o["brand"] == "Peugeot" for o in out["options"])


def test_no_vehicle_asks_without_guessing_options():
    out = decide("Comment changer ma batterie ?")
    assert out["action"] == "clarify" and out["reason"] == "no_vehicle" and out["options"] == []


def test_named_vehicle_answers_directly():
    out = decide("Quelle huile moteur pour ma Peugeot 208 ?")
    assert out["action"] == "answer" and out["vehicle"]["slug"] == "peugeot-208-2023"


@pytest.mark.parametrize("text,brand", [
    ("Comment changer la batterie de ma Porsche 911 ?", "Porsche"),
    ("How do I reset the oil service light on my Lexus RX?", "Lexus"),
])
def test_brands_without_a_manual_abstain(text, brand):
    out = decide(text)
    assert out["action"] == "abstain" and out["brand"] == brand


def test_mentions_requires_capital_for_everyday_words():
    assert mentions("ma Seat Ibiza", "seat") is True
    assert mentions("my seat belt", "seat") is False
    assert mentioned_brand("Quelle pression pour ma Peugeot ?") == "peugeot"


@pytest.fixture
def client(monkeypatch):
    import os

    os.environ.setdefault("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_ENABLED", "0")
    import api

    return api.app.test_client()


def test_decide_endpoint(client):
    r = client.post("/api/ask/decide", json={"message": "Comment changer ma batterie ?"})
    assert r.status_code == 200 and r.json["action"] == "clarify" and r.json["reason"] == "no_vehicle"

    r = client.post("/api/ask/decide", json={"message": "Quelle huile moteur pour ma Peugeot 208 ?"})
    assert r.json["action"] == "answer" and r.json["vehicle"]["slug"] == "peugeot-208-2023"

    r = client.post("/api/ask/decide", json={"message": "batterie de ma Porsche 911"})
    assert r.json["action"] == "abstain" and r.json["brand"] == "Porsche"

    assert client.post("/api/ask/decide", json={"message": "  "}).status_code == 400
