"""Safe offline access to Geometry Dash's `CCLocalLevels.dat`.

Encoding: XOR 11 -> urlsafe base64 -> gzip -> XML plist.
Writes are refused while the game is running, always go through a backup and
a verified temporary file, and never delete existing levels.
"""

from __future__ import annotations

import base64
import datetime as _dt
import gzip
import os
import pathlib
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .gdlvl import build_level_dict, level_from_xml
from .level import Level


DEFAULT_SAVE = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "GeometryDash" / "CCLocalLevels.dat"
BACKUPS_KEPT = 10


class SaveFileError(RuntimeError):
    pass


def is_game_running() -> bool:
    try:
        output = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq GeometryDash.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.lower()
        return "geometrydash.exe" in output
    except (OSError, subprocess.SubprocessError):
        return False


def decode_save(raw: bytes) -> str:
    table = bytes((b ^ 11) for b in range(256))
    decoded = raw.translate(table).decode("latin-1").replace("\x00", "")
    decoded = decoded.replace("-", "+").replace("_", "/")
    decoded += "=" * (-len(decoded) % 4)
    try:
        return gzip.decompress(base64.b64decode(decoded)).decode("utf-8")
    except Exception as exc:  # gzip / base64 / utf-8
        raise SaveFileError(f"Не удалось декодировать сохранение: {exc}") from exc


def encode_save(xml: str) -> bytes:
    packed = gzip.compress(xml.encode("utf-8"), mtime=0)
    text = base64.b64encode(packed).decode("ascii").replace("+", "-").replace("/", "_")
    table = bytes((b ^ 11) for b in range(256))
    return text.encode("latin-1").translate(table)


def _level_list(root: ET.Element) -> ET.Element:
    top = root.find("dict")
    if top is None:
        raise SaveFileError("В сохранении нет корневого <dict>.")
    children = [c for c in top if isinstance(c.tag, str)]
    for i in range(0, len(children) - 1, 2):
        if children[i].tag == "k" and (children[i].text or "") == "LLM_01":
            return children[i + 1]
    raise SaveFileError("В сохранении нет списка локальных уровней LLM_01.")


def _entries(dict_el: ET.Element) -> list[tuple[str, ET.Element, ET.Element]]:
    """Return (key, key_element, value_element) for a flat plist dict."""
    result = []
    children = [c for c in dict_el if isinstance(c.tag, str)]
    for i in range(0, len(children) - 1, 2):
        if children[i].tag == "k":
            result.append(((children[i].text or ""), children[i], children[i + 1]))
    return result


def list_levels(path: pathlib.Path | None = None) -> list[str]:
    path = pathlib.Path(path or DEFAULT_SAVE)
    if not path.exists():
        raise SaveFileError(
            f"Файл сохранения не найден: {path}. Запустите Geometry Dash один раз, "
            "чтобы игра создала сохранение."
        )
    root = ET.fromstring(decode_save(path.read_bytes()))
    levels = _level_list(root)
    ordered = []
    for key, _, value in _entries(levels):
        if not key.startswith("k_"):
            continue
        try:
            index = int(key[2:])
        except ValueError:
            index = 10 ** 9
        ordered.append((index, value))
    ordered.sort(key=lambda item: item[0])
    names = []
    for _, value in ordered:
        for k, _, v in _entries(value):
            if k == "k2":
                names.append("".join(v.itertext()))
    return names


def add_level(level: Level, path: pathlib.Path | None = None,
              *, allow_running: bool = False) -> tuple[pathlib.Path, pathlib.Path]:
    """Insert `level` as the newest local level. Returns (save, backup)."""
    path = pathlib.Path(path or DEFAULT_SAVE)
    if not path.exists():
        raise SaveFileError(
            f"Файл сохранения не найден: {path}. Запустите Geometry Dash один раз, "
            "закройте игру и повторите импорт."
        )
    if not allow_running and is_game_running():
        raise SaveFileError(
            "Geometry Dash запущена. Полностью закройте игру перед записью сохранения "
            "(или используйте штатную кнопку Import в игре)."
        )

    root = ET.fromstring(decode_save(path.read_bytes()))
    levels = _level_list(root)
    existing = list_levels(path)
    if any(name.strip().lower() == level.name.strip().lower() for name in existing):
        raise SaveFileError(
            f"Уровень с именем «{level.name}» уже существует. "
            "Удалите/переименуйте его в игре или задайте другое имя."
        )

    # Shift k_N -> k_{N+1}, descending so renames cannot collide.
    shifts = []
    for key, key_el, _ in _entries(levels):
        if key.startswith("k_") and key[2:].isdigit():
            shifts.append((int(key[2:]), key_el))
    for index, key_el in sorted(shifts, reverse=True):
        key_el.text = f"k_{index + 1}"

    # Keep GD's identity fields unique: it silently drops levels whose k80/k126
    # collide, and k83 controls the order in the local level list.
    used_ids: set[int] = set()
    used_nonces: set[str] = set()
    max_order = 0
    for key, _, value in _entries(levels):
        if not key.startswith("k_"):
            continue
        fields = {k: "".join(v.itertext()) for k, _, v in _entries(value)}
        if fields.get("k80", "").isdigit():
            used_ids.add(int(fields["k80"]))
        if fields.get("k126"):
            used_nonces.add(fields["k126"])
        if fields.get("k83", "").isdigit():
            max_order = max(max_order, int(fields["k83"]))

    new_dict = ET.fromstring(build_level_dict(level, tag="d"))
    new_fields = {k: v for k, _, v in _entries(new_dict)}
    level_id = int("".join(new_fields["k80"].itertext()))
    while level_id in used_ids:
        level_id += 1
    new_fields["k80"].text = str(level_id)
    new_fields["k83"].text = str(max_order + 1)
    nonce = "".join(new_fields["k126"].itertext())
    counter = 0
    while nonce in used_nonces:
        counter += 1
        nonce = ("".join(new_fields["k126"].itertext())[:14] + f"{counter:02d}")
    new_fields["k126"].text = nonce

    key_el = ET.Element("k")
    key_el.text = "k_0"
    # Keep the `_isArr` marker first, then put the new level at the top of the
    # list so Geometry Dash shows it first in the editor's local levels.
    levels.insert(2, key_el)
    levels.insert(3, new_dict)

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=False).decode("utf-8")
    data = encode_save(xml)

    backup = backup_save(path)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_bytes(data)
        # Verify the file can be decoded and contains our level before replacing.
        check = ET.fromstring(decode_save(tmp_path.read_bytes()))
        check_levels = _level_list(check)
        found = False
        for key, _, value in _entries(check_levels):
            if key != "k_0":
                continue
            for k, _, v in _entries(value):
                if k == "k2" and "".join(v.itertext()) == level.name:
                    found = True
        if not found:
            raise SaveFileError("Проверка временного файла не нашла добавленный уровень.")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return path, backup


def backup_save(path: pathlib.Path) -> pathlib.Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.backup-{stamp}")
    shutil.copy2(path, backup)
    _prune_backups(path)
    return backup


def _prune_backups(path: pathlib.Path) -> None:
    backups = sorted(path.parent.glob(path.name + ".backup-*"))
    for old in backups[:-BACKUPS_KEPT]:
        try:
            old.unlink()
        except OSError:
            pass


def load_save_level(name: str, path: pathlib.Path | None = None) -> Level:
    """Read one local level from the save file (useful for inspection)."""
    path = pathlib.Path(path or DEFAULT_SAVE)
    root = ET.fromstring(decode_save(path.read_bytes()))
    for key, _, value in _entries(_level_list(root)):
        if not key.startswith("k_"):
            continue
        entries = {k: v for k, _, v in _entries(value)}
        level_name = "".join(entries.get("k2").itertext()) if entries.get("k2") is not None else ""
        if level_name.lower() == name.lower():
            wrapper = ET.Element("plist")
            wrapper.append(value)
            return level_from_xml(wrapper)
    raise SaveFileError(f"Уровень «{name}» не найден в сохранении.")
