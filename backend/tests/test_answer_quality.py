import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

os.environ.setdefault("GOOGLE_API_KEY", "test-key")

from src.guide_chatbot import _has_repetition_loop, _is_thin_or_incomplete_answer  # noqa: E402


def test_thin_answer_detects_short_single_sentence():
    text = "Le regulateur maintient la vitesse sans action continue sur la pedale."
    assert _is_thin_or_incomplete_answer(text)


def test_thin_answer_detects_abrupt_tail():
    text = (
        "Le regulateur de vitesse maintient une allure stable sur autoroute, "
        "ce qui ameliore le confort de conduite sans avoir"
    )
    assert _is_thin_or_incomplete_answer(text)


def test_thin_answer_detects_repetition_loop():
    text = (
        "Pour utiliser le regulateur de vitesse, les etapes precises d'activation "
        "et de configuration ne sont pas. Pour utiliser le regulateur de vitesse, "
        "les etapes precises d'activation et de configuration ne sont pas."
    )
    assert _has_repetition_loop(text)


def test_thin_answer_accepts_structured_complete_response():
    text = (
        "1. Activez le regulateur sur route degagee.\n"
        "2. Appuyez sur SET pour memoriser la vitesse.\n"
        "3. Ajustez avec les commandes + et -.\n"
        "4. Utilisez RES pour reprendre la derniere consigne.\n"
        "5. Desactivez avec frein, OFF ou embrayage selon la transmission."
    )
    assert not _is_thin_or_incomplete_answer(text)
