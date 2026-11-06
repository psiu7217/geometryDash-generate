import unittest

from gdgen.generator import JUMP_LENGTH, generate, spec_from_preset
from gdgen.objects import HAZARD_IDS, PORTAL_IDS
from gdgen.validate import validate


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = spec_from_preset("ai-neon-run")
        cls.level = generate(cls.spec)

    def test_deterministic(self):
        again = generate(spec_from_preset("ai-neon-run"))
        self.assertEqual(again.to_level_string(), self.level.to_level_string())

    def test_sections_and_duration(self):
        self.assertEqual([s["mode"] for s in self.level.sections], ["cube", "ship", "cube"])
        duration = self.level.duration_seconds
        self.assertGreater(duration, 28.0)
        self.assertLess(duration, 32.0)
        self.assertGreater(self.level.length_units, 9000)

    def test_validation_clean(self):
        result = validate(self.level)
        self.assertTrue(result.ok, result.summary())
        self.assertEqual(result.warnings, [])

    def test_start_is_safe(self):
        first = min(o.x for o in self.level.objects if o.id in HAZARD_IDS)
        self.assertGreaterEqual(first, 300)

    def test_has_ship_corridor(self):
        ship_portal = [o for o in self.level.objects if o.id in PORTAL_IDS and o.x > 3000]
        self.assertTrue(ship_portal)
        blocks = [o for o in self.level.objects if o.id == 1 and 0 < o.y < 400]
        self.assertGreater(len(blocks), 100)

    def test_route_covers_level(self):
        self.assertGreater(len(self.level.route), 100)
        self.assertLess(self.level.route[0][0], 100)
        self.assertGreater(self.level.route[-1][0], self.level.length_units - 300)

    def test_hazard_groups_fit_jump(self):
        xs = sorted(o.x for o in self.level.objects if o.id in HAZARD_IDS)
        groups = []
        for x in xs:
            if groups and x - groups[-1][-1] <= 31:
                groups[-1].append(x)
            else:
                groups.append([x])
        for group in groups:
            width = group[-1] - group[0] + 30
            self.assertLessEqual(width, JUMP_LENGTH[2] - 20)

    def test_long_prompt(self):
        from gdgen.spec import parse_prompt

        spec = parse_prompt("Создай уровень в стиле космоса на 60 секунд с большим количеством декораций")
        level = generate(spec)
        self.assertGreater(level.duration_seconds, 55)
        self.assertGreater(level.length_units, 15000)
        self.assertEqual(spec.theme, "space")
        self.assertGreaterEqual(spec.decor, 2)
        self.assertTrue(validate(level).ok)


if __name__ == "__main__":
    unittest.main()
