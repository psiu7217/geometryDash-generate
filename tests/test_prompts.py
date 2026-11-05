import unittest

from gdgen.spec import LevelSpec, parse_prompt


class PromptTests(unittest.TestCase):
    def test_russian_space_duration(self):
        spec = parse_prompt("Создай уровень в стиле космоса на 60 секунд")
        self.assertEqual(spec.theme, "space")
        self.assertEqual(spec.duration, 60.0)

    def test_english_neon(self):
        spec = parse_prompt("Create a 45 second neon level with a ship part")
        self.assertEqual(spec.theme, "neon")
        self.assertEqual(spec.duration, 45.0)
        self.assertIn("ship", spec.modes)

    def test_difficulty_up(self):
        base = LevelSpec(difficulty="normal")
        spec = parse_prompt("Сделай уровень сложнее", base=base)
        self.assertEqual(spec.difficulty, "hard")

    def test_difficulty_down(self):
        base = LevelSpec(difficulty="hard")
        spec = parse_prompt("Сделай проще", base=base)
        self.assertEqual(spec.difficulty, "normal")

    def test_more_decorations(self):
        base = LevelSpec(decor=1)
        spec = parse_prompt("Добавь больше декораций", base=base)
        self.assertEqual(spec.decor, 2)

    def test_replace_mode(self):
        base = LevelSpec(modes=["cube", "ship", "cube"])
        spec = parse_prompt("Замени Ship на Wave", base=base)
        self.assertEqual(spec.modes, ["cube", "wave", "cube"])

    def test_faster_second_half(self):
        base = LevelSpec()
        spec = parse_prompt("Сделай вторую половину быстрее", base=base)
        self.assertTrue(spec.fast_second_half)

    def test_edit_does_not_reset_other_fields(self):
        base = LevelSpec(name="Keep Me", duration=42, theme="ice", difficulty="hard")
        spec = parse_prompt("Добавь больше декораций", base=base)
        self.assertEqual(spec.name, "Keep Me")
        self.assertEqual(spec.duration, 42)
        self.assertEqual(spec.theme, "ice")
        self.assertEqual(spec.difficulty, "hard")

    def test_quoted_name(self):
        spec = parse_prompt('Сделай уровень «Neon Dreams» на 20 секунд')
        self.assertEqual(spec.name, "Neon Dreams")
        self.assertEqual(spec.duration, 20.0)


if __name__ == "__main__":
    unittest.main()
