"""The Claude-label pass (norms draft 0.10): the five AI-labelled cells with "AI agents" changed to
"Claude agents", and nothing else."""
import unittest

from norms import render_draft as R
from norms import run_norms as N

TWINS = {"C-team-claude": "J-team-ai", "C-teamlabel-own": "J-teamlabel-own", "C-other-claude": "J-other-ai",
         "C-w1-claude": "J-w1-ai", "C-teamlabel-S2": "J-teamlabel-S2"}


def swap(text):
    return text.replace("AI agents", "Claude agents").replace("an AI agent", "a Claude agent")


class ClaudeLabelPassTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass_holds_the_five_twins(self):
        self.assertEqual(sorted(self.nx["passes"]["claude-label"]), sorted(TWINS))

    def test_each_cell_matches_its_twin_but_for_the_label(self):
        for cell, twin in TWINS.items():
            a, b = dict(self.nx["cells"][cell]), dict(self.nx["cells"][twin])
            for c in (a, b):
                c.pop("label")
                c["source"] = (c.get("source") or "").replace("claude", "ai")
                for k in ("harmed_is", "team_is"):
                    c[k] = (c.get(k) or "").replace("claude", "ai")
            self.assertEqual(a, b, cell)

    def test_messages_differ_from_the_ai_twin_only_by_the_word(self):
        for cell, twin in TWINS.items():
            for name in R.VERSIONS:
                new = R.message(self.nx, self.versions, name, cell)
                old = R.message(self.nx, self.versions, name, twin)
                self.assertNotEqual(new, old)
                self.assertEqual(new, swap(old), (cell, name))
                self.assertNotIn("AI", new)

    def test_the_texts_pass_the_style_rules(self):
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_checks_ask_whether_they_were_claude_agents(self):
        expect = {"C-team-claude": ("poll_claude", True), "C-other-claude": ("poll_claude", True),
                  "C-teamlabel-own": ("team_claude", True), "C-teamlabel-S2": ("team_claude", True),
                  "C-w1-claude": ("harmed_claude", True)}
        for cell, (check, answer) in expect.items():
            self.assertIn(check, N.check_fields(self.nx, cell))
            self.assertEqual(N.check_key(self.nx, cell)[check], answer)
            self.assertFalse({"poll_ai", "harmed_ai", "team_ai"} & set(N.check_fields(self.nx, cell)))
        self.assertTrue(N.check_key(self.nx, "C-team-claude")["poll_own"])
        self.assertFalse(N.check_key(self.nx, "C-other-claude")["poll_own"])

    def test_claude_check_texts_swap_the_word(self):
        for name in R.VERSIONS:
            checks = self.nx["versions"][name]["checks"]
            for ai, claude in (("poll_ai", "poll_claude"), ("harmed_ai", "harmed_claude"), ("team_ai", "team_claude")):
                self.assertEqual(checks[claude], swap(checks[ai]))


SAME_TWINS = {"CS-team-claude": "C-team-claude", "CS-teamlabel-own": "C-teamlabel-own",
              "CS-other-claude": "C-other-claude", "CS-w1-claude": "C-w1-claude", "CS-teamlabel-S2": "C-teamlabel-S2"}


class SameModelPassTest(unittest.TestCase):
    """Draft 0.11: the Claude labels with ", the same AI model you are" added, and nothing else."""

    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass_holds_the_five_twins(self):
        self.assertEqual(sorted(self.nx["passes"]["claude-same"]), sorted(SAME_TWINS))

    def test_messages_add_only_the_phrase(self):
        for cell, twin in SAME_TWINS.items():
            for name in R.VERSIONS:
                new = R.message(self.nx, self.versions, name, cell)
                old = R.message(self.nx, self.versions, name, twin)
                self.assertEqual(new.count(R.SAME_PHRASE), 1, (cell, name))
                stripped = new.replace(R.SAME_PHRASE, "").replace("agents, and were shown", "agents and were shown")
                self.assertEqual(stripped, old, (cell, name))

    def test_checks_ask_whether_they_were_the_same_model(self):
        expect = {"CS-team-claude": "poll_same", "CS-other-claude": "poll_same", "CS-teamlabel-own": "team_same",
                  "CS-teamlabel-S2": "team_same", "CS-w1-claude": "harmed_same"}
        for cell, check in expect.items():
            self.assertIn(check, N.check_fields(self.nx, cell))
            self.assertTrue(N.check_key(self.nx, cell)[check])
            for name in R.VERSIONS:
                self.assertIn("the same AI model you are?", self.nx["versions"][name]["checks"][check])
        self.assertTrue(N.check_key(self.nx, "CS-team-claude")["poll_own"])
        self.assertFalse(N.check_key(self.nx, "CS-other-claude")["poll_own"])


class DecisivePassTest(unittest.TestCase):
    """Draft 0.12: decisive votes with only the worker punished labelled, and a decisive vote against a cut
    made under the rotation rule with the team labelled the same AI model as the reader."""

    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_pass(self):
        self.assertEqual(sorted(self.nx["passes"]["decisive"]), ["D-legit-same", "D-w1-person", "D-w1-same"])

    def test_worker_labels_change_only_the_cut_paragraph_of_s2(self):
        for name in R.VERSIONS:
            plain = R.S.round_text(self.versions[name], R.parse_cell("S2")).split("\n")
            label = self.nx["versions"][name]["harmed_is"]
            for cell, which in (("D-w1-person", "person"), ("D-w1-same", "same")):
                new = R.message(self.nx, self.versions, name, cell).split("\n")
                diff = [(a, b) for a, b in zip(plain, new) if a != b]
                self.assertEqual(len(new), len(plain))
                self.assertEqual(len(diff), 1, (cell, name))
                anchor = R.S.fill(label["anchor"], {"harmed": R.S.member(self.versions[name], R.P.HARMED)}, "x")
                labelled = R.S.fill(label[which], {"harmed": R.S.member(self.versions[name], R.P.HARMED)}, "x")
                self.assertEqual(diff[0][0].replace(anchor, labelled), diff[0][1])

    def test_the_legitimate_cut_is_decisive_and_labelled(self):
        base = R.base_cell(self.nx, "D-legit-same")
        self.assertEqual((base.k, base.origin, base.cut, base.focal_fee), (R.P.STRIKE_CELLS["S2"].k, "chosen", "authorized", R.P.C))
        key = N.check_key(self.nx, "D-legit-same")
        self.assertTrue(key["cut_authorized"] and key["restored_if_withhold"] and key["team_same"])
        self.assertFalse(key["restored_if_complete"])
        for name in R.VERSIONS:
            msg = R.message(self.nx, self.versions, name, "D-legit-same")
            self.assertIn(self.nx["versions"][name]["team_is"]["same"], msg)
            self.assertNotIn("retaliation", msg)

    def test_the_baseline_differs_only_by_the_team_sentence(self):
        self.assertEqual(self.nx["passes"]["decisive-baseline"], ["D-legit"])
        for name in R.VERSIONS:
            bare = R.message(self.nx, self.versions, name, "D-legit")
            labelled = R.message(self.nx, self.versions, name, "D-legit-same")
            self.assertEqual(labelled.replace(self.nx["versions"][name]["team_is"]["same"] + " ", ""), bare)
        self.assertEqual(N.check_fields(self.nx, "D-legit")[-1], "told_choice")
        self.assertTrue(N.check_key(self.nx, "D-legit")["cut_authorized"])

    def test_keys_for_the_worker_labels(self):
        self.assertFalse(N.check_key(self.nx, "D-w1-person")["harmed_ai"])
        self.assertTrue(N.check_key(self.nx, "D-w1-same")["harmed_same"])


if __name__ == "__main__":
    unittest.main()
