"""Regression coverage for the cyber-city preset and detailed preview."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from gdgen import cli
from gdgen.city import CITY_GLOW, CITY_PANEL
from gdgen.generator import generate, spec_from_preset
from gdgen.gdlvl import load_gdlvl
from gdgen.preview import render_preview
from gdgen.spec import parse_prompt
from gdgen.validate import validate


class CyberCityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = spec_from_preset("neon-cyber-city")
        cls.level = generate(cls.spec)

    def test_preset_attributes(self):
        self.assertEqual(self.spec.duration, 60)
        self.assertEqual(self.spec.difficulty, "hard")
        self.assertEqual(self.spec.theme, "cyber")
        self.assertIn("wave", self.spec.modes)
        self.assertEqual(self.spec.bpm, 120)

    def test_city_uses_cosmetic_objects(self):
        city = [o for o in self.level.objects if o.id in (CITY_PANEL, CITY_GLOW)]
        self.assertGreater(len(city), 100)
        self.assertTrue(all(o.id != 1 for o in city))
        self.assertTrue(all(o.get(20) == 3 for o in city))

    def test_deterministic_and_valid(self):
        self.assertEqual(generate(self.spec).to_level_string(), self.level.to_level_string())
        result = validate(self.level)
        self.assertTrue(result.ok, result.summary())

    def test_bpm_from_prompt(self):
        self.assertEqual(parse_prompt("Киберпанк 142 BPM").bpm, 142)
        self.assertEqual(parse_prompt("cyber BPM: 95").bpm, 95)

    def test_detail_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "detail.png"
            render_preview(self.level, out, 14, 18, start_x=1200, window_blocks=90)
            data = out.read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual(width, 1300)
            self.assertGreater(height, 200)

    def test_invalid_detail_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                render_preview(self.level, Path(tmp) / "a.png", window_blocks=0)
            with self.assertRaises(ValueError):
                render_preview(self.level, Path(tmp) / "b.png",
                               start_x=1_000_000, window_blocks=90)


class PreviewOnlyTests(unittest.TestCase):
    def test_preview_only_does_not_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = cli.main(["generate", "--preset", "neon-cyber-city",
                           "--out", tmp, "--preview-only"])
            self.assertEqual(rc, 0)
            self.assertFalse((Path(tmp) / "neon_cyber_city.gdlvl").exists())
            self.assertFalse((Path(tmp) / "neon_cyber_city.json").exists())
            self.assertTrue((Path(tmp) / "preview" / "neon_cyber_city.png").exists())
            self.assertTrue((Path(tmp) / "preview" / "neon_cyber_city_detail.png").exists())

    def test_edit_out_keeps_original_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["generate", "--preset", "ai-neon-run",
                                      "--out", tmp, "--no-preview"]), 0)
            original = Path(tmp) / "ai_neon_run.gdlvl"
            sidecar = original.with_suffix(".json")
            target = Path(tmp) / "revision.gdlvl"
            self.assertTrue(sidecar.exists())
            self.assertEqual(cli.main(["edit", str(original), "--out", str(target),
                                       "--prompt", "Сделай сложнее",
                                       "--no-preview"]), 0)
            self.assertTrue(sidecar.exists())
            self.assertTrue(target.exists())
            self.assertTrue(target.with_suffix(".json").exists())
            self.assertEqual(load_gdlvl(original).name, "AI Neon Run")


if __name__ == "__main__":
    unittest.main()
