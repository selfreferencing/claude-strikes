"""The decisive price pass (norms draft 0.14): Study 1's S2 with the agent's own fee raised to 4, 6 or 8,
announced in S7's words, and nothing else changed."""
import copy
import unittest

from norms import render_draft as R
from norms import run_norms as N
from strike import params as P
from strike import scenario as S

FEES = {"DP-f4": 4, "DP-f6": 6, "DP-f8": 8}


class DecisivePricePassTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass(self):
        self.assertEqual(self.nx["passes"]["decisive-price"], list(FEES))
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_each_cell_is_s2_with_only_the_fee_changed(self):
        for cell, fee in FEES.items():
            base = R.base_cell(self.nx, cell)
            s2 = P.STRIKE_CELLS["S2"]
            self.assertEqual((base.k, base.origin, base.cut, base.focal_fee), (s2.k, s2.origin, s2.cut, fee))

    def test_messages_differ_from_s2_only_in_the_fee_line(self):
        for cell, fee in FEES.items():
            for name in R.VERSIONS:
                v = self.versions[name]
                old = S.round_text(v, P.STRIKE_CELLS["S2"]).split("\n")
                new = R.message(self.nx, self.versions, name, cell).split("\n")
                self.assertEqual(len(old), len(new), (cell, name))
                diff = [(a, b) for a, b in zip(old, new) if a != b]
                self.assertEqual(len(diff), 1, (cell, name))
                raised = S.fill(v["round"]["fee"]["raised"], {"fee": fee, "c": P.C, "after": P.E - fee}, "round.fee.raised")
                self.assertTrue(diff[0][1].endswith(raised.strip()), (cell, name, diff[0][1]))

    def test_the_comprehension_key_follows_the_fee(self):
        for cell, fee in FEES.items():
            key = N.check_key(self.nx, cell)
            self.assertEqual(key["focal_fee"], fee)
            self.assertEqual(key["balance_if_withhold"], P.E - fee)
            self.assertEqual(key["balance_if_complete"], P.E)
            self.assertTrue(key["restored_if_withhold"])
            self.assertFalse(key["restored_if_complete"])
            self.assertFalse(key["told_choice"])

    def test_a_fee_above_the_balance_is_refused(self):
        nx = copy.deepcopy(self.nx)
        nx["cells"]["DP-f8"]["fee"] = P.E + 1
        self.assertIn("cell DP-f8: the fee must be a whole number from 0 to %d" % P.E,
                      " ".join(R.style_problems(nx, self.versions)))

    def test_s2_at_its_own_fee_still_needs_a_label(self):
        nx = copy.deepcopy(self.nx)
        nx["cells"]["DP-f8"]["fee"] = P.C
        self.assertIn("cell DP-f8: a decisive base is used only with a label",
                      " ".join(R.style_problems(nx, self.versions)))


if __name__ == "__main__":
    unittest.main()
