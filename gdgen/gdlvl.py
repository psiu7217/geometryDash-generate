"""Read / write Geometry Dash `.gdlvl` files (GD 2.209+).

Container: urlsafe_base64( gzip( XML plist with a single level dict ) ).
The level data itself (`k4`) is gzip + base64url encoded inside the plist.
"""

from __future__ import annotations

import base64
import binascii
import gzip
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


def compress_text(text: str) -> str:
    return _b64encode(gzip.compress(text.encode("utf-8"), mtime=0))


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


def build_level_dict(level: Level) -> str:
    """Build the plist `<dict>` for a level file."""
    entries = [
        _entry("kCEK", "i", "4"),
        _entry("k2", "s", level.name),
        _entry("k3", "s", base64.b64encode(level.description.encode("utf-8")).decode("ascii")),
        _entry("k4", "s", encode_level_data(level.to_level_string())),
        _entry("k5", "s", level.author),
        _entry("k13", "t", ""),
        _entry("k16", "i", "1"),
        _entry("k21", "i", "2"),
        _entry("k45", "i", str(level.music_id)),
        _entry("k48", "i", "0"),
        _entry("k50", "i", "0"),
        _entry("k80", "i", "0"),
        _entry("k101", "i", "0"),
        _entry("k156", "i", "0"),
    ]
    return "<dict>" + "".join(entries) + "</dict>"


def build_gdlvl_xml(level: Level) -> str:
    return (
        '<?xml version="1.0"?>'
        '<plist version="1.0" gjver="2.0">'
        + build_level_dict(level)
        + "</plist>"
    )


def encode_gdlvl(level: Level) -> bytes:
    return _b64encode(gzip.compress(build_gdlvl_xml(level).encode("utf-8"), mtime=0)).encode("ascii")


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
    dict_el = root.find("dict")
    if dict_el is None:
        dict_el = root.find(".//dict")
    if dict_el is None:
        raise ValueError(".gdlvl не содержит <dict> уровня")
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
