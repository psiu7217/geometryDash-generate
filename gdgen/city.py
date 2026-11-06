"""Low-risk cyberpunk scenery and BPM accents.

Uses documented decorative objects, not gameplay blocks: colored gradient
slab #1904 and small glow orb #1887 (Geometry Dash 2.2).
"""

from __future__ import annotations

import random

from .level import Level
from .objects import GDObject

CITY_PANEL = 1904  # decorative colored gradient slab middle
CITY_GLOW = 1887   # decorative small glow orb
CITY_IDS = frozenset((CITY_PANEL, CITY_GLOW))


def _panel(level: Level, x: float, y: float, width: float, height: float,
           channel: int, *, order: int = -3) -> None:
    level.objects.append(GDObject(CITY_PANEL, round(x, 2), round(y, 2), {
        21: channel, 128: round(width / 30, 3), 129: round(height / 30, 3),
        20: 3, 25: order,
    }))


def _glow(level: Level, x: float, y: float, channel: int, scale: float = 1) -> None:
    props = {21: channel, 20: 3, 25: -2}
    if scale != 1:
        props[32] = scale
    level.objects.append(GDObject(CITY_GLOW, round(x, 2), round(y, 2), props))


def add_cyber_city(level: Level, sections: list, rng: random.Random,
                   *, decor: int = 3, bpm: int = 120) -> None:
    """Build deterministic decorative skyline and approximate beat accents.

    This does not change level geometry or synchronize to an unknown audio
    track. Section objects need start/end/speed attributes.
    """
    if decor < 2:
        return
    spacing = 240.0 if decor == 2 else 180.0
    for section in sections:
        x = section.start + 150
        while x < section.end - 100:
            width = rng.choice((90, 120, 150))
            height = rng.choice((150, 180, 210, 240))
            base = 195.0
            roof = base + height
            accent = rng.choice((1, 2, 3, 4))
            _panel(level, x, base + height / 2, width, height, 5)
            _panel(level, x, roof + 6, width + 12, 8, accent, order=-2)
            if decor >= 3:
                for dx in (-width / 4, width / 4):
                    for y in range(int(base + 45), int(roof - 25), 57):
                        _glow(level, x + dx, y, accent, 0.6)
                _panel(level, x, roof + 28, 4, 40, accent, order=-2)
                _glow(level, x, roof + 50, 6, 0.7)
            x += spacing

    if bpm <= 0:
        return
    from .generator import BASE_SPEED, SPEED_FACTOR
    beat_distance_base = BASE_SPEED * (60.0 / bpm)
    for section in sections:
        distance = beat_distance_base * SPEED_FACTOR[section.speed]
        x = section.start + distance
        while x < section.end - 60:
            _glow(level, x, 460, 6, 0.45)
            x += distance
