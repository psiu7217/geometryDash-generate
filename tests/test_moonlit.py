"""Moonlit regression: 60s, modes, safety, export and cosmetic art."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gdgen import cli
from gdgen.generator import generate, spec_from_preset
from gdgen.gdlvl import load_gdlvl, save_gdlvl
from gdgen.moonlit import (
    CLOUD_IDS, GLOW, MOON_DISC, MOONLIT_DECOR_IDS,
    MOVE_TRIGGER, PULSE_TRIGGER, ship_corridor_bounds,
)
from gdgen.objects import BLOCK, HAZARD_IDS, PORTAL_BALL, PORTAL_WAVE
from gdgen.validate import validate


class MoonlitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = spec_from_preset("moonlit-cloud-kingdom")
        cls.level = generate(cls.spec)

    def test_gameplay_configuration(self):
        self.assertEqual(self.spec.modes, ["cube", "ship", "ball", "wave"])
        self.assertEqual(self.spec.difficulty, "easy")
        self.assertLessEqual(len(self.spec.name), 20)
        self.assertAlmostEqual(self.level.duration_seconds, 60, delta=0.3)
        self.assertEqual([s["mode"] for s in self.level.sections],
                         ["cube", "ship", "ball", "wave"])

    def test_reachable_portals_and_ball_geometry(self):
        objects = self.level.objects
        self.assertEqual(sum(o.id == PORTAL_BALL for o in objects), 3)
        self.assertEqual(sum(o.id == PORTAL_WAVE for o in objects), 2)
        ball = self.level.sections[2]
        ceiling = [o for o in objects if o.id == BLOCK
                   and ball["start"] + 500 <= o.x < ball["end"] - 500
                   and o.y > 180]
        self.assertGreater(len(ceiling), 10)

    def test_safely_sparse_gameplay(self):
        hazards = sorted(o.x for o in self.level.objects if o.id in HAZARD_IDS)
        self.assertGreaterEqual(hazards[0], 700)
        self.assertLessEqual(len(hazards), 8)
        self.assertTrue(all(b-a >= 600 for a, b in zip(hazards, hazards[1:])))
        # No decorative native cloud creates solid collision geometry.
        self.assertFalse(any(o.id == BLOCK and o.color_channel in (7, 9, 11)
                             for o in self.level.objects))

    def test_moon_stars_and_arcs(self):
        ids = [o.id for o in self.level.objects]
        self.assertTrue(any(oid in CLOUD_IDS for oid in ids))
        self.assertIn(MOON_DISC, ids)
        self.assertIn(GLOW, ids)
        self.assertIn(MOVE_TRIGGER, ids)
        self.assertIn(PULSE_TRIGGER, ids)
        self.assertGreater(sum(oid in MOONLIT_DECOR_IDS for oid in ids), 400)

    def test_ship_requires_steering_but_has_wide_reaction_windows(self):
        ship = self.level.sections[1]
        start, end = ship["start"], ship["end"]
        positions = range(int(start + 880), int(end - 850), 60)
        samples = [ship_corridor_bounds(start, end, x) for x in positions]
        centers = [center for _, _, center in samples]
        # Flying at a constant altitude will hit at least one bank.
        self.assertGreater(max(centers) - min(centers), 165)
        for fixed_y in range(60, 331, 15):
            self.assertTrue(
                any(fixed_y < low + 15 or fixed_y > high - 15
                    for low, high, _ in samples),
                f"Ship can stay at y={fixed_y} for the entire slalom",
            )
        # No expert-level pinches or instantaneous 90-degree turns.
        self.assertTrue(all(top - bottom >= 180
                            for bottom, top, _ in samples))
        self.assertLess(max(abs(b - a)
                            for a, b in zip(centers, centers[1:])), 28)

    def test_ship_generated_blocks_follow_profile(self):
        ship = self.level.sections[1]
        start, end = ship["start"], ship["end"]
        walls = [o for o in self.level.objects
                 if o.id == BLOCK and start + 400 < o.x < end - 400]
        self.assertGreater(len(walls), 65)
        for x in range(int(start + 900), int(end - 700), 120):
            low, high, center = ship_corridor_bounds(start, end, x)
            self.assertGreaterEqual(high - low, 180)
            # A generous free corridor should surround the planned route.
            self.assertGreater(center - low, 68)
            self.assertGreater(high - center, 68)

    def test_new_scenery_density(self):
        decorative = [o for o in self.level.objects
                      if o.id in MOONLIT_DECOR_IDS]
        self.assertGreater(len(decorative), 1400)
        self.assertGreater(len(self.level.objects), 1800)
        self.assertEqual(sum(o.id in HAZARD_IDS for o in self.level.objects), 8)

    def test_group_targets_exist(self):
        groups = set()
        for obj in self.level.objects:
            val = obj.get(57)
            if val is not None:
                groups.update(int(group) for group in str(val).split("."))
        for obj in self.level.objects:
            if obj.id == MOVE_TRIGGER:
                self.assertIn(int(obj.get(51)), groups)

    def test_determinism_and_structure(self):
        self.assertEqual(self.level.to_level_string(),
                         generate(spec_from_preset("moonlit-cloud-kingdom")).to_level_string())
        result = validate(self.level)
        self.assertFalse(result.errors, result.summary())

    def test_gdlvl_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "demo.gdlvl"
            save_gdlvl(p, self.level)
            decoded = load_gdlvl(p)
            self.assertEqual(decoded.to_level_string(), self.level.to_level_string())

    def test_cli_export_and_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["generate", "--preset", "moonlit-cloud-kingdom",
                                       "--out", tmp, "--no-preview"]), 0)
            self.assertTrue((Path(tmp) / "moonlit_cloud_kingdom.gdlvl").exists())
            self.assertTrue((Path(tmp) / "moonlit_cloud_kingdom.json").exists())


if __name__ == "__main__":
    unittest.main()
