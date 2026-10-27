import unittest

from webquiz.textmatch import best_match, normalize, score


class TextMatchTest(unittest.TestCase):
    def test_leading_label_is_stripped_only_with_whitespace(self):
        self.assertEqual(normalize("A 农村改革"), "农村改革")
        self.assertEqual(normalize("A\n农村改革"), "农村改革")
        # B+ must keep its B
        self.assertEqual(normalize("B+"), "B+")
        self.assertNotEqual(normalize("B+"), "+")

    def test_exact_beats_substring(self):
        candidates = ["软件工程专业导论", "软件工程", "软件建模与分析"]
        idx, _ = best_match("软件工程", candidates)
        self.assertEqual(idx, 1)

    def test_substring_still_matches(self):
        idx, _ = best_match("农村改革", ["A 农村改革", "B 城市改革"])
        self.assertEqual(idx, 0)

    def test_radical_normalisation(self):
        self.assertEqual(normalize("人⺠⺠主专政"), normalize("人民民主专政"))

    def test_unknown_glyph_is_ignored(self):
        self.assertGreater(score("因为改革往往牵一发而动全身",
                                 "因为改革往往牵▀发而动全身"), 0.8)

    def test_low_similarity_rejected(self):
        idx, _ = best_match("完全不同的选项", ["A", "B"])
        self.assertIsNone(idx)


if __name__ == "__main__":
    unittest.main()
