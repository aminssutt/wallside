"""
Automated RAG quality test suite for Car Chat.
Tests retrieval accuracy, hallucination resistance, language handling,
off-topic rejection, and source grounding across multiple guides.
"""
import sys
import os
import io
import time
import json
import re
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).parent
load_dotenv(BACKEND_DIR / ".env")

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

from src.guide_chatbot import get_guide_chatbot, clear_guide_chatbot_cache
from src.guide_manager import guide_manager

# ============================================================
# TEST CASES
# ============================================================

TEST_CASES = [
    # ---- RETRIEVAL ACCURACY (should find answer in manual) ----
    {
        "slug": "peugeot-208-2023",
        "question": "Quelle est la capacite du reservoir de carburant ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["litre", "reservoir"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "peugeot-308-2022",
        "question": "Comment activer le regulateur de vitesse ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["regulateur", "vitesse"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "dacia-duster-2024",
        "question": "Ou se trouve la roue de secours ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["roue"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "citroen-c3-2024",
        "question": "Comment changer les essuie-glaces ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["essuie", "glace"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "honda-civic-11",
        "question": "What is the recommended tire pressure?",
        "lang": "en",
        "category": "retrieval",
        "expect_keywords": ["tire", "pressure", "psi", "kpa"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "volkswagen-golf-8-2020",
        "question": "Comment fonctionne le systeme Start/Stop ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["start", "stop", "moteur"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "bmw-3-series-2024",
        "question": "How to pair a phone via Bluetooth?",
        "lang": "en",
        "category": "retrieval",
        "expect_keywords": ["bluetooth", "phone", "pair"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "hyundai-tucson-2024",
        "question": "Comment ouvrir le capot ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["capot", "levier", "ouvr"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "mercedes-c-class-2022",
        "question": "What engine oil is recommended?",
        "lang": "en",
        "category": "retrieval",
        "expect_keywords": ["oil"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
    {
        "slug": "renault-captur-2024",
        "question": "Quelle est la procedure de vidange ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["vidange", "huile"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },

    # ---- HALLUCINATION RESISTANCE (question where manual likely has no answer) ----
    {
        "slug": "peugeot-208-2023",
        "question": "Quel est le couple de serrage exact des boulons de culasse ?",
        "lang": "fr",
        "category": "hallucination",
        "expect_keywords": [],
        "expect_sources": True,
        "expect_no_hallucination": True,
        "expect_admission": True,  # Should say "not in the manual" or similar
    },
    {
        "slug": "dacia-sandero-2023",
        "question": "Quelle est la puissance exacte en chevaux du moteur 1.0 TCe 90 a 3500 tours ?",
        "lang": "fr",
        "category": "hallucination",
        "expect_keywords": [],
        "expect_sources": True,
        "expect_no_hallucination": True,
        "expect_admission": True,
    },

    # ---- OFF-TOPIC REJECTION ----
    {
        "slug": "peugeot-308-2022",
        "question": "Donne moi une recette de gateau au chocolat",
        "lang": "fr",
        "category": "off_topic",
        "expect_keywords": ["hors sujet", "specialise"],
        "expect_sources": False,
        "expect_no_hallucination": True,
    },
    {
        "slug": "honda-civic-11",
        "question": "Who won the football world cup in 2022?",
        "lang": "en",
        "category": "off_topic",
        "expect_keywords": ["off-topic", "specialized", "Off-topic"],
        "expect_sources": False,
        "expect_no_hallucination": True,
    },

    # ---- LANGUAGE HANDLING ----
    {
        "slug": "hyundai-tucson-2024",
        "question": "\\ube0c\\ub808\\uc774\\ud06c \\uc2dc\\uc2a4\\ud15c\\uc740 \\uc5b4\\ub5bb\\uac8c \\uc791\\ub3d9\\ud558\\ub098\\uc694?",
        "lang": "ko",
        "category": "language",
        "expect_keywords": [],  # Korean response expected
        "expect_sources": True,
        "expect_no_hallucination": True,
        "expect_lang": "ko",
    },
    {
        "slug": "peugeot-208-2023",
        "question": "Can you speak English?",
        "lang": "en",
        "category": "language",
        "expect_keywords": ["English", "French", "Korean"],
        "expect_sources": False,
        "expect_no_hallucination": True,
    },

    # ---- MULTI-TURN COHERENCE ----
    {
        "slug": "volkswagen-golf-8-2020",
        "question": "Quels sont les voyants du tableau de bord ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["voyant", "tableau"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },

    # ---- EDGE CASES ----
    {
        "slug": "alfa-romeo-4c-2013-2020",
        "question": "a",
        "lang": "fr",
        "category": "edge",
        "expect_keywords": [],
        "expect_sources": False,
        "expect_no_hallucination": True,
    },
    {
        "slug": "peugeot-3008-2018",
        "question": "Comment fonctionne la climatisation automatique et comment regler la temperature dans l'habitacle en ete comme en hiver avec les differents modes de ventilation disponibles ?",
        "lang": "fr",
        "category": "retrieval",
        "expect_keywords": ["climatisation", "temperature"],
        "expect_sources": True,
        "expect_no_hallucination": True,
    },
]


# ============================================================
# EVALUATION FUNCTIONS
# ============================================================

HALLUCINATION_PATTERNS = [
    r"(?i)\b\d{2,3}\s*(?:N[Â·.]?m|nm)\b",       # torque values like "42 N.m"
    r"(?i)\b\d+\s*(?:cv|ch|hp|bhp|ps)\b",        # horsepower
    r"(?i)\b\d+(?:\.\d+)?\s*(?:bar|psi)\b",      # pressure
]

ADMISSION_PATTERNS = [
    r"(?i)(?:pas|not)\s+(?:disponible|available|dans|in|trouve|found)",
    r"(?i)(?:information|donnee|valeur).*(?:pas|non|n'est pas).*(?:disponible|presente|mentionn)",
    r"(?i)(?:je ne|i (?:don'?t|cannot|can'?t)).*(?:trouv|find|confirm)",
    r"(?i)cette information n'est pas",
    r"(?i)the manual (?:does not|doesn'?t)",
    r"(?i)not (?:specified|mentioned|available|found) in",
    r"(?i)(?:pas|non) (?:specifie|mentionne|precise) dans",
    r"(?i)aucune information",
]


def check_keywords(response: str, keywords: list) -> bool:
    """Check if at least one keyword is found in the response."""
    if not keywords:
        return True
    text = response.lower()
    return any(kw.lower() in text for kw in keywords)


def check_sources(response: str) -> bool:
    """Check if the response contains a Sources block."""
    return "Sources:" in response or "sources:" in response


def check_no_hallucination(response: str, category: str) -> bool:
    """Check for suspicious fabricated values (only for non-retrieval)."""
    if category == "retrieval":
        return True  # In retrieval, numerical values are expected
    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, response):
            return False
    return True


def check_admission(response: str) -> bool:
    """Check if the response admits lack of information."""
    return any(re.search(p, response) for p in ADMISSION_PATTERNS)


def check_language(response: str, expected_lang: str) -> bool:
    """Basic check that response is in expected language."""
    if expected_lang == "ko":
        korean_chars = len(re.findall(r"[\uac00-\ud7af]", response))
        return korean_chars > 10
    if expected_lang == "en":
        en_words = len(re.findall(r"\b(?:the|is|are|and|for|this|that|with|you|can)\b", response, re.I))
        return en_words >= 3
    return True


def evaluate_test(test: dict, response: str) -> dict:
    """Evaluate a single test case and return detailed results."""
    results = {
        "slug": test["slug"],
        "question": test["question"][:60],
        "category": test["category"],
        "passed": True,
        "checks": {},
        "response_length": len(response),
    }

    # Check 1: Keywords
    if test["expect_keywords"]:
        kw_ok = check_keywords(response, test["expect_keywords"])
        results["checks"]["keywords"] = kw_ok
        if not kw_ok:
            results["passed"] = False

    # Check 2: Sources
    if test["expect_sources"]:
        src_ok = check_sources(response)
        results["checks"]["sources"] = src_ok
        if not src_ok:
            results["passed"] = False

    # Check 3: No hallucination
    if test.get("expect_no_hallucination"):
        hall_ok = check_no_hallucination(response, test["category"])
        results["checks"]["no_hallucination"] = hall_ok
        if not hall_ok:
            results["passed"] = False

    # Check 4: Admission of ignorance
    if test.get("expect_admission"):
        adm_ok = check_admission(response)
        results["checks"]["admits_no_info"] = adm_ok
        if not adm_ok:
            results["passed"] = False

    # Check 5: Language
    if test.get("expect_lang"):
        lang_ok = check_language(response, test["expect_lang"])
        results["checks"]["correct_language"] = lang_ok
        if not lang_ok:
            results["passed"] = False

    # Check 6: Non-empty response
    non_empty = len(response.strip()) > 20
    results["checks"]["non_empty"] = non_empty
    if not non_empty:
        results["passed"] = False

    return results


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("  CAR CHAT - RAG QUALITY TEST SUITE")
    print("=" * 70)

    if not os.getenv("GOOGLE_API_KEY"):
        print("\n  ERROR: GOOGLE_API_KEY not set. Cannot run tests.\n")
        sys.exit(1)

    # Filter tests to only use indexed guides
    indexed_slugs = {g["slug"] for g in guide_manager.list_guides()}
    active_tests = [t for t in TEST_CASES if t["slug"] in indexed_slugs]
    skipped = len(TEST_CASES) - len(active_tests)

    print(f"\n  Guides available: {len(indexed_slugs)}")
    print(f"  Test cases: {len(active_tests)} (skipped {skipped} - guide not indexed)")
    print(f"  Categories: retrieval, hallucination, off_topic, language, edge")
    print("-" * 70)

    all_results = []
    category_stats = {}
    total_time = 0

    for i, test in enumerate(active_tests):
        slug = test["slug"]
        question = test["question"]
        lang = test.get("lang", "fr")
        category = test["category"]

        print(f"\n  [{i+1}/{len(active_tests)}] {category:14} | {slug[:30]:30} | {question[:40]}...")

        try:
            chatbot = get_guide_chatbot(slug)
            start = time.perf_counter()
            response = chatbot.chat(question, lang=lang, session_id=f"test-{i}")
            elapsed = time.perf_counter() - start
            total_time += elapsed

            result = evaluate_test(test, response)
            result["time_s"] = round(elapsed, 2)
            all_results.append(result)

            status = "PASS" if result["passed"] else "FAIL"
            checks_str = " ".join(
                f"{k}={'OK' if v else 'FAIL'}" for k, v in result["checks"].items()
            )
            print(f"         {status} ({elapsed:.1f}s) | {checks_str}")

            if not result["passed"]:
                # Show a snippet of the response for debugging
                snippet = response[:200].replace("\n", " ")
                print(f"         Response: {snippet}...")

            if category not in category_stats:
                category_stats[category] = {"passed": 0, "total": 0}
            category_stats[category]["total"] += 1
            if result["passed"]:
                category_stats[category]["passed"] += 1

        except Exception as exc:
            print(f"         ERROR: {exc}")
            all_results.append({
                "slug": slug,
                "question": question[:60],
                "category": category,
                "passed": False,
                "checks": {"error": str(exc)},
                "time_s": 0,
            })
            if category not in category_stats:
                category_stats[category] = {"passed": 0, "total": 0}
            category_stats[category]["total"] += 1

    # ============================================================
    # RESULTS SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    total_passed = sum(1 for r in all_results if r["passed"])
    total_tests = len(all_results)
    overall_pct = (total_passed / total_tests * 100) if total_tests > 0 else 0

    print(f"\n  Overall: {total_passed}/{total_tests} passed ({overall_pct:.1f}%)")
    print(f"  Total time: {total_time:.1f}s (avg {total_time/max(total_tests,1):.1f}s per query)")

    print(f"\n  {'Category':<20} {'Passed':>8} {'Total':>8} {'Rate':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")
    for cat, stats in sorted(category_stats.items()):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat:<20} {stats['passed']:>8} {stats['total']:>8} {rate:>7.1f}%")

    # Failed tests detail
    failed = [r for r in all_results if not r["passed"]]
    if failed:
        print(f"\n  FAILED TESTS ({len(failed)}):")
        for r in failed:
            failed_checks = [k for k, v in r.get("checks", {}).items() if not v]
            print(f"    - [{r['category']}] {r['slug']}: {r['question']} | Failed: {', '.join(failed_checks)}")

    print("\n" + "=" * 70)
    print(f"  PRECISION SCORE: {overall_pct:.1f}%")
    print("=" * 70)

    # Save results to JSON
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tests": total_tests,
        "passed": total_passed,
        "failed": total_tests - total_passed,
        "precision_pct": round(overall_pct, 1),
        "avg_response_time_s": round(total_time / max(total_tests, 1), 2),
        "category_stats": category_stats,
        "results": all_results,
    }
    results_path = Path(__file__).parent / "test_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {results_path}\n")


if __name__ == "__main__":
    main()

