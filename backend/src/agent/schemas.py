"""Function-calling schemas exposed to the Gemini planner.

Each tool the agent can invoke is declared here as a ``FunctionDeclaration``
with a JSON-Schema-like ``parameters`` object. Gemini reads these to decide
which tool(s) to call and with what arguments.

Keep the descriptions action-oriented and unambiguous: the planner picks a
tool mainly from its description, so small phrasing tweaks change behaviour.
"""
from __future__ import annotations

from typing import List

from google.genai import types as genai_types


# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

_SEARCH_MANUAL = genai_types.FunctionDeclaration(
    name="search_manual",
    description=(
        "Search the owner's manual of the current vehicle for passages "
        "relevant to the user's question. Use this FIRST for any factual "
        "question about the vehicle's procedures, specifications, warning "
        "lights, maintenance, or features. Returns manual chunks with their "
        "source file and page number."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": (
                    "Focused query to search the manual. Reformulate the "
                    "user's question into precise technical keywords "
                    "(e.g. 'tire pressure recommended', 'brake pad "
                    "replacement procedure'). Keep it short (3-8 words)."
                ),
            },
        },
        "required": ["query"],
    },
)


_SEARCH_WEB = genai_types.FunctionDeclaration(
    name="search_web",
    description=(
        "Search the public web for information the manual does not cover "
        "(recalls, real-world fixes, community tips, third-party repair "
        "guides, recent model updates). Prefer search_manual first; only "
        "fall back to the web when the manual is silent or the question is "
        "clearly outside its scope (e.g. known recalls, forum fixes). "
        "The tool automatically issues a parallel site:<manufacturer> "
        "query so official sources are surfaced alongside general results; "
        "you do not need to add site: yourself. You MAY call this function "
        "more than once per question (up to 2x) with different queries when "
        "another angle would clearly widen coverage (e.g. technical + "
        "regulatory, or English + user-language)."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": (
                    "Web search query. Include the vehicle make and model "
                    "to avoid generic results. Keep it under 12 words."
                ),
            },
            "max_results": {
                "type": "INTEGER",
                "description": "Upper bound on results to return (1-8).",
            },
            "language": {
                "type": "STRING",
                "description": (
                    "ISO-639-1 code biasing the search region "
                    "(fr / en / ko / de / es / it). Leave empty for "
                    "worldwide. Use 'fr' for French-specific content "
                    "(regulations, official FR sites), 'ko' for Korean "
                    "sources, 'en' for technical English sources."
                ),
            },
        },
        "required": ["query"],
    },
)


_SEARCH_YOUTUBE = genai_types.FunctionDeclaration(
    name="search_youtube",
    description=(
        "Find a single high-quality YouTube tutorial video for a procedural "
        "question (e.g. how to replace brake pads, change a tire, reset a "
        "service light). Only call this when the user explicitly asks how "
        "to perform a hands-on procedure or when a video would materially "
        "help. Worldwide search by default: the tool probes English, "
        "French and Korean query variants so a good tutorial is found "
        "regardless of the user's own language."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": (
                    "Concise query naming the procedure + vehicle "
                    "(e.g. 'Renault Clio 5 replace brake pads'). "
                    "English wording usually yields the best-produced "
                    "tutorials; the tool expands to other languages on "
                    "its own."
                ),
            },
            "language": {
                "type": "STRING",
                "description": (
                    "Optional ISO-639-1 code (fr / en / ko / de / es / it) "
                    "to bias YouTube results toward that locale. Omit to "
                    "stay worldwide."
                ),
            },
        },
        "required": ["query"],
    },
)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def build_tool_declarations() -> List[genai_types.Tool]:
    """Return the single ``Tool`` wrapping every declared function."""
    return [
        genai_types.Tool(
            function_declarations=[
                _SEARCH_MANUAL,
                _SEARCH_WEB,
                _SEARCH_YOUTUBE,
            ]
        )
    ]


TOOL_NAMES = ("search_manual", "search_web", "search_youtube")
