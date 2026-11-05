"""Procedural Geometry Dash level generator driven by a LevelSpec."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .level import Color, Level
from .objects import (
    MODE_PORTALS, PORTAL_CUBE, SPEED_FAST, SPEED_NORMAL,
    make_block, make_color_trigger, make_portal, make_spike,
)
from .route import estimate_route
from .spec import LevelSpec, THEMES


BASE_SPEED = 311.58
SPEED_FACTOR = {0: 0.779, 1: 1.0, 2: 1.294, 3: 1.515, 4: 1.853}
JUMP_LENGTH = {0: 106, 1: 136, 2: 176, 3: 206, 4: 252}
SPEED_PORTAL = {0: 200, 1: SPEED_NORMAL, 2: SPEED_FAST, 3: 203, 4: 1334}

SECTION_WEIGHTS = {
    1: [1.0],
    2: [0.45, 0.55],
    3: [0.36, 0.28, 0.36],
    4: [0.26, 0.22, 0.24, 0.28],
}

GAP_BY_DIFFICULTY = {
    "easy": 430.0,
    "normal": 340.0,
    "hard": 275.0,
    "harder": 240.0,
    "insane": 210.0,
}


@dataclass
class Section:
    mode: str
    start: float
    end: float
    speed: int
    index: int


def generate(spec: LevelSpec) -> Level:
    rng = random.Random(spec.seed)
    level = Level(
        name=spec.name,
        description=_description(spec),
        author="AI Generator",
        music_id=spec.music_id,
        colors=_palette(spec),
        start_speed=0,
        start_mode=0,
    )

    modes = [m for m in spec.modes if m] or ["cube"]
    weights = SECTION_WEIGHTS.get(len(modes), [1.0 / len(modes)] * len(modes))
    sections: list[Section] = []
    cursor = 0.0
    for index, (mode, weight) in enumerate(zip(modes, weights)):
        speed = 2 if spec.fast_second_half and index == len(modes) - 1 else 1
        length = spec.duration * weight * BASE_SPEED * SPEED_FACTOR[speed]
        length = max(1200.0, round(length / 30.0) * 30.0)
        sections.append(Section(mode, cursor, cursor + length, speed, index))
        cursor += length

    for section in sections:
        _build_section(level, spec, section, rng)

    _add_decor(level, spec, sections, rng)
    _add_color_shifts(level, spec, sections)

    level.sections = [
        {
            "start": round(s.start, 1),
            "end": round(s.end, 1),
            "mode": s.mode,
            "speed": s.speed,
        }
        for s in sections
    ]
    level.duration_seconds = sum(
        (s.end - s.start) / (BASE_SPEED * SPEED_FACTOR[s.speed]) for s in sections
    )
    level.route = estimate_route(level)
    return level


# --------------------------------------------------------------------- palette
def _palette(spec: LevelSpec) -> dict[int, Color]:
    theme = THEMES[spec.theme]
    palette = theme["palette"]
    colors = {
        1000: Color.from_hex(theme["bg"]),
        1001: Color.from_hex(theme["ground"]),
        1002: Color.from_hex(palette[0]),
        1003: Color.from_hex(palette[1]),
        1004: Color.from_hex(_darken(palette[2])),
        1: Color.from_hex(palette[0], blending=True),
        2: Color.from_hex(palette[1], blending=True),
        3: Color.from_hex(palette[2], blending=True),
        4: Color.from_hex(palette[3], blending=True),
        5: Color.from_hex(_darken(palette[2]), alpha=0.9),
        6: Color.from_hex(palette[0], alpha=0.35, blending=True),
    }
    return colors


def _darken(hex_value: str) -> str:
    value = hex_value.lstrip("#")
    parts = [max(0, int(int(value[i:i + 2], 16) * 0.35)) for i in (0, 2, 4)]
    return "".join(f"{p:02x}" for p in parts)


def _description(spec: LevelSpec) -> str:
    return (
        f"Generated from prompt. Theme: {THEMES[spec.theme]['label']}, "
        f"difficulty: {spec.difficulty}, modes: {' -> '.join(spec.modes)}. "
        f"Made with Geometry Dash AI Level Generator."
    )


# --------------------------------------------------------------------- sections
def _build_section(level: Level, spec: LevelSpec, section: Section, rng: random.Random) -> None:
    mode = section.mode
    start = section.start
    speed_len = JUMP_LENGTH.get(section.speed, 136)

    # Mode portal at every boundary (the first section starts as cube).
    if section.index > 0:
        portal_id = MODE_PORTALS.get(mode, PORTAL_CUBE)
        level.objects.append(make_portal(portal_id, start + 30, 45))
        level.objects.append(make_portal(SPEED_PORTAL[section.speed], start + 90, 45))

    if mode == "cube":
        _cube_section(level, spec, section, rng, speed_len)
    elif mode == "ship":
        _ship_section(level, spec, section)
    elif mode == "wave":
        _wave_section(level, spec, section)
    else:
        _ship_section(level, spec, section, gap=120.0)


def _cube_section(level: Level, spec: LevelSpec, section: Section,
                  rng: random.Random, jump_len: float) -> None:
    start = section.start + (420.0 if section.index == 0 else 300.0)
    end = section.end - 240.0
    gap = GAP_BY_DIFFICULTY.get(spec.difficulty, 340.0) * SPEED_FACTOR[section.speed]
    x = start
    while x < end:
        roll = rng.random()
        if spec.difficulty in {"hard", "harder", "insane"} and roll < 0.18:
            _spike_group(level, x, 3)
            advance = gap + 60
        elif roll < 0.58:
            _spike_group(level, x, 1)
            advance = gap
        elif roll < 0.82:
            _spike_group(level, x, 2)
            advance = gap + 40
        else:
            # Yellow jump pad: auto-jump over a wide, safe stretch.
            level.objects.append(
                _pad(x, channel=1)
            )
            advance = 189.0 * SPEED_FACTOR[section.speed] + 120
        x += advance

    # A couple of floating platforms above the route, safe and decorative.
    if spec.decor >= 1:
        px = section.start + 300
        while px < section.end - 300:
            level.objects.append(make_block(px, 165, channel=2, sx=2.5, sy=0.5, detail=1))
            px += 720


def _spike_group(level: Level, x: float, count: int) -> None:
    for i in range(count):
        level.objects.append(make_spike(x + i * 30, 15, channel=4 if count > 1 else 3))


def _pad(x: float, channel: int = 3):
    from .objects import GDObject, PAD_YELLOW

    return GDObject(PAD_YELLOW, x, 15, {21: channel})


def _ship_section(level: Level, spec: LevelSpec, section: Section, gap: float = 150.0) -> None:
    start = section.start + 90.0
    end = section.end - 150.0
    body_start = start + 210.0
    body_end = end - 240.0
    if body_end <= body_start:
        body_start, body_end = start, end

    # Ramp in: floor 0 -> 90 and ceiling 360 -> floor+gap (smooth transition).
    _build_corridor_strip(
        level, start, body_start, gap, ramp_from_floor=0.0, ramp_to_floor=90.0,
        gap_from=360.0, gap_to=gap,
    )
    x = body_start
    while x < body_end:
        floor = 90.0 + 45.0 * math.sin((x - body_start) / 420.0)
        _wall_column(level, x + 15, floor, gap)
        x += 30.0
    # Ramp out back to the open ground.
    last_floor = 90.0 + 45.0 * math.sin(max(0.0, body_end - body_start) / 420.0)
    _build_corridor_strip(
        level, body_end, end, gap, ramp_from_floor=last_floor, ramp_to_floor=0.0,
        gap_from=gap, gap_to=360.0,
    )


def _build_corridor_strip(level: Level, x0: float, x1: float, gap: float,
                          ramp_from_floor: float, ramp_to_floor: float,
                          gap_from: float, gap_to: float) -> None:
    steps = max(1, int((x1 - x0) / 30))
    for i in range(steps):
        t = i / max(1, steps - 1)
        floor = ramp_from_floor + (ramp_to_floor - ramp_from_floor) * t
        current_gap = gap_from + (gap_to - gap_from) * t
        _wall_column(level, x0 + i * 30 + 15, floor, current_gap)


def _wall_column(level: Level, x: float, floor: float, gap: float) -> None:
    if floor > 0.5:
        height = floor
        level.objects.append(
            make_block(x, height / 2, channel=5, sy=height / 30.0, detail=2)
        )
        level.objects.append(
            make_block(x, floor - 2, channel=1, sy=0.12, sx=1.0)
        )
    ceiling = floor + gap
    if ceiling < 359.5:
        height = 360.0 - ceiling
        level.objects.append(
            make_block(x, ceiling + height / 2, channel=5, sy=height / 30.0, detail=2)
        )
        level.objects.append(
            make_block(x, ceiling + 2, channel=2, sy=0.12, sx=1.0)
        )


def _wave_section(level: Level, spec: LevelSpec, section: Section) -> None:
    # A wider ship-like corridor: wave is harder, keep it forgiving.
    _ship_section(level, spec, section, gap=180.0)


# --------------------------------------------------------------------- decor
def _add_decor(level: Level, spec: LevelSpec, sections: list[Section], rng: random.Random) -> None:
    if spec.decor <= 0:
        return
    palette_channels = [1, 2, 3, 4]
    for section in sections:
        if section.mode != "cube":
            continue
        spacing = {1: 420, 2: 300, 3: 210}[max(1, min(3, spec.decor))]
        x = section.start + 150
        while x < section.end - 150:
            channel = palette_channels[rng.randrange(len(palette_channels))]
            height = rng.choice([3.0, 4.0, 5.0])
            level.objects.append(
                make_block(x, 300 + 15 * height, channel=channel, sx=0.25, sy=height)
            )
            if spec.decor >= 2:
                level.objects.append(
                    make_block(x + 60, 270, channel=6, sx=1.4, sy=0.4)
                )
            if spec.decor >= 3:
                level.objects.append(
                    make_block(x + 120, 360, channel=channel, sx=1.0, sy=0.18)
                )
            x += spacing


def _add_color_shifts(level: Level, spec: LevelSpec, sections: list[Section]) -> None:
    palette = spec.palette_hex()
    for i, section in enumerate(sections[1:], start=1):
        color = Color.from_hex(palette[i % len(palette)])
        level.objects.append(
            make_color_trigger(section.start + 150, 1, (color.r, color.g, color.b), 1.5)
        )


def build_preset(name: str, prompt: str) -> LevelSpec:
    spec = spec_from_preset(name)
    if prompt:
        from .spec import parse_prompt

        spec = parse_prompt(prompt)
    return spec


def spec_from_preset(name: str) -> LevelSpec:
    preset = name.lower()
    if preset == "ai-neon-run":
        return LevelSpec(
            name="AI Neon Run",
            duration=30.0,
            difficulty="normal",
            theme="neon",
            modes=["cube", "ship", "cube"],
            decor=2,
            fast_second_half=True,
            seed=20261105,
        )
    raise ValueError(f"Unknown preset: {name}")
