"""Level specification and rule-based prompt parsing (RU/EN).

The generator is deterministic: a prompt is converted into a `LevelSpec`,
and the spec is rendered with a seed. Editing a level means editing its spec
and regenerating, which keeps the result reproducible.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field


THEMES: dict[str, dict] = {
    "neon": {
        "bg": "05010f", "ground": "0a0420",
        "palette": ["00f0ff", "a020f0", "2040ff", "ff20c0"],
        "label": "Neon",
    },
    "space": {
        "bg": "00030a", "ground": "020617",
        "palette": ["38f0ff", "7a5cff", "1b4bff", "c04bff"],
        "label": "Space",
    },
    "lava": {
        "bg": "120200", "ground": "240604",
        "palette": ["ff6a00", "ff2200", "ffb300", "ff007a"],
        "label": "Lava",
    },
    "ice": {
        "bg": "001018", "ground": "062433",
        "palette": ["9ff6ff", "3fd0ff", "6f8cff", "e0ffff"],
        "label": "Ice",
    },
    "cyber": {
        "bg": "030014", "ground": "0b0524",
        "palette": ["00ffd5", "ff00c8", "7a00ff", "ffe600"],
        "label": "Cyber",
    },
    "forest": {
        "bg": "020c05", "ground": "04160a",
        "palette": ["3dff8b", "00d0a0", "9dff3d", "00ffcc"],
        "label": "Forest",
    },
    "sunset": {
        "bg": "1a0033", "ground": "330a2a",
        "palette": ["ff6ad5", "ff9e3d", "a03dff", "ffd23d"],
        "label": "Sunset",
    },
}

THEME_WORDS = {
    "neon": ["неон", "neon"],
    "space": ["космос", "космич", "space", "galaxy", "галакт", "звезд", "stars"],
    "lava": ["лава", "лавов", "lava", "вулкан", "volcano"],
    "ice": ["лёд", "лед", "льдин", "ice", "frozen", "снег", "snow"],
    "cyber": ["кибер", "cyber", "matrix", "матриц", "hacker", "хакер"],
    "forest": ["лес", "forest", "джунгл", "jungle", "природ", "nature"],
    "sunset": ["закат", "sunset", "рассвет", "sunrise", "retro", "ретро"],
}

MODE_WORDS = {
    "cube": ["cube", "куб"],
    "ship": ["ship", "корабл", "кораблик"],
    "ball": ["ball", "шар"],
    "ufo": ["ufo", "нло"],
    "wave": ["wave", "волн"],
    "robot": ["robot", "робот"],
    "spider": ["spider", "паук"],
    "swing": ["swing", "качел"],
}

DIFFICULTY_ORDER = ["easy", "normal", "hard", "harder", "insane"]
DIFFICULTY_WORDS = {
    "easy": ["лёгк", "легк", "easy", "простой", "simple"],
    "normal": ["обычн", "нормал", "средн", "normal", "medium"],
    "hard": ["сложн", "hard", "трудн"],
    "harder": ["очень сложн", "хардкор", "harder", "very hard"],
    "insane": ["insane", "безумн", "экстрим", "extreme"],
}


@dataclass
class LevelSpec:
    name: str = "AI Level"
    duration: float = 30.0
    difficulty: str = "normal"
    theme: str = "neon"
    modes: list[str] = field(default_factory=lambda: ["cube", "ship", "cube"])
    decor: int = 1
    fast_second_half: bool = False
    seed: int = 1
    music_id: int = 0
    bpm: int = 120  # decorative rhythm accents; not a song-sync guarantee

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "LevelSpec":
        data = json.loads(text)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def clone(self) -> "LevelSpec":
        return copy.deepcopy(self)

    def palette_hex(self) -> list[str]:
        return list(THEMES[self.theme]["palette"])

    def bg_hex(self) -> str:
        return THEMES[self.theme]["bg"]

    def ground_hex(self) -> str:
        return THEMES[self.theme]["ground"]


def _find_mode(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    lowered = text.lower()
    for mode, words in MODE_WORDS.items():
        for word in words:
            for match in re.finditer(re.escape(word), lowered):
                found.append((match.start(), mode))
    found.sort()
    # Remove duplicates that come from overlapping words (e.g. "куб" in "кубик").
    modes: list[tuple[int, str]] = []
    for pos, mode in found:
        if modes and modes[-1][1] == mode and pos - modes[-1][0] < 12:
            continue
        modes.append((pos, mode))
    return modes


def _difficulty_up(current: str, steps: int = 1) -> str:
    index = DIFFICULTY_ORDER.index(current)
    return DIFFICULTY_ORDER[min(len(DIFFICULTY_ORDER) - 1, index + steps)]


def _difficulty_down(current: str, steps: int = 1) -> str:
    index = DIFFICULTY_ORDER.index(current)
    return DIFFICULTY_ORDER[max(0, index - steps)]


def parse_prompt(text: str, base: LevelSpec | None = None) -> LevelSpec:
    """Apply the instructions found in `text` to a copy of `base`."""
    spec = (base or LevelSpec()).clone()
    original = text
    text_l = text.lower()

    # --- explicit name: «...», "...", название: ...
    name_match = re.search(r"(?:название|name)\s*[:\-]\s*[\"'«]?([^\"'»\n]+)", text, re.I)
    if name_match:
        spec.name = name_match.group(1).strip()
    else:
        quoted = re.search(r"[«\"]([^»\"]{2,60})[»\"]", original)
        if quoted:
            spec.name = quoted.group(1).strip()

    # --- duration
    duration_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:сек(?:унд)?|seconds?|secs?|s)\b", text_l
    )
    if duration_match:
        spec.duration = max(10.0, min(180.0, float(duration_match.group(1).replace(",", "."))))
    elif re.search(r"длинн|дольше|longer", text_l):
        spec.duration = min(180.0, spec.duration + 15.0)
    elif re.search(r"короч|shorter", text_l):
        spec.duration = max(10.0, spec.duration - 10.0)

    # --- theme
    for theme, words in THEME_WORDS.items():
        if any(word in text_l for word in words):
            spec.theme = theme
            break

    # --- explicit slot replacement ("замени Ship на Wave" / "replace ship with wave")
    for match in re.finditer(
        r"(?:замен\w*|поменя\w*|replace)\s+([a-zа-яё]+)\s+(?:на|with)\s+([a-zа-яё]+)",
        text_l,
    ):
        old = _mode_from_word(match.group(1))
        new = _mode_from_word(match.group(2))
        if old and new and old in spec.modes:
            spec.modes = [new if m == old else m for m in spec.modes]

    # --- mode sequence
    mentions = _find_mode(text_l)
    if mentions:
        replacement_text = re.sub(
            r"(?:замен\w*|поменя\w*|replace).*?(?:на|with)\s+[a-zа-яё]+", "", text_l
        )
        mentions = _find_mode(replacement_text)
        if len(mentions) >= 2:
            spec.modes = [mode for _, mode in mentions]
        elif len(mentions) == 1:
            mode = mentions[0][1]
            if mode not in spec.modes:
                spec.modes = ["cube", mode, "cube"]

    # --- difficulty
    if re.search(r"сложнее|harder|increase difficulty", text_l):
        spec.difficulty = _difficulty_up(spec.difficulty)
    elif re.search(r"проще|легче|easier|decrease difficulty", text_l):
        spec.difficulty = _difficulty_down(spec.difficulty)
    else:
        for difficulty, words in DIFFICULTY_WORDS.items():
            if any(word in text_l for word in words):
                spec.difficulty = difficulty
                break

    # --- decorations
    if re.search(r"без декор|no decor", text_l):
        spec.decor = 0
    elif re.search(r"больше декор|more decor", text_l):
        spec.decor = min(3, spec.decor + 1)
    elif re.search(r"меньше декор|less decor", text_l):
        spec.decor = max(0, spec.decor - 1)
    elif re.search(r"декор|decoration", text_l):
        spec.decor = max(spec.decor, 2)

    # --- speed
    if re.search(r"втор(ая|ую) половин\w* быстрее|faster.*second half|half.*faster", text_l):
        spec.fast_second_half = True
    elif re.search(r"втор(ая|ую) половин\w* медленнее|slower.*second half", text_l):
        spec.fast_second_half = False

    # --- beat grid (cosmetic accents; track BPM must be supplied)
    bpm_match = re.search(r"\b(\d{2,3})\s*bpm\b|\bbpm\s*[:=]?\s*(\d{2,3})\b", text_l)
    if bpm_match:
        spec.bpm = max(40, min(300, int(next(g for g in bpm_match.groups() if g))))

    # --- music
    music_match = re.search(r"(?:музык\w*|music|song)\s*(?:id)?\s*[:=]?\s*(\d+)", text_l)
    if music_match:
        spec.music_id = int(music_match.group(1))

    return spec


def _mode_from_word(word: str) -> str | None:
    word = word.lower()
    for mode, words in MODE_WORDS.items():
        if any(word.startswith(w) or w.startswith(word) for w in words):
            return mode
    return None


def describe(spec: LevelSpec) -> str:
    theme = THEMES[spec.theme]["label"]
    modes = " -> ".join(m.capitalize() for m in spec.modes)
    return (
        f"{spec.name}: {spec.duration:.0f}s, {spec.difficulty}, theme {theme}, "
        f"modes {modes}, decor {spec.decor}/3, BPM {spec.bpm}"
    )
