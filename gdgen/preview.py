"""Static PNG preview renderer (no third-party dependencies).

The image is built from exactly the same Level object that is serialized into
`.gdlvl`: blocks, spikes, portals, pads/orbs, decorations and the estimated
player route.
"""

from __future__ import annotations

import math
import pathlib
import struct
import zlib

from .level import Color, Level
from .objects import (
    BLOCK, HAZARD_IDS, MODE_NAMES, PORTAL_IDS, SPIKE, SMALL_SPIKE,
    PAD_PINK, PAD_YELLOW, PAD_BLUE, ORB_YELLOW, ORB_PINK, ORB_BLUE,
    GRAVITY_FLIP, GRAVITY_NORMAL, MIRROR_ON, MIRROR_OFF,
)
from .route import estimate_route, _mode_sections


FONT: dict[str, list[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    " ": ["00000"] * 7,
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00110", "00110"],
    ">": ["01000", "00100", "00010", "00001", "00010", "00100", "01000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "#": ["01010", "01010", "11111", "01010", "11111", "01010", "01010"],
}

MODE_COLORS = {
    "cube": (0, 240, 255),
    "ship": (200, 80, 255),
    "wave": (255, 40, 180),
    "ball": (255, 160, 0),
    "ufo": (120, 255, 120),
    "robot": (255, 230, 0),
    "spider": (255, 80, 80),
    "swing": (80, 140, 255),
}


class Canvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int]) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        self.pixels = bytearray(background * (self.width * self.height))

    def set(self, x: int, y: int, color: tuple[int, int, int], alpha: float = 1.0) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        index = (y * self.width + x) * 3
        if alpha >= 0.999:
            self.pixels[index:index + 3] = bytes(color)
        else:
            for i in range(3):
                old = self.pixels[index + i]
                self.pixels[index + i] = int(old * (1 - alpha) + color[i] * alpha)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int],
             alpha: float = 1.0) -> None:
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        for y in range(max(0, y0), min(self.height, y1 + 1)):
            for x in range(max(0, x0), min(self.width, x1 + 1)):
                self.set(x, y, color, alpha)

    def outline(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int],
                alpha: float = 1.0) -> None:
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        for x in range(x0, x1 + 1):
            self.set(x, y0, color, alpha)
            self.set(x, y1, color, alpha)
        for y in range(y0, y1 + 1):
            self.set(x0, y, color, alpha)
            self.set(x1, y, color, alpha)

    def line(self, x0: float, y0: float, x1: float, y1: float,
             color: tuple[int, int, int], alpha: float = 1.0, dashed: bool = False) -> None:
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
        for i in range(steps + 1):
            if dashed and (i // 6) % 2 == 1:
                continue
            t = i / steps
            self.set(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t), color, alpha)

    def triangle(self, points: list[tuple[float, float]], color: tuple[int, int, int],
                 alpha: float = 1.0) -> None:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x0, x1 = int(min(xs)), int(max(xs))
        y0, y1 = int(min(ys)), int(max(ys))
        area = _edge(*points[0], *points[1], *points[2])
        if abs(area) < 1e-6:
            return
        for y in range(max(0, y0), min(self.height - 1, y1) + 1):
            for x in range(max(0, x0), min(self.width - 1, x1) + 1):
                px, py = x + 0.5, y + 0.5
                w0 = _edge(points[1][0], points[1][1], points[2][0], points[2][1], px, py)
                w1 = _edge(points[2][0], points[2][1], points[0][0], points[0][1], px, py)
                w2 = _edge(points[0][0], points[0][1], points[1][0], points[1][1], px, py)
                if (w0 >= 0 and w1 >= 0 and w2 >= 0) or (w0 <= 0 and w1 <= 0 and w2 <= 0):
                    self.set(x, y, color, alpha)

    def circle(self, cx: float, cy: float, radius: float, color: tuple[int, int, int],
               alpha: float = 1.0) -> None:
        r2 = radius * radius
        for y in range(int(cy - radius), int(cy + radius) + 1):
            for x in range(int(cx - radius), int(cx + radius) + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    self.set(x, y, color, alpha)

    def text(self, x: int, y: int, text: str, color: tuple[int, int, int],
             scale: int = 1, alpha: float = 1.0) -> None:
        cursor = x
        for char in text.upper():
            glyph = FONT.get(char, FONT["?"] if "?" in FONT else FONT[" "])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rect(cursor + col * scale, y + row * scale,
                                  cursor + col * scale + scale - 1,
                                  y + row * scale + scale - 1, color, alpha)
            cursor += 6 * scale

    def save_png(self, path: pathlib.Path) -> None:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * stride:(y + 1) * stride])
        compressed = zlib.compress(bytes(raw), 9)
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        data = signature
        for tag, payload in ((b"IHDR", ihdr), (b"IDAT", compressed), (b"IEND", b"")):
            data += struct.pack(">I", len(payload)) + tag + payload
            data += struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _edge(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax)


def render_preview(level: Level, path: str | pathlib.Path,
                   width_per_block: int = 8, height_per_block: int = 12) -> pathlib.Path:
    path = pathlib.Path(path)
    if not level.route:
        level.route = estimate_route(level)
    sections = level.sections or [
        {"start": start, "end": end, "mode": mode}
        for start, end, mode in _mode_sections(level, level.length_units + 100)
    ]

    min_x, max_x, min_y, max_y = level.bounds()
    max_x = max(max_x, 1.0) + 120
    y_max = max(480.0, max_y + 30)
    y_min = min(-30.0, min_y - 30)

    margin = 20
    header = 86
    footer = 58
    scale_x = width_per_block / 30.0
    scale_y = height_per_block / 30.0
    width = int(margin * 2 + max_x * scale_x)
    height = int(header + footer + (y_max - y_min) * scale_y)

    bg = _color(level, level.bg_channel, (5, 1, 15))
    canvas = Canvas(width, height, _darken(bg, 0.75))

    def px(x: float) -> float:
        return margin + x * scale_x

    def py(y: float) -> float:
        return header + (y_max - y) * scale_y

    # Section bands and labels.
    for section in sections:
        start = section["start"]
        end = section["end"]
        mode = section["mode"]
        tint = MODE_COLORS.get(mode, (80, 80, 120))
        canvas.rect(px(start), header, px(end), px(y_min), _mix(_darken(bg, 0.75), tint, 0.08))
        canvas.line(px(start), header, px(start), height - footer, tint, 0.35)
        canvas.text(int((px(start) + px(end)) / 2 - len(mode) * 4),
                    header - 12, mode, tint, 1, 0.9)

    # Grid (10 blocks).
    grid_color = _mix(_darken(bg, 0.75), (120, 120, 255), 0.12)
    x = 0
    while x <= max_x:
        canvas.line(px(x), header, px(x), height - footer, grid_color, 0.5)
        x += 300

    # Ground.
    ground = _color(level, level.ground_channel, (10, 4, 32))
    canvas.rect(px(-100), py(0), px(max_x + 100), py(y_min), ground)
    canvas.line(px(-100), py(0), px(max_x + 100), py(0), _color(level, 1002, (0, 229, 255)), 0.8)

    # Objects: blocks first, hazards/portals above them.
    for obj in sorted(level.objects, key=lambda o: (o.id != BLOCK, o.x)):
        color = _color(level, obj.color_channel or 1004, (80, 90, 160))
        if obj.id == BLOCK:
            top = obj.y + 15 * obj.scale_y
            bottom = obj.y - 15 * obj.scale_y
            left = obj.x - 15 * obj.scale_x
            right = obj.x + 15 * obj.scale_x
            canvas.rect(px(left), py(top), px(right), py(bottom), color, 0.92)
            if obj.color_channel in (5,):
                canvas.outline(px(left), py(top), px(right), py(bottom),
                               _color(level, 1, (0, 240, 255)), 0.35)
            else:
                canvas.outline(px(left), py(top), px(right), py(bottom),
                               _mix(color, (255, 255, 255), 0.45), 0.5)
        elif obj.id in (SPIKE, SMALL_SPIKE) or obj.id in HAZARD_IDS:
            top = obj.y + 15
            bottom = obj.y - 15
            points = [(px(obj.x - 15), py(bottom)), (px(obj.x + 15), py(bottom)),
                      (px(obj.x), py(top))]
            if int(obj.rotation) % 360 == 180:
                points = [(px(obj.x - 15), py(bottom)), (px(obj.x + 15), py(bottom)),
                          (px(obj.x), py(bottom - 30))]
            canvas.triangle(points, color)
        elif obj.id in (PAD_YELLOW, PAD_PINK, PAD_BLUE):
            pad_color = {PAD_YELLOW: (255, 220, 0), PAD_PINK: (255, 80, 200),
                         PAD_BLUE: (80, 160, 255)}[obj.id]
            canvas.rect(px(obj.x - 15), py(obj.y + 6), px(obj.x + 15), py(obj.y - 6),
                        pad_color, 0.9)
        elif obj.id in (ORB_YELLOW, ORB_PINK, ORB_BLUE):
            orb_color = {ORB_YELLOW: (255, 220, 0), ORB_PINK: (255, 80, 200),
                         ORB_BLUE: (80, 160, 255)}[obj.id]
            canvas.circle(px(obj.x), py(obj.y), 7, orb_color, 0.9)
        elif obj.id in MODE_NAMES:
            mode = MODE_NAMES[obj.id]
            tint = MODE_COLORS.get(mode, (200, 200, 255))
            canvas.rect(px(obj.x - 10), py(obj.y + 30), px(obj.x + 10), py(obj.y - 30),
                        tint, 0.45)
            canvas.outline(px(obj.x - 10), py(obj.y + 30), px(obj.x + 10), py(obj.y - 30),
                           tint, 0.95)
            canvas.text(int(px(obj.x) - 3), int(py(obj.y) - 3), mode[0].upper(), tint, 1)
        elif obj.id in (GRAVITY_NORMAL, GRAVITY_FLIP):
            canvas.rect(px(obj.x - 8), py(obj.y + 24), px(obj.x + 8), py(obj.y - 24),
                        (255, 255, 255), 0.25)
        elif obj.id in (MIRROR_ON, MIRROR_OFF):
            canvas.line(px(obj.x), py(obj.y + 30), px(obj.x), py(obj.y - 30),
                        (180, 180, 255), 0.7)
        elif obj.id in PORTAL_IDS:
            canvas.rect(px(obj.x - 8), py(obj.y + 25), px(obj.x + 8), py(obj.y - 25),
                        (255, 255, 255), 0.2)
        else:
            canvas.circle(px(obj.x), py(obj.y), 1.6, color, 0.6)

    # Route: dashed line, drawn above the level.
    if level.route:
        for (x0, y0), (x1, y1) in zip(level.route, level.route[1:]):
            canvas.line(px(x0), py(y0), px(x1), py(y1), (255, 255, 255), 0.55, dashed=True)

    # Header.
    title_color = _color(level, 1, (0, 240, 255))
    canvas.text(margin, 16, level.name[:42], title_color, 3)
    duration = level.duration_seconds or level.length_units / 311.58
    subtitle = f"GENERATED PREVIEW  {duration:.1f}S  {level.length_units / 30:.0f} BLOCKS  {len(level.objects)} OBJECTS"
    canvas.text(margin, 48, subtitle, (220, 220, 240), 1)
    canvas.text(margin, 64, "ROUTE IS ESTIMATED, NOT A VERIFIED PLAYTHROUGH", (255, 210, 90), 1)

    # Footer legend.
    fy = height - footer + 16
    legend = [
        ((0, 240, 255), "BLOCK"), ((255, 80, 80), "HAZARD"),
        ((255, 255, 255), "ROUTE"), ((200, 80, 255), "PORTAL"),
    ]
    lx = margin
    for color, label in legend:
        canvas.rect(lx, fy, lx + 10, fy + 10, color)
        canvas.text(lx + 16, fy + 2, label, (210, 210, 230), 1)
        lx += 16 + len(label) * 6 + 22
    canvas.text(margin, fy + 18, "DARK BACKGROUND - NEON PALETTE - STATIC RENDER FROM .GDLVL DATA",
                (150, 150, 180), 1)

    canvas.save_png(path)
    return path


def _color(level: Level, channel: int, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    color: Color | None = level.colors.get(channel)
    if color is None:
        return fallback
    return (color.r, color.g, color.b)


def _darken(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]
