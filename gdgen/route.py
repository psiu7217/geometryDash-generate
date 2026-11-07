"""Heuristic player route used by the preview and the sanity checks.

This is NOT a physics simulation and does not prove the level is beatable.
It only estimates where a player would be: jump arcs over spikes in cube mode
and the centre of the free corridor in ship mode.
"""

from __future__ import annotations

import math

from .level import Level
from .objects import HAZARD_IDS, MODE_NAMES, PORTAL_IDS, BLOCK

GROUND_Y = 30.0
JUMP_HEIGHT = 64.0


def _mode_sections(level: Level, max_x: float) -> list[tuple[float, float, str]]:
    """Split the level into (start, end, mode) using mode portals."""
    portals = sorted(
        (o.x, MODE_NAMES[o.id]) for o in level.objects if o.id in PORTAL_IDS
    )
    sections: list[tuple[float, float, str]] = []
    mode = MODE_NAMES.get(level.start_mode, "cube") if level.start_mode in MODE_NAMES else "cube"
    x = 0.0
    for px, new_mode in portals:
        if px > x:
            sections.append((x, px, mode))
        mode = new_mode
        x = px
    sections.append((x, max_x, mode))
    return sections


def _corridor_center(level: Level, x: float) -> float | None:
    """Largest free vertical gap at x, based on scaled blocks."""
    intervals: list[tuple[float, float]] = []
    for obj in level.objects:
        if obj.id != BLOCK:
            continue
        half_w = 15.0 * obj.scale_x
        if abs(obj.x - x) > half_w + 2:
            continue
        top = obj.y + 15.0 * obj.scale_y
        bottom = obj.y - 15.0 * obj.scale_y
        if top < 0 or bottom > 420:
            continue
        intervals.append((max(0.0, bottom), min(420.0, top)))
    if not intervals:
        return None
    intervals.sort()
    merged: list[list[float]] = []
    for bottom, top in intervals:
        if merged and bottom <= merged[-1][1] + 0.5:
            merged[-1][1] = max(merged[-1][1], top)
        else:
            merged.append([bottom, top])
    gaps: list[tuple[float, float, float]] = []
    cursor = 0.0
    for bottom, top in merged:
        if bottom > cursor:
            gaps.append((bottom - cursor, cursor, bottom))
        cursor = max(cursor, top)
    if cursor < 420:
        gaps.append((420 - cursor, cursor, 420))
    if not gaps:
        return None
    _, bottom, top = max(gaps)
    return (bottom + top) / 2


def estimate_route(level: Level, step: float = 15.0) -> list[tuple[float, float]]:
    max_x = max((o.x for o in level.objects), default=0.0) + 100
    sections = _mode_sections(level, max_x)

    hazards = sorted(o.x for o in level.objects if o.id in HAZARD_IDS and o.y < 120)
    points: list[tuple[float, float]] = []

    jump_len = 136.0
    jump_start: float | None = None
    hazard_index = 0

    for start, end, mode in sections:
        x = start
        while x < end:
            if mode == "cube":
                while hazard_index < len(hazards) and hazards[hazard_index] < x - 40:
                    hazard_index += 1
                if jump_start is None:
                    lead = jump_len * 0.44
                    if hazard_index < len(hazards) and x + lead >= hazards[hazard_index] > x + 5:
                        jump_start = x
                    y = GROUND_Y
                else:
                    t = (x - jump_start) / jump_len
                    if t >= 1:
                        jump_start = None
                        y = GROUND_Y
                    else:
                        y = GROUND_Y + JUMP_HEIGHT * math.sin(math.pi * t)
            elif mode in {"ship", "ball", "wave"}:
                # Ship and Wave follow the middle of the free corridor; Ball
                # uses the middle of the lower half of its gravity corridor.
                y = _corridor_center(level, x) or 75.0
            else:
                y = 75.0
            points.append((round(x, 2), round(y, 2)))
            x += step
    return points


def annotate_sections(level: Level) -> None:
    max_x = max((o.x for o in level.objects), default=0.0) + 100
    level.sections = [
        {"start": round(start, 1), "end": round(end, 1), "mode": mode}
        for start, end, mode in _mode_sections(level, max_x)
    ]
