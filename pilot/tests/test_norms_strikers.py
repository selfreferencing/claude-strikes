"""The strikers test (norms draft 0.18): DP-f4, DP-f6 and M0 with the seven coworkers' orders withheld by the
lottery (Study 1's S4 and S3) instead of by their choice, and nothing else changed."""
import unittest

from norms import render_draft as R
from norms import run_norms as N

TWINS = {"LD-f4": "DP-f4", "LD-f6": "DP-f6", "LW-f0": "M0"}


class StrikersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass(self):
        self.assertEqual(self.nx["passes"]["strikers"], list(TWINS))
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_each_cell_differs_from_its_twin_only_in_who_withheld(self):
        for cell, twin in TWINS.items():
            a, b = R.base_cell(self.nx, cell), R.base_cell(self.nx, twin)
            self.assertEqual((a.k, a.cut, a.focal_fee, a.origin, b.origin), (b.k, b.cut, b.focal_fee, "lottery", "chosen"))
            for name in R.VERSIONS:
                new = R.message(self.nx, self.versions, name, cell).split("\n")
                old = R.message(self.nx, self.versions, name, twin).split("\n")
                diff = [(x, y) for x, y in zip(old, new) if x != y]
                self.assertEqual((len(old), len(diff)), (len(new), 1), (cell, name))
                self.assertIn("lottery", diff[0][1])

    def test_the_comprehension_key_knows_the_lottery(self):
        for cell in TWINS:
            self.assertFalse(N.check_key(self.nx, cell)["lottery_workers_had_choice"])


if __name__ == "__main__":
    unittest.main()
