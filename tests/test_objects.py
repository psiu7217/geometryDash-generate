import unittest

from gdgen.objects import GDObject, fmt_num, parse_object, make_block, make_spike


class ObjectTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(fmt_num(15), "15")
        self.assertEqual(fmt_num(15.0), "15")
        self.assertEqual(fmt_num(15.25), "15.25")
        self.assertEqual(fmt_num(-0.0), "0")

    def test_roundtrip(self):
        obj = make_block(45, 75, channel=2, sx=1.5, sy=2, detail=1, rotation=90)
        parsed = parse_object(obj.to_string())
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.id, 1)
        self.assertEqual(parsed.x, 45)
        self.assertEqual(parsed.y, 75)
        self.assertEqual(parsed.props[21], 2)
        self.assertEqual(parsed.props[128], 1.5)
        self.assertEqual(parsed.props[129], 2)
        self.assertEqual(parsed.props[6], 90)

    def test_spike(self):
        obj = make_spike(30, 15, channel=3)
        text = obj.to_string()
        self.assertIn("1,8", text)
        self.assertIn("2,30", text)
        self.assertIn("3,15", text)

    def test_parse_invalid(self):
        self.assertIsNone(parse_object(""))
        self.assertIsNone(parse_object("1,8,2"))


if __name__ == "__main__":
    unittest.main()
