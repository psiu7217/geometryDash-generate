"""Moonlit Cloud Kingdom: gentle four-mode gameplay and native 2.2 scenery.

Reference: dreamy violet moon, clouds, stars, floating arcades. All cosmetic
sprites use native Geometry Dash objects; no image embedding or external assets.
Current output requires a real in-game playtest before beatability claims.
"""

from __future__ import annotations

import math
import random

from .level import Color, Level
from .objects import (
    BLOCK, GDObject, MODE_PORTALS, GRAVITY_NORMAL, ORB_YELLOW, make_block,
    make_color_trigger, make_portal, make_spike,
)

# Native 2.2 sprite IDs, verified against frqubit's GD 2.2 sprite index.
CLOUD_IDS = (48, 49, 129, 130, 131)
MOON_DISC = 3621                    # decorative round sprite
MOON_DETAIL = 3624                  # decorative round variant
GLOW = 1887                         # glowing ornament, already used in city.py
PANEL = 1904                        # decoration panel, already used in city.py
MOONLIT_DECOR_IDS = frozenset((*CLOUD_IDS, MOON_DISC, MOON_DETAIL, GLOW, PANEL))
MOVE_TRIGGER = 901
PULSE_TRIGGER = 1006
ALPHA_TRIGGER = 1007

BASE_SPEED = 311.58
BEATS_PER_MINUTE = 120
SECTION_MODES = ("cube", "ship", "ball", "wave")
# Palette channels intentionally separate decor and traversable surfaces.
PALETTE = {
    1000: "080823", 1001: "1b1038", 1002: "e3baff",
    1003: "7552b5", 1004: "b1a0dc",
    1: "e9d6ff", 2: "f5a0e7", 3: "aa80ff", 4: "8cdafa",
    5: "674b9c", 6: "ffe9b7", 7: "e3d0ff", 8: "60468b",
    9: "bdacf6", 10: "f0ccff", 11: "c993ff", 12: "3a2b73",
}


def _obj(level: Level, obj_id: int, x: float, y: float, *,
         channel: int = 1, sx: float = 1.0, sy: float | None = None,
         z: int = -3, layer: int = 4, group: int | None = None,
         rotation: float = 0) -> GDObject:
    props: dict[int, int | float | str] = {
        21: channel, 20: layer, 25: z, 64: 1, 67: 1,
    }
    if sx != 1:
        props[128] = round(sx, 3)
    if sy is not None and sy != 1:
        props[129] = round(sy, 3)
    if rotation:
        props[6] = round(rotation, 3)
    if group is not None:
        props[57] = str(group)
    result = GDObject(obj_id, round(x, 2), round(y, 2), props)
    level.objects.append(result)
    return result


def _cloud(level: Level, x: float, y: float, size: float,
           color: int, rng: random.Random, *, group: int | None = None,
           z: int = -6) -> None:
    _obj(level, rng.choice(CLOUD_IDS), x, y, channel=color,
         sx=size, sy=size * rng.uniform(0.75, 1.05),
         z=z, group=group)


def _star(level: Level, x: float, y: float, channel: int = 6,
          size: float = 0.7, *, hanging: bool = False) -> None:
    _obj(level, GLOW, x, y, channel=channel, sx=size, sy=size, z=-2)
    if hanging:
        # A barely visible vertical decorative tether (not a solid block).
        _obj(level, PANEL, x, y + 48, channel=8, sx=0.02, sy=3.0, z=-7)


def _moon(level: Level, x: float, y: float, scale: float) -> None:
    _obj(level, GLOW, x, y, channel=11, sx=scale * 1.35, z=-9)
    _obj(level, MOON_DISC, x, y, channel=7, sx=scale, z=-8)
    for dx, dy, r in ((-36, 31, 0.8), (18, -40, 0.58), (44, 44, 0.4)):
        _obj(level, MOON_DETAIL, x + dx * scale / 5, y + dy * scale / 5,
             channel=9, sx=r * scale / 3.5, z=-7)


def _arch(level: Level, x: float, y: float, width: float = 165,
          height: float = 165) -> None:
    """Purely cosmetic stylized arcade; no collision blocks."""
    for dx in (-width / 2, width / 2):
        _obj(level, PANEL, x + dx, y, channel=10, sx=0.24,
             sy=height / 30, z=-4)
        _obj(level, PANEL, x + dx, y - height / 2 + 12, channel=3,
             sx=0.65, sy=0.20, z=-3)
        _star(level, x + dx, y + height / 2 + 15, channel=6, size=0.6)
    _obj(level, PANEL, x, y + height / 2, channel=10,
         sx=(width + 32) / 30, sy=0.26, z=-4)
    for i in range(7):
        a = math.pi * (1.0 - i / 6)
        px = x + (width / 2) * math.cos(a)
        py = y + height / 2 + 38 * math.sin(a)
        _obj(level, GLOW, px, py, channel=11, sx=0.5, z=-3)


def _crystal_cluster(level: Level, x: float, y: float, rng: random.Random,
                     *, width: float = 75, z: int = -3) -> None:
    """A family of harmless glowing facets; never collision blocks."""
    for i in range(3):
        dx = (i - 1) * width * 0.33
        height = rng.choice((30, 45, 60, 75))
        channel = (3, 4, 10)[i]
        _obj(level, PANEL, x + dx, y + height * 0.27, channel=channel,
             sx=0.30, sy=height / 30, rotation=(i - 1) * 15, z=z)
        _star(level, x + dx, y + height * 0.75, channel=7, size=0.25)


def _cloud_palace(level: Level, x: float, y: float,
                  rng: random.Random, *, grand: bool = False) -> None:
    """Layered skyline and bridge/turret motifs far behind the playable lane."""
    size = 1.35 if grand else 1.0
    _cloud(level, x, y - 68 * size, 2.8 * size, 9, rng, z=-6)
    _cloud(level, x - 90 * size, y - 76 * size, 1.65 * size, 2, rng, z=-6)
    _cloud(level, x + 90 * size, y - 74 * size, 1.80 * size, 3, rng, z=-6)
    for dx in (-76 * size, 0, 76 * size):
        tower_height = (125 if dx == 0 else 90) * size
        _obj(level, PANEL, x + dx, y + tower_height * 0.34,
             channel=8, sx=0.53 * size, sy=tower_height / 30, z=-7)
        _obj(level, PANEL, x + dx, y + tower_height * 0.82,
             channel=10, sx=1.05 * size, sy=0.22, z=-5)
        _star(level, x + dx, y + tower_height + 8, channel=6, size=0.55)
    _arch(level, x, y + 73 * size, width=105 * size, height=87 * size)


def _ship_path_decor(level: Level, start: float, end: float,
                     rng: random.Random) -> None:
    """Navigation cues and crystal banks outside the ship's safe lane."""
    for i, x in enumerate(range(int(start + 760), int(end - 550), 220)):
        floor, ceiling, center = ship_corridor_bounds(start, end, x)
        _star(level, x, center, channel=6, size=0.30)
        if floor > 25:
            _obj(level, PANEL, x, floor + 6, channel=4,
                 sx=4.6, sy=0.13, z=-2)
            _cloud(level, x + 34, max(0, floor - 38), 1.7, 3, rng, z=-4)
        if ceiling < 390:
            _obj(level, PANEL, x, ceiling - 6, channel=2,
                 sx=4.6, sy=0.13, z=-2)
            _cloud(level, x - 26, ceiling + 35, 1.6, 9, rng, z=-4)
        if i % 3 == 0:
            _crystal_cluster(level, x, min(398, ceiling + 20), rng,
                             width=52, z=-4)


def _at(level: Level, x: float, y: float, mode: str) -> None:
    level.objects.append(make_portal(MODE_PORTALS[mode], x, y))
    # No extra speed portal: all 4 sections use normal speed.


def _cube(level: Level, start: float, end: float) -> None:
    # Explicitly sparse: previous 'Neon Cyber City' was judged too hard.
    for offset in (1050, 1980, 3060, 3960):
        if start + offset < end - 350:
            level.objects.append(make_spike(start + offset, 15, channel=3))
    # Optional yellow orbs reinforce the reference image but are not required
    # for progression. They are placed away from all compulsory spikes.
    for offset in (1480, 3570):
        level.objects.append(GDObject(ORB_YELLOW, start + offset, 105, {21: 6}))
    # The ordinary Geometry Dash ground at y=0 is traversable.
    # Do NOT build a row of solid blocks on it: that would trap the player.


def _solid_strip(level: Level, x0: float, x1: float, bottom: float,
                 top: float, color: int, *, step: int = 90) -> None:
    if top <= bottom or x1 <= x0:
        return
    x = x0
    while x < x1 - 0.001:
        width = min(step, x1 - x)
        level.objects.append(make_block(
            x + width / 2, (top + bottom) / 2, channel=color,
            sx=width / 30, sy=(top - bottom) / 30,
        ))
        x += width


def ship_corridor_bounds(start: float, end: float,
                         x: float) -> tuple[float, float, float]:
    """Gradual, wide S-curves: (floor top, ceiling bottom, safe center).

    Important: two peaks and troughs must *block* a constant-height flight.
    Entrance and exit open gradually, with no thin surprise pinch points.
    This is conservative geometry, NOT a simulated ship playthrough.
    """
    entry = start + 300.0
    exit_ = end - 300.0
    ease_in = max(0.0, min(1.0, (x - entry) / 550.0))
    ease_out = max(0.0, min(1.0, (exit_ - x) / 550.0))
    strength = min(ease_in, ease_out)
    phase = (x - start - 900.0) * (2.0 * math.pi / 2150.0)
    center = 190.0 + 121.0 * strength * math.sin(phase)
    half_gap = 172.0 - 74.0 * strength  # gap >= 196 units in the active section
    return (max(0.0, center - half_gap),
            min(410.0, center + half_gap), center)


def _ship(level: Level, start: float, end: float) -> None:
    """A readable slalom through tall cloud banks, not an empty flight tunnel.

    The player has time to ascend after the portal before the first bend.
    The central path gradually rises/falls by ~240 units peak-to-trough;
    a constant-Y line hits an upper or lower bank. No moving solids.
    """
    x = start + 300.0
    while x < end - 290:
        width = min(60.0, end - 290.0 - x)
        mid = x + width / 2
        floor, ceiling, _ = ship_corridor_bounds(start, end, mid)
        # Near ground: no solid block when the curve dives below y=0.
        if floor > 2:
            _solid_strip(level, x, x + width, 0, floor, 5, step=60)
        if ceiling < 409:
            _solid_strip(level, x, x + width, ceiling, 410, 5, step=60)
        x += 60.0


def _ball(level: Level, start: float, end: float) -> None:
    # Actual Ball: tap to flip gravity between the ground and overhead ceiling.
    # The top starts after a long safe entry and ends before Wave.
    # Ceiling lower face = 195; enough clearance for switching gravity.
    _solid_strip(level, start + 500, end - 620, 195, 225, 5, step=90)
    # At normal speed there is > 4 seconds before each single spike.
    for offset in (1720, 3450):
        if start + offset < end - 850:
            level.objects.append(make_spike(start + offset, 15, channel=3))
    # Auto-restore normal gravity for balls travelling on the ceiling.
    # Without this, an inverted Ball can drift upward when the ceiling ends.
    level.objects.append(GDObject(GRAVITY_NORMAL, end - 790, 180, {}))
    # The final stretch has no ceiling: users can return to the floor before
    # the Wave portal. A second portal at ceiling height covers missed landings.


def _wave(level: Level, start: float, end: float) -> None:
    # Wide corridor, deliberately designed for ±45 degree Wave input:
    # >= 300 units of usable vertical space, no sharp zigzag slits.
    # The player can follow a gentle diagonal rather than precise taps.
    x = start + 180
    while x < end - 30:
        phase = (x - start) / 1000.0
        floor = 8 + 8 * math.sin(phase)
        ceiling = floor + 325
        width = min(90.0, end - 30 - x)
        _solid_strip(level, x, x + width, 0, floor, 5, step=90)
        _solid_strip(level, x, x + width, ceiling, 410, 5, step=90)
        x += 90


def _scenery(level: Level, sections: list[dict], rng: random.Random,
             bpm: int) -> None:
    max_x = sections[-1]["end"]
    # Deep parallax layers: more clouds and a recognizable world.
    for i, x in enumerate(range(90, int(max_x), 120)):
        offset = rng.uniform(-45, 45)
        _cloud(level, x + offset, rng.uniform(240, 390),
               rng.uniform(2.0, 4.2), 12, rng, group=201, z=-8)
        if i % 3 != 0:
            _cloud(level, x + rng.uniform(-60, 60), rng.uniform(135, 265),
                   rng.uniform(1.05, 2.6), rng.choice((2, 3, 5)),
                   rng, group=202, z=-6)

    # Readable near-surface cloud decoration only: no physical collisions.
    for x in range(270, int(max_x - 150), 260):
        _cloud(level, x, rng.choice((35, 55, 75)),
               rng.uniform(1.3, 2.5), 1, rng, z=-2)

    # Stars and dangling lanterns; keep below conservative world limits.
    for i in range(int(max_x / 75)):
        x = 120 + i * 75 + rng.uniform(-16, 16)
        y = rng.uniform(245, 420)
        _star(level, x, y, channel=rng.choice((6, 7, 11)),
              size=rng.uniform(0.28, 0.7), hanging=i % 9 == 0)

    for section in sections:
        middle = (section["start"] + section["end"]) / 2
        _moon(level, middle + 300, 315, 6.0)
        for x in (section["start"] + 750, section["end"] - 630):
            _arch(level, x, 240, width=140, height=150)

    # More scene variety: cloud bridges, glowing ruins, lanterns, crystals.
    # Only native *decorative* IDs; never create extra solid obstacles here.
    for i, x in enumerate(range(550, int(max_x - 420), 550)):
        base_y = (280, 315, 340, 275)[i % 4]
        _cloud_palace(level, x, base_y, rng, grand=i % 3 == 1)
    for i, x in enumerate(range(340, int(max_x - 150), 310)):
        base_y = (88, 355, 115, 325)[i % 4]
        _crystal_cluster(level, x, base_y, rng, width=58)
        for dx, dy in ((-54, 20), (-23, 34), (16, 25)):
            _star(level, x + dx, base_y + dy, channel=6, size=0.22)

    _ship_path_decor(level, sections[1]["start"], sections[1]["end"], rng)

    # Ending temple: three decorative arcades, no solid walls.
    finish = sections[-1]["end"] - 180
    for offset, scale in ((-200, 1.2), (0, 1.6), (200, 1.2)):
        _arch(level, finish + offset, 225, 110 * scale, 130 * scale)
    for x in range(int(finish - 180), int(finish + 180), 60):
        _star(level, x, rng.uniform(280, 390), size=0.85)

    # Cosmetic triggers: native color, move, pulse and alpha keys.
    # This is conservative raw-object support, NOT a verified animation test.
    level.objects.append(GDObject(MOVE_TRIGGER, 690, 15,
                                  {51: 201, 28: 0, 29: 18, 10: 3.0}))
    level.objects.append(GDObject(MOVE_TRIGGER, 840, 15,
                                  {51: 202, 28: 0, 29: -9, 10: 4.0}))
    level.objects.append(GDObject(ALPHA_TRIGGER, 570, 15,
                                  {51: 202, 35: 0.85, 10: 1.5}))
    level.objects.append(GDObject(ALPHA_TRIGGER, sections[1]["start"] + 450, 15,
                                  {51: 202, 35: 1.0, 10: 2.0}))
    for section in sections:
        x = section["start"] + 360
        level.objects.append(make_color_trigger(x, 11, (190, 140, 255), 2.0))
        level.objects.append(GDObject(PULSE_TRIGGER, x + 210, 15, {
            23: 6, 52: 0, 7: 255, 8: 236, 9: 201,
            45: 0.25, 46: 0.20, 47: 0.9,
        }))
    # BPM accents are passive glow markers, not music-accurate placement.
    beat_step = BASE_SPEED * 60 / max(40, bpm)
    x = beat_step * 2
    while x < max_x - 90:
        _star(level, x, 390, size=0.25)
        x += beat_step * 2


def _route(level: Level, sections: list[dict]) -> list[tuple[float, float]]:
    """Visual guide only; not a physics simulation or beatability proof."""
    spikes = {round(o.x) for o in level.objects if o.id == 8}
    result: list[tuple[float, float]] = []
    for section in sections:
        mode, start, end = section["mode"], section["start"], section["end"]
        x = start
        while x <= end:
            if mode == "cube":
                near = min((abs(x - sx) for sx in spikes if start <= sx < end),
                           default=9999)
                y = 88 if near <= 44 else 30
            elif mode == "ship":
                y = ship_corridor_bounds(start, end, x)[2]
            elif mode == "ball":
                t = (x - start) / max(1, end - start)
                y = 210 if 0.25 <= t <= 0.87 else 30
            else:
                # Gentle illustration of a 45-degree-controlled trajectory,
                # not an input schedule with validated transition timings.
                y = 145 + 53 * math.sin((x - start) / 130)
            result.append((round(x, 2), round(y, 2)))
            x += 15
    return result


def generate_moonlit(spec) -> Level:
    """Build the independent 60-second reference-inspired demo preset."""
    if spec.modes != list(SECTION_MODES):
        raise ValueError("Moonlit preset requires Cube -> Ship -> Ball -> Wave")
    rng = random.Random(spec.seed)
    level = Level(
        name=spec.name, author="AI Generator",
        description=("Moonlit Cloud Kingdom: easy fairy-tale journey among stars, "
                     "floating clouds, moonlit arches and a celestial temple."),
        music_id=spec.music_id,
        colors={index: Color.from_hex(value, blending=(index in (6, 11)))
                for index, value in PALETTE.items()},
    )
    durations = (0.25, 0.25, 0.25, 0.25)
    cursor = 0.0
    sections: list[dict] = []
    for i, (mode, weight) in enumerate(zip(SECTION_MODES, durations)):
        length = round((spec.duration * weight * BASE_SPEED) / 30) * 30
        end = cursor + length
        sections.append({"start": cursor, "end": end, "mode": mode, "speed": 1})
        if i:
            # Ship altitude is player-controlled: cover the broad flight lane
            # with vertically separated mode portals, not only a low one.
            if mode == "ball":
                for portal_y in (45, 145, 245):
                    _at(level, cursor + 30, portal_y, mode)
            elif mode == "wave":
                # Ball can approach from floor or ceiling.
                _at(level, cursor + 30, 45, mode)
                _at(level, cursor + 30, 200, mode)
            else:
                _at(level, cursor + 30, 45, mode)
        if mode == "cube":
            _cube(level, cursor, end)
        elif mode == "ship":
            _ship(level, cursor, end)
        elif mode == "ball":
            _ball(level, cursor, end)
        else:
            _wave(level, cursor, end)
        cursor = end

    _scenery(level, sections, rng, spec.bpm)
    level.sections = sections
    level.duration_seconds = cursor / BASE_SPEED
    level.route = _route(level, sections)
    return level
