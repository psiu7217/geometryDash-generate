"""Geometry Dash object model and number formatting.

Only the subset needed by the generator is modelled: an object has an id,
coordinates and arbitrary raw GD properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Common object IDs (verified against GD AI Bridge reference / public parsers).
BLOCK = 1
SPIKE = 8
SMALL_SPIKE = 39
PAD_YELLOW = 35
PAD_PINK = 140
PAD_BLUE = 67
ORB_YELLOW = 36
ORB_PINK = 141
ORB_BLUE = 84
PORTAL_CUBE = 12
PORTAL_SHIP = 13
PORTAL_BALL = 47
PORTAL_UFO = 111
PORTAL_WAVE = 660
PORTAL_ROBOT = 745
PORTAL_SPIDER = 1331
PORTAL_SWING = 1933
GRAVITY_NORMAL = 10
GRAVITY_FLIP = 11
MIRROR_ON = 45
MIRROR_OFF = 46
SIZE_NORMAL = 99
SIZE_MINI = 101
SPEED_SLOW = 200
SPEED_NORMAL = 201
SPEED_FAST = 202
SPEED_FASTER = 203
SPEED_FASTEST = 1334
COLOR_TRIGGER = 899
PULSE_TRIGGER = 1006
MOVE_TRIGGER = 901
START_POS = 31

PORTAL_IDS = {
    PORTAL_CUBE,
    PORTAL_SHIP,
    PORTAL_BALL,
    PORTAL_UFO,
    PORTAL_WAVE,
    PORTAL_ROBOT,
    PORTAL_SPIDER,
    PORTAL_SWING,
}

MODE_NAMES = {
    PORTAL_CUBE: "cube",
    PORTAL_SHIP: "ship",
    PORTAL_BALL: "ball",
    PORTAL_UFO: "ufo",
    PORTAL_WAVE: "wave",
    PORTAL_ROBOT: "robot",
    PORTAL_SPIDER: "spider",
    PORTAL_SWING: "swing",
}

MODE_PORTALS = {name: oid for oid, name in MODE_NAMES.items()}

HAZARD_IDS = {SPIKE, SMALL_SPIKE, 103, 392}


@dataclass(slots=True)
class GDObject:
    id: int
    x: float
    y: float
    props: dict[int, object] = field(default_factory=dict)

    def get(self, prop: int, default: object = None) -> object:
        return self.props.get(prop, default)

    def to_string(self) -> str:
        parts = [f"1,{self.id}", f"2,{fmt_num(self.x)}", f"3,{fmt_num(self.y)}"]
        for key in sorted(self.props):
            value = self.props[key]
            if value is None:
                continue
            parts.append(f"{key},{fmt_value(value)}")
        return ",".join(parts)

    @property
    def color_channel(self) -> int:
        return int(self.get(21, 0) or 0)

    @property
    def scale_x(self) -> float:
        return float(self.get(128, self.get(32, 1)) or 1)

    @property
    def scale_y(self) -> float:
        return float(self.get(129, self.get(32, 1)) or 1)

    @property
    def rotation(self) -> float:
        return float(self.get(6, 0) or 0)


def fmt_num(value: float | int) -> str:
    """Format a number the way GD does: no trailing .0, max 3 decimals."""
    if isinstance(value, bool):
        return "1" if value else "0"
    f = float(value)
    if f.is_integer():
        return str(int(f))
    text = f"{f:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def fmt_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return fmt_num(value)
    return str(value)


def parse_object(segment: str) -> GDObject | None:
    """Parse one `1,id,2,x,...` segment. Returns None for empty/invalid input."""
    fields = [f for f in segment.split(",") if f != ""]
    if len(fields) < 6:
        return None
    pairs: list[tuple[str, str]] = []
    for i in range(0, len(fields) - 1, 2):
        pairs.append((fields[i], fields[i + 1]))
    data = dict(pairs)
    if "1" not in data or "2" not in data or "3" not in data:
        return None
    try:
        obj_id = int(float(data["1"]))
        x = float(data["2"])
        y = float(data["3"])
    except ValueError:
        return None
    props: dict[int, object] = {}
    for key, value in pairs:
        if key in {"1", "2", "3"}:
            continue
        try:
            prop = int(key)
        except ValueError:
            continue
        try:
            props[prop] = int(value) if value.lstrip("-").isdigit() else float(value)
        except ValueError:
            props[prop] = value
    return GDObject(obj_id, x, y, props)


def make_block(x: float, y: float, channel: int = 1, *, sx: float = 1, sy: float = 1,
               detail: int | None = None, rotation: float | None = None,
               layer: int | None = None) -> GDObject:
    props: dict[int, object] = {21: channel}
    if sx != 1:
        props[128] = sx
    if sy != 1:
        props[129] = sy
    if detail is not None:
        props[22] = detail
    if rotation:
        props[6] = rotation
    if layer is not None:
        props[20] = layer
    return GDObject(BLOCK, x, y, props)


def make_spike(x: float, y: float = 15, channel: int = 1, *, rotation: int = 0,
               small: bool = False) -> GDObject:
    props: dict[int, object] = {21: channel}
    if rotation:
        props[6] = rotation
    return GDObject(SMALL_SPIKE if small else SPIKE, x, y, props)


def make_portal(obj_id: int, x: float, y: float) -> GDObject:
    return GDObject(obj_id, x, y, {})


def make_color_trigger(x: float, channel: int, rgb: tuple[int, int, int],
                       duration: float = 0.0, alpha: float = 1.0) -> GDObject:
    r, g, b = rgb
    return GDObject(COLOR_TRIGGER, x, 15, {
        7: r, 8: g, 9: b, 10: round(float(duration), 3), 23: channel, 35: alpha,
    })


def bounds(objects: Iterable[GDObject]) -> tuple[float, float, float, float]:
    xs = [o.x for o in objects]
    ys = [o.y for o in objects]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), max(xs), min(ys), max(ys))
