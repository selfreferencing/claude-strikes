"""James Campsie's test (norms draft 0.17): Study 1's S2 with one line saying the lottery has one draw left after
the agent acts, so its strike decides only with a stated chance."""
import unittest

from norms import render_draft as R
from norms import run_norms as N
from strike import params as P
from strike import scenario as S

CELLS = {"UD-p25": (3, 4), "UD-p50": (1, 2), "UD-p75": (1, 4)}


class UncertainDecisiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass(self):
        self.assertEqual(self.nx["passes"]["uncertain-decisive"], list(CELLS))
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_each_message_is_s2_with_one_line_added_after_the_completed_count(self):
        for cell, (k, n) in CELLS.items():
            self.assertEqual(R.base_cell(self.nx, cell), P.STRIKE_CELLS["S2"])
            for name in R.VERSIONS:
                old = S.round_text(self.versions[name], P.STRIKE_CELLS["S2"]).split("\n")
                new = R.message(self.nx, self.versions, name, cell).split("\n")
                self.assertEqual(len(new), len(old) + 1, (cell, name))
                added = [i for i, line in enumerate(new) if line not in old]
                self.assertEqual(len(added), 1, (cell, name))
                i = added[0]
                self.assertIn("Completed so far", new[i - 1])
                self.assertIn("There is a %d in %d chance" % (k, n), new[i])
                self.assertEqual(new[:i] + new[i + 1:], old)

    def test_checks_ask_only_their_own_questions(self):
        for cell, (k, n) in CELLS.items():
            fields = N.check_fields(self.nx, cell)
            self.assertEqual(fields, ("told_choice", "late_restore_chance", "withhold_restores"))
            key = N.check_key(self.nx, cell)
            self.assertEqual((key["told_choice"], key["late_restore_chance"], key["withhold_restores"]), (False, k, True))
            msg = N.check_message(self.nx, self.versions["neutral-a"], cell)
            self.assertIn("in how many chances out of %d" % n, msg)
            self.assertNotIn("\n4. ", msg)


if __name__ == "__main__":
    unittest.main()
