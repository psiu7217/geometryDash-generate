"""Level string model: colour channels, header and object serialization."""

from __future__ import annotations

from dataclasses import dataclass, field

from .objects import GDObject, fmt_num, parse_object


@dataclass(slots=True)
class Color:
    r: int
    g: int
    b: int
    alpha: float = 1.0
    blending: bool = False

    @classmethod
    def from_hex(cls, value: str, alpha: float = 1.0, blending: bool = False) -> "Color":
        value = value.lstrip("#")
        return cls(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha, blending)

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def scaled(self, factor: float) -> tuple[int, int, int]:
        return (
            max(0, min(255, round(self.r * factor))),
            max(0, min(255, round(self.g * factor))),
            max(0, min(255, round(self.b * factor))),
        )

    def to_channel_string(self, channel: int) -> str:
        parts = [
            "1", str(self.r), "2", str(self.g), "3", str(self.b),
            "4", "-1", "6", str(channel), "7", fmt_num(self.alpha),
        ]
        if self.blending:
            parts += ["5", "1"]
        parts += ["15", "1" if self.blending else "0", "18", "0", "8", "1"]
        return "_".join(parts)


@dataclass
class Level:
    name: str
    objects: list[GDObject] = field(default_factory=list)
    colors: dict[int, Color] = field(default_factory=dict)
    description: str = ""
    author: str = "AI Generator"
    bg_channel: int = 1000
    ground_channel: int = 1001
    start_speed: int = 0
    start_mode: int = 0
    music_id: int = 0
    # Non-serialized metadata used by the preview / validation.
    route: list[tuple[float, float]] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.colors:
            self.colors = default_colors()

    # ------------------------------------------------------------------ header
    def channel_string(self) -> str:
        return "".join(
            color.to_channel_string(channel) + "|"
            for channel, color in sorted(self.colors.items())
        )

    def header(self) -> str:
        pairs = [
            ("kS38", self.channel_string().rstrip(",")),
            ("kA13", "0"),
            ("kA15", "1"),
            ("kA16", "1"),
            ("kA6", str(self.bg_channel)),
            ("kA7", str(self.ground_channel)),
            ("kA17", "0"),
            ("kA18", "0"),
            ("kS39", "0"),
            ("kA2", str(self.start_mode)),
            ("kA3", "0"),
            ("kA8", "0"),
            ("kA4", str(self.start_speed)),
            ("kA9", "0"),
            ("kA10", "0"),
            ("kA11", "0"),
        ]
        return ",".join(f"{key},{value}" for key, value in pairs)

    def to_level_string(self) -> str:
        body = "".join(obj.to_string() + ";" for obj in sorted(self.objects, key=lambda o: (o.x, o.y)))
        return self.header() + ";" + body

    # ------------------------------------------------------------------ stats
    def bounds(self) -> tuple[float, float, float, float]:
        if not self.objects:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [o.x for o in self.objects]
        ys = [o.y for o in self.objects]
        return (min(xs), max(xs), min(ys), max(ys))

    @property
    def length_units(self) -> float:
        return self.bounds()[1]

    def object_count(self) -> int:
        return len(self.objects)

    def stats(self) -> dict:
        from .objects import BLOCK, HAZARD_IDS, PORTAL_IDS

        counts = {"blocks": 0, "hazards": 0, "portals": 0, "other": 0}
        for obj in self.objects:
            if obj.id == BLOCK:
                counts["blocks"] += 1
            elif obj.id in HAZARD_IDS:
                counts["hazards"] += 1
            elif obj.id in PORTAL_IDS:
                counts["portals"] += 1
            else:
                counts["other"] += 1
        min_x, max_x, min_y, max_y = self.bounds()
        return {
            "name": self.name,
            "objects": len(self.objects),
            **counts,
            "min_x": round(min_x, 2),
            "max_x": round(max_x, 2),
            "min_y": round(min_y, 2),
            "max_y": round(max_y, 2),
            "channels": len(self.colors),
        }


def default_colors() -> dict[int, Color]:
    """Neon palette used when no theme is specified."""
    return {
        1000: Color.from_hex("05010f"),          # background
        1001: Color.from_hex("0a0420"),          # ground
        1002: Color.from_hex("00e5ff"),          # line
        1003: Color.from_hex("7a2cff"),          # 3D line
        1004: Color.from_hex("1b2a6b"),          # default object colour
        1: Color.from_hex("00f0ff", blending=True),   # cyan
        2: Color.from_hex("a020f0", blending=True),   # purple
        3: Color.from_hex("2040ff", blending=True),   # blue
        4: Color.from_hex("ff20c0", blending=True),   # accent
        5: Color.from_hex("101044", alpha=0.85),      # panel
        6: Color.from_hex("00f0ff", alpha=0.35, blending=True),  # glow
    }


def parse_level_string(data: str) -> tuple[dict, list[GDObject]]:
    """Parse a level string into (header dict, objects)."""
    if not data:
        return {}, []
    segments = data.split(";")
    header_segment = segments[0]
    header: dict[str, str] = {}
    fields = header_segment.split(",")
    for i in range(0, len(fields) - 1, 2):
        header[fields[i]] = fields[i + 1]
    objects = []
    for segment in segments[1:]:
        if not segment.strip():
            continue
        obj = parse_object(segment)
        if obj is not None:
            objects.append(obj)
    return header, objects


def parse_colors(header: dict[str, str]) -> dict[int, Color]:
    colors: dict[int, Color] = {}
    raw = header.get("kS38", "")
    for channel_str in raw.split("|"):
        if not channel_str.strip():
            continue
        values: dict[int, str] = {}
        pieces = channel_str.split("_")
        for i in range(0, len(pieces) - 1, 2):
            try:
                values[int(pieces[i])] = pieces[i + 1]
            except ValueError:
                continue
        try:
            channel = int(values.get(6, "0"))
            r = int(float(values.get(1, "0")))
            g = int(float(values.get(2, "0")))
            b = int(float(values.get(3, "0")))
            alpha = float(values.get(7, "1"))
            blending = values.get(5, "0") in {"1", "1.0"} or values.get(15, "0") in {"1", "1.0"}
        except (ValueError, TypeError):
            continue
        if channel:
            colors[channel] = Color(r, g, b, alpha, blending)
    return colors
