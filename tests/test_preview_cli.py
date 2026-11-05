import struct
import tempfile
import unittest
from pathlib import Path

from gdgen import cli
from gdgen.generator import generate, spec_from_preset
from gdgen.preview import render_preview


class PreviewTests(unittest.TestCase):
    def test_png_structure(self):
        level = generate(spec_from_preset("ai-neon-run"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.png"
            render_preview(level, path)
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            width, height = struct.unpack(">II", data[16:24])
            self.assertGreater(width, 1000)
            self.assertGreater(height, 200)
            self.assertLess(len(data), 5_000_000)
            self.assertIn(b"IEND", data)


class CliTests(unittest.TestCase):
    def test_generate_edit_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(["generate", "--preset", "ai-neon-run", "--out", tmp, "--no-preview"])
            self.assertEqual(code, 0)
            path = Path(tmp) / "ai_neon_run.gdlvl"
            self.assertTrue(path.exists())
            self.assertTrue((Path(tmp) / "ai_neon_run.json").exists())

            code = cli.main(["edit", str(path), "--prompt", "Добавь больше декораций", "--no-preview"])
            self.assertEqual(code, 0)
            data = (Path(tmp) / "ai_neon_run.json").read_text(encoding="utf-8")
            self.assertIn("_generator", data)

            out = Path(tmp) / "out.png"
            code = cli.main(["preview", str(path), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

            code = cli.main(["inspect", str(path)])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
