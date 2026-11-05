"""Static validation of generated levels.

These checks catch malformed files and obvious design mistakes. They do not
prove that a level is beatable — see PROGRESS.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .level import Level
from .objects import BLOCK, HAZARD_IDS, MODE_NAMES, PORTAL_IDS
from .generator import JUMP_LENGTH, SPEED_FACTOR
from .route import GROUND_Y, _corridor_center


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            lines.extend(f"  - {w}" for w in self.warnings)
        if not lines:
            lines.append("OK: структурных ошибок не найдено.")
        return "\n".join(lines)


def validate(level: Level) -> ValidationResult:
    result = ValidationResult()
    objects = level.objects

    if not objects:
        result.errors.append("Уровень не содержит объектов.")
        return result

    if not level.name.strip():
        result.errors.append("У уровня пустое имя.")

    # --- coordinates
    for obj in objects:
        if not (math.isfinite(obj.x) and math.isfinite(obj.y)):
            result.errors.append(f"Некорректные координаты у объекта id={obj.id}.")
            break
        if obj.x < -300 or obj.y < -300 or obj.y > 900:
            result.errors.append(
                f"Объект id={obj.id} вне разумных границ: x={obj.x}, y={obj.y}."
            )
            break

    # --- bounds / length
    min_x, max_x, min_y, max_y = level.bounds()
    result.info["length_units"] = round(max_x, 1)
    result.info["duration_estimate"] = round(level.duration_seconds or max_x / 311.58, 2)
    if max_x < 3000:
        result.warnings.append("Уровень короче 3000 units — это меньше 10 секунд.")

    # --- start safety
    first_hazard = min((o.x for o in objects if o.id in HAZARD_IDS), default=None)
    if first_hazard is not None and first_hazard < 300:
        result.errors.append(
            f"Первый шип слишком близко к старту (x={first_hazard}). Нужно >= 300."
        )

    # --- portals
    mode_portals = [o for o in objects if o.id in MODE_NAMES]
    if not mode_portals:
        result.warnings.append("В уровне нет порталов смены режима.")
    else:
        xs = [o.x for o in mode_portals]
        if xs != sorted(xs):
            result.errors.append("Порталы режимов стоят не по порядку по X.")
        for obj in mode_portals:
            if obj.y < 0 or obj.y > 200:
                result.warnings.append(
                    f"Портал {MODE_NAMES[obj.id]} на необычной высоте y={obj.y}."
                )

    # --- hazards and jump feasibility
    hazard_xs = sorted(o.x for o in objects if o.id in HAZARD_IDS and o.y < 120)
    groups: list[list[float]] = []
    for x in hazard_xs:
        if groups and x - groups[-1][-1] <= 31:
            groups[-1].append(x)
        else:
            groups.append([x])
    speed = _speed_at(level, groups[0][0] if groups else 0)
    jump_len = JUMP_LENGTH.get(speed, 136)
    previous_end: float | None = None
    for group in groups:
        width = group[-1] - group[0] + 30
        if width > jump_len - 20:
            result.errors.append(
                f"Группа шипов шириной {width:.0f} units не перепрыгивается "
                f"прыжком длиной {jump_len} (x={group[0]:.0f})."
            )
        if previous_end is not None and group[0] - previous_end < 70:
            result.warnings.append(f"Слишком плотная группа шипов около x={group[0]:.0f}.")
        previous_end = group[-1]

    # --- route clears low hazards
    if level.route:
        for x in hazard_xs:
            y = _route_y(level.route, x)
            if y is not None and y < 50:
                result.warnings.append(
                    f"Расчётный маршрут проходит слишком низко над шипом x={x:.0f} (y={y:.0f})."
                )
    else:
        result.warnings.append("Маршрут игрока не рассчитан.")

    # --- free space along the route (ship/wave corridors)
    if level.route:
        for section in level.sections:
            if section.get("mode") not in {"ship", "wave"}:
                continue
            start = section["start"] + 240
            end = section["end"] - 260
            x = start
            while x < end:
                center = _corridor_center(level, x)
                if center is None:
                    result.errors.append(
                        f"В ship-секции на x={x:.0f} не найден свободный коридор."
                    )
                    break
                route_y = _route_y(level.route, x)
                if route_y is not None and abs(center - route_y) > 120:
                    result.warnings.append(
                        f"Маршрут сильно расходится с центром коридора на x={x:.0f}."
                    )
                    break
                x += 90

    # --- colour channels
    for channel in {level.bg_channel, level.ground_channel}:
        if channel not in level.colors:
            result.errors.append(f"Цветовой канал {channel} не определён в kS38.")

    # --- size
    level_string = level.to_level_string()
    result.info["level_string_bytes"] = len(level_string.encode("utf-8"))
    if len(level_string.encode("utf-8")) > 8_000_000:
        result.errors.append("Строка уровня больше 8 МБ — GD может не принять файл.")

    return result


def _speed_at(level: Level, x: float) -> int:
    # Internal index: 0 slow, 1 normal, 2 fast, 3 faster, 4 fastest.
    speed = 1
    for obj in sorted(level.objects, key=lambda o: o.x):
        if obj.x > x:
            break
        if obj.id == 200:
            speed = 0
        elif obj.id == 201:
            speed = 1
        elif obj.id == 202:
            speed = 2
        elif obj.id == 203:
            speed = 3
        elif obj.id == 1334:
            speed = 4
    return speed


def _route_y(route: list[tuple[float, float]], x: float) -> float | None:
    if not route:
        return None
    if x <= route[0][0]:
        return route[0][1]
    for (x0, y0), (x1, y1) in zip(route, route[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return route[-1][1]
