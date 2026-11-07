"""Read / write Geometry Dash `.gdlvl` files (GD 2.209+).

Container: urlsafe_base64( gzip( XML plist with a single level dict ) ).
The level data itself (`k4`) is gzip + base64url encoded inside the plist.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import html
import pathlib
import re
import xml.etree.ElementTree as ET

from .level import Color, Level, parse_colors, parse_level_string
from .objects import GDObject, fmt_num


def _b64decode(data: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode("ascii")
    data = b"".join(data.split())
    data += b"=" * (-len(data) % 4)
    data = data.replace(b"+", b"-").replace(b"/", b"_")
    return base64.urlsafe_b64decode(data)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _stable_gzip(data: bytes) -> bytes:
    """gzip with a fixed header so bytes match on Windows and Linux.

    ``gzip.compress(..., mtime=0)`` already zeroes the timestamp, but Python
    still writes a platform-dependent OS byte at offset 9, which made CI keep
    re-committing identical levels. Force the standard unknown value instead.
    """
    compressed = bytearray(gzip.compress(data, mtime=0))
    compressed[9] = 255
    return bytes(compressed)


def compress_text(text: str) -> str:
    return _b64encode(_stable_gzip(text.encode("utf-8")))


def decompress_text(value: str) -> str:
    if not value:
        return ""
    if value.startswith("H4sI"):
        return gzip.decompress(_b64decode(value)).decode("utf-8", errors="replace")
    return value


def encode_level_data(level_string: str) -> str:
    return compress_text(level_string)


def decode_level_data(value: str) -> str:
    return decompress_text(value)


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _entry(key: str, kind: str, value: str) -> str:
    if kind == "t":
        return f"<k>{key}</k><t />"
    return f"<k>{key}</k><{kind}>{_xml_escape(value)}</{kind}>"


def _stable_identity(level: Level) -> tuple[str, str]:
    """Deterministic level id and server nonce derived from the level content."""
    payload = encode_level_data(level.to_level_string())
    seed = (level.name + "|" + payload).encode("utf-8")
    digest = hashlib.md5(seed).digest()
    level_id = str(100000 + int.from_bytes(digest[:4], "big") % 900000)
    nonce = base64.urlsafe_b64encode(hashlib.sha256(seed + b"nonce").digest()).decode("ascii")[:16]
    return level_id, nonce


def build_level_dict(level: Level, tag: str = "dict") -> str:
    """Build a plist dict for one level.

    `tag` is `dict` for standalone `.gdlvl` files. Inside `CCLocalLevels.dat`
    Geometry Dash stores nested dictionaries with its own shorthand tag `<d>`
    and ignores unknown elements, so save-file import must use `tag="d"`.

    Geometry Dash silently drops local levels that lack the identity fields it
    writes itself (`k80` id, `k83` order and `k126` nonce), so a full set of
    keys is emitted here. Types and defaults mirror a real GD 2.209 save entry.
    """
    level_id, nonce = _stable_identity(level)
    entries = [
        _entry("kCEK", "i", "4"),
        _entry("k18", "i", "0"),
        _entry("k36", "i", "0"),
        _entry("k85", "i", "0"),
        _entry("k86", "i", "0"),
        _entry("k87", "i", "0"),
        _entry("k88", "s", "100"),
        _entry("k23", "i", "0"),
        _entry("k19", "i", "0"),
        _entry("k71", "i", "0"),
        _entry("k90", "i", "0"),
        _entry("k20", "i", "2"),
        _entry("k109", "s", "0"),
        _entry("k110", "s", "0"),
        _entry("k2", "s", level.name),
        _entry("k3", "s", base64.b64encode(level.description.encode("utf-8")).decode("ascii")),
        _entry("k4", "s", encode_level_data(level.to_level_string())),
        _entry("k5", "s", level.author),
        _entry("k101", "s", ",".join(["0"] * 20)),
        _entry("k8", "i", "2"),
        _entry("k13", "t", ""),
        _entry("k21", "i", "2"),
        _entry("k16", "i", "1"),
        _entry("k80", "i", level_id),
        _entry("k83", "i", "1"),
        _entry("k64", "i", "1"),
        _entry("k45", "i", str(level.music_id)),
        _entry("k50", "i", "51"),
        _entry("k48", "i", "0"),
        _entry("kI1", "r", "0"),
        _entry("kI2", "r", "0"),
        _entry("kI3", "r", "1"),
        _entry("kI5", "i", "0"),
        _entry("kI6", "d", "00102030405060708090100110120130"),
        _entry("kI7", "i", "-1"),
        _entry("k126", "s", nonce),
    ]
    return f"<{tag}>" + "".join(entries) + f"</{tag}>"


def build_gdlvl_xml(level: Level) -> str:
    return (
        '<?xml version="1.0"?>'
        '<plist version="1.0" gjver="2.0">'
        + build_level_dict(level)
        + "</plist>"
    )


def encode_gdlvl(level: Level) -> bytes:
    return _b64encode(_stable_gzip(build_gdlvl_xml(level).encode("utf-8"))).encode("ascii")


def decode_gdlvl_bytes(raw: bytes) -> ET.Element:
    xml_bytes = gzip.decompress(_b64decode(raw))
    text = xml_bytes.decode("utf-8", errors="replace")
    if not text.lstrip().startswith("<?xml") and not text.lstrip().startswith("<plist"):
        raise ValueError("Не удалось распознать .gdlvl: внутри нет XML plist")
    return ET.fromstring(text)


def flat_entries(dict_element: ET.Element) -> dict[str, ET.Element]:
    """Return key -> value element for a flat plist dict."""
    entries: dict[str, ET.Element] = {}
    children = [c for c in dict_element if isinstance(c.tag, str)]
    for i in range(0, len(children) - 1, 2):
        key_el, value_el = children[i], children[i + 1]
        if key_el.tag != "k":
            continue
        entries[(key_el.text or "")] = value_el
    return entries


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return html.unescape("".join(element.itertext()))


def _int(element: ET.Element | None, default: int = 0) -> int:
    try:
        return int(float(_text(element)))
    except (ValueError, TypeError):
        return default


def level_from_xml(root: ET.Element) -> Level:
    # Standalone .gdlvl uses <dict>, while CCLocalLevels.dat uses the
    # abbreviated <d> tag for each nested level dictionary.
    dict_el = next(
        (candidate for candidate in (
            root.find("dict"), root.find("d"), root.find(".//dict"), root.find(".//d"),
        ) if candidate is not None),
        None,
    )
    if dict_el is None:
        raise ValueError("Данные уровня не содержат <dict> или <d>")
    entries = flat_entries(dict_el)
    name = _text(entries.get("k2")) or "Unnamed"
    description_raw = _text(entries.get("k3"))
    try:
        description = base64.b64decode(description_raw).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        description = description_raw
    level_string = decode_level_data(_text(entries.get("k4")))
    header, objects = parse_level_string(level_string)
    colors = parse_colors(header)
    level = Level(
        name=name,
        description=description,
        author=_text(entries.get("k5")) or "Unknown",
        objects=objects,
        colors=colors or Level(name=name).colors,
        music_id=_int(entries.get("k45")),
    )
    try:
        level.start_speed = int(header.get("kA4", "0"))
        level.start_mode = int(header.get("kA2", "0"))
        level.bg_channel = int(header.get("kA6", "1000"))
        level.ground_channel = int(header.get("kA7", "1001"))
    except ValueError:
        pass
    return level


def load_gdlvl(path: str | pathlib.Path) -> Level:
    return level_from_xml(decode_gdlvl_bytes(pathlib.Path(path).read_bytes()))


def save_gdlvl(path: str | pathlib.Path, level: Level) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_gdlvl(level))
    return path


# --------------------------------------------------------------------- objects
def objects_to_string(objects: list[GDObject]) -> str:
    return "".join(o.to_string() + ";" for o in objects)


__all__ = [
    "encode_gdlvl", "decode_gdlvl_bytes", "load_gdlvl", "save_gdlvl",
    "level_from_xml", "compress_text", "decompress_text", "fmt_num",
]
