import unittest

from gdgen.generator import generate, spec_from_preset
from gdgen.gdlvl import (
    decode_gdlvl_bytes, encode_gdlvl, level_from_xml, load_gdlvl, save_gdlvl,
)
from gdgen.level import parse_colors, parse_level_string


class GdlvlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = generate(spec_from_preset("ai-neon-run"))

    def test_encoded_container(self):
        data = encode_gdlvl(self.level)
        self.assertTrue(data.startswith(b"H4sI"))
        root = decode_gdlvl_bytes(data)
        restored = level_from_xml(root)
        self.assertEqual(restored.name, "AI Neon Run")
        self.assertEqual(len(restored.objects), len(self.level.objects))
        self.assertGreater(restored.length_units, 9000)

    def test_file_roundtrip(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "level.gdlvl"
            save_gdlvl(path, self.level)
            self.assertTrue(path.exists())
            loaded = load_gdlvl(path)
            self.assertEqual(loaded.name, self.level.name)
            self.assertEqual(len(loaded.objects), len(self.level.objects))
            self.assertEqual(set(loaded.colors), set(self.level.colors))
            self.assertGreater(len(path.read_bytes()), 1000)

    def test_header_has_colors(self):
        text = self.level.to_level_string()
        header, objects = parse_level_string(text)
        self.assertIn("kS38", header)
        self.assertEqual(header["kA6"], "1000")
        self.assertEqual(header["kA7"], "1001")
        colors = parse_colors(header)
        self.assertIn(1000, colors)
        self.assertIn(1, colors)
        self.assertEqual(colors[1].blending, True)
        self.assertGreater(len(objects), 100)

    def test_level_string_ends_with_semicolon(self):
        text = self.level.to_level_string()
        self.assertTrue(text.endswith(";"))
        self.assertEqual(text.count(";"), len(self.level.objects) + 1)


if __name__ == "__main__":
    unittest.main()
