import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from gdgen.gdlvl import build_level_dict
from gdgen.generator import generate, spec_from_preset
from gdgen.level import Level
from gdgen.savefile import (
    SaveFileError, add_level, decode_save, encode_save, is_game_running, list_levels,
)


def write_save(path: Path, levels: list[Level]) -> None:
    body = "".join(
        f"<k>k_{index}</k>{build_level_dict(level)}"
        for index, level in enumerate(levels)
    )
    xml = (
        '<?xml version="1.0"?><plist version="1.0" gjver="2.0"><dict>'
        "<k>LLM_01</k><dict>"
        "<k>_isArr</k><t />"
        + body
        + "</dict></dict></plist>"
    )
    path.write_bytes(encode_save(xml))


class SaveFileTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        xml = "<plist><dict><k>LLM_01</k><dict><k>_isArr</k><t /></dict></dict></plist>"
        raw = encode_save(xml)
        self.assertEqual(decode_save(raw), xml)
        self.assertNotIn(b"<plist", raw)

    def test_is_game_running_is_bool(self):
        self.assertIsInstance(is_game_running(), bool)

    def test_add_level_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "CCLocalLevels.dat"
            write_save(save, [Level(name="Existing Level")])
            before = save.read_bytes()

            new_level = generate(spec_from_preset("ai-neon-run"))
            used, backup = add_level(new_level, save, allow_running=True)

            self.assertEqual(used, save)
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_bytes(), before)
            names = list_levels(save)
            self.assertEqual(names[0], "AI Neon Run")
            self.assertIn("Existing Level", names)
            self.assertEqual(len(names), 2)

    def test_duplicate_name_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "CCLocalLevels.dat"
            write_save(save, [Level(name="AI Neon Run")])
            new_level = generate(spec_from_preset("ai-neon-run"))
            with self.assertRaises(SaveFileError):
                add_level(new_level, save, allow_running=True)

    def test_missing_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SaveFileError):
                list_levels(Path(tmp) / "nope.dat")


if __name__ == "__main__":
    unittest.main()
