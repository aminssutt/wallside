"""Shared matplotlib style for report figures.

Categorical hues come from the validated reference palette in fixed slot order (never cycled; checked with
the dataviz palette validator: adjacent CVD dE >= 9.1, normal-vision dE >= 19.6 on the light surface).
Three slots sit below 3:1 contrast on the surface, so every figure is paired with a CSV table in results/.
Color follows the entity: a retriever keeps its slot across every figure via `color_for`.
"""
from __future__ import annotations

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
MAX_SERIES = len(SERIES)

_assigned: dict[str, str] = {}


def color_for(entity: str) -> str:
    """Stable slot per entity across all figures of a session; a 9th entity is a programming error."""
    if entity not in _assigned:
        if len(_assigned) >= MAX_SERIES:
            raise ValueError(f"more than {MAX_SERIES} series: fold into 'Other' or facet ({entity})")
        _assigned[entity] = SERIES[len(_assigned)]
    return _assigned[entity]


def apply(ax) -> None:
    fig = ax.figure
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelcolor=INK_SECONDARY, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)


LINE = dict(linewidth=2, markersize=8, markeredgewidth=2, markeredgecolor=SURFACE)
