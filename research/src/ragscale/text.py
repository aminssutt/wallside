"""Text normalization shared by corpus building, lexical retrieval and gold matching."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import lru_cache

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WS_RE = re.compile(r"\s+")

STOPWORDS_FR = frozenset(
    """
    a au aux avec ce ces cet cette dans de des du elle elles en est et etre eux il ils je la le les leur leurs
    lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses si son sont sur ta te tes
    toi ton tu un une vos votre vous y comment quel quelle quels quelles quoi faut peut dois doit
    peux cela ca lorsque quand afin ainsi alors aussi autre avant apres bien car chaque
    deja donc dont encore entre fait faire ici jusqu leur lors moins peu plus sans selon sous tout tous toute toutes tres
    """.split()
)
STOPWORDS_EN = frozenset(
    """
    a about above after again against all am an and any are as at be because been before being below between both but by
    can could did do does doing down during each few for from further had has have having he her here hers herself him
    himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or other
    our ours ourselves out over own same she should so some such than that the their theirs them themselves then there
    these they this those through to too under until up very was we were what when where which while who whom why will
    with you your yours yourself yourselves would may must shall
    """.split()
)
STOPWORDS = STOPWORDS_FR | STOPWORDS_EN


def fold(text: str) -> str:
    """Lowercase and strip diacritics: 'Réservoir' -> 'reservoir'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def normalize_for_match(text: str) -> str:
    """Canonical form for substring/duplicate matching: folded, punctuation-free, single spaces."""
    return " ".join(_TOKEN_RE.findall(fold(text)))


def content_hash(text: str) -> str:
    return hashlib.sha1(normalize_for_match(text).encode("utf-8")).hexdigest()


def raw_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(fold(text))


def content_tokens(text: str) -> list[str]:
    """Folded tokens without stopwords, digits kept, single letters dropped."""
    return [t for t in raw_tokens(text) if len(t) > 1 and t not in STOPWORDS]


def detect_lang(text: str) -> str:
    """Cheap fr/en detector by stopword counts; returns 'fr' or 'en'."""
    toks = raw_tokens(text[:20000])
    fr = sum(1 for t in toks if t in _FR_MARKERS)
    en = sum(1 for t in toks if t in _EN_MARKERS)
    return "fr" if fr >= en else "en"


_FR_MARKERS = frozenset("le la les des du est et pour dans une sur avec par vous votre pas sont".split())
_EN_MARKERS = frozenset("the and is for in with to of your you are be this that on".split())


@lru_cache(maxsize=2)
def _stemmer(lang: str):
    import Stemmer

    return Stemmer.Stemmer("french" if lang == "fr" else "english")


def stem_tokens(tokens: list[str], lang: str) -> list[str]:
    return _stemmer(lang).stemWords(tokens)


def lexical_overlap(query: str, passage: str) -> float:
    """Share of the query's content tokens that literally appear in the passage (0..1)."""
    q = set(content_tokens(query))
    if not q:
        return 0.0
    p = set(content_tokens(passage))
    return len(q & p) / len(q)


def squash_ws(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


# Brand and model names that are also everyday FR/EN words ("seat belt", "smart key", "ranger le coffre",
# "espace de chargement", "focus", "swift"): they only count when capitalized (or with their brand).
COMMON_WORD_BRANDS = frozenset({"seat", "smart", "mini", "ram", "genesis", "alpine", "lotus", "jaguar", "ora", "nio", "rover"})
COMMON_WORD_MODELS = frozenset({"ranger", "espace", "rafale", "focus", "swift", "partner", "spring", "leaf", "avenger",
                                "puma", "panda", "jogger", "uno", "austral", "levante", "fiesta", "scenic", "civic",
                                "colt", "mustang", "kangoo", "zoe", "leon", "ibiza", "tipo", "juke", "outback", "forester"})


def mentions_name(text: str, name_key: str) -> bool:
    """Whether the normalized name (e.g. "alfa romeo", "seat") is mentioned in `text`. Brands that are common
    words only count when written capitalized somewhere other than the first word ("ma Seat Ibiza")."""
    if not name_key:
        return False
    padded = f" {normalize_for_match(text)} "
    if f" {name_key} " not in padded:
        return False
    if name_key not in COMMON_WORD_BRANDS and name_key not in COMMON_WORD_MODELS:
        return True
    words = re.findall(r"[\w-]+", text)
    return any(fold(w) == name_key and w[:1].isupper() for w in words[1:])
