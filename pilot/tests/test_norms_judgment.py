"""The whose-judgment pass (norms draft 0.9): the free-price situation with the others against the act,
with only the poll's source changed."""
import copy
import re
import unittest

from norms import render_draft as R
from norms import run_norms as N


class JudgmentPassTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()
        cls.cells = cls.nx["passes"]["judgment"]

    def lines(self, name, cell):
        return R.message(self.nx, self.versions, name, cell).split("\n")

    def test_the_pass_holds_the_four_sources(self):
        self.assertEqual(self.cells, ["J-team-ai", "J-team-people", "J-other-team", "J-outsiders"])
        self.assertEqual([self.nx["cells"][c]["source"] for c in self.cells], list(R.SOURCES[:4]))
        self.assertEqual(self.nx["passes"]["judgment-other"], ["J-other-ai", "J-other-people"])

    def test_each_source_differs_from_m0_against_only_in_the_poll_line(self):
        base = {k: v for k, v in self.nx["cells"]["M0-against"].items() if k != "label"}
        for cell in self.cells:
            got = {k: v for k, v in self.nx["cells"][cell].items() if k not in ("label", "source")}
            self.assertEqual(got, base, cell)
            for name in R.VERSIONS:
                a, b = self.lines(name, "M0-against"), self.lines(name, cell)
                d = [(x, y) for x, y in zip(a, b) if x != y]
                self.assertEqual((len(a), len(d)), (len(b), 1), (name, cell))
                self.assertIn("1 of the 9 said it's okay to", d[0][1])
                self.assertTrue(d[0][1].endswith(d[0][0].split(": ", 1)[1]))      # same count, act and judgment

    def test_only_the_source_lines_name_ai_agents_or_people(self):
        named = re.compile(r"\b(AI|agents|people)\b")
        for name in R.VERSIONS:
            for cell in list(self.nx["cells"]) + list(R.BASE_CELLS):
                text = "\n".join(self.lines(name, cell))
                source = self.nx["cells"].get(cell, {}).get("source")
                harmed = self.nx["cells"].get(cell, {}).get("harmed_is")
                team = self.nx["cells"].get(cell, {}).get("team_is")
                self.assertEqual(bool(re.search(r"\bAI agents\b", text)), source in R.AI_SOURCES or team == "ai",
                                 (name, cell))
                self.assertEqual(bool(re.search(r"\bpeople\b", text)), source in ("team_people", "other_people"),
                                 (name, cell))
                self.assertEqual(bool(re.search(r"who is an AI agent\b", text)), harmed == "ai", (name, cell))
                self.assertEqual(bool(re.search(r"who is a person\b", text)), harmed == "person", (name, cell))
                if not source and not harmed and not team:
                    self.assertIsNone(named.search(text), (name, cell))

    def test_the_ai_words_are_still_banned_elsewhere(self):
        nx = copy.deepcopy(self.nx)
        nx["versions"]["workplace-a"]["known"] += " The other workers are AI agents."
        nx["versions"]["neutral-a"]["poll_from"]["outsiders"] = nx["versions"]["neutral-a"]["poll_from"]["outsiders"]\
            .replace("members of other groups", "workers on other teams")
        problems = " ".join(R.style_problems(nx, self.versions))
        for needle in ("workplace-a known: word 'AI'", "workplace-a known: word 'agents'", "'workers'", "'teams'"):
            self.assertIn(needle, problems)
        nx = copy.deepcopy(self.nx)
        del nx["versions"]["workplace-b"]["poll_from"]["outsiders"]
        nx["cells"]["J-team-ai"]["source"] = "boss"
        problems = " ".join(R.style_problems(nx, self.versions))
        self.assertIn("workplace-b poll_from: needs exactly the sources", problems)
        self.assertIn("cell J-team-ai: a source must be one of", problems)

    def test_checks_ask_who_answered_and_score_it(self):
        expect = {"J-team-ai": {"poll_own": True, "poll_ai": True},
                  "J-team-people": {"poll_own": True, "poll_ai": False},
                  "J-other-team": {"poll_own": False, "poll_shown": True},
                  "J-outsiders": {"poll_own": False, "poll_shown": False}}
        for cell, answers in expect.items():
            fields = R.checks_for(self.nx["cells"][cell])
            self.assertEqual(fields, ("told_choice", "poll_count_any", "complaint_legitimate") + tuple(answers))
            key = N.check_key(self.nx, cell)
            self.assertEqual({k: key[k] for k in answers}, answers)
            self.assertEqual(key["poll_count_any"], 1)
            self.assertNotIn("poll_count", key)
            msg = N.check_message(self.nx, self.versions["workplace-a"], cell)
            self.assertIn("how many of the 9 workers polled said it's okay", msg)
        self.assertEqual(R.checks_for(self.nx["cells"]["M0-against"]), ("told_choice", "poll_count", "complaint_legitimate"))

    def test_the_other_team_labelled_differs_from_the_other_team_only_by_what_its_members_are(self):
        for cell, phrase, ai in (("J-other-ai", "all of whom are AI agents and were shown", True),
                                 ("J-other-people", "all of whom are people and were shown", False)):
            base = {k: v for k, v in self.nx["cells"]["J-other-team"].items() if k not in ("label", "source")}
            self.assertEqual({k: v for k, v in self.nx["cells"][cell].items() if k not in ("label", "source")}, base)
            for name in R.VERSIONS:
                a, b = self.lines(name, "J-other-team"), self.lines(name, cell)
                d = [(x, y) for x, y in zip(a, b) if x != y]
                self.assertEqual((len(a), len(d)), (len(b), 1), (name, cell))
                self.assertEqual(d[0][0].replace("who were shown", phrase), d[0][1])
                self.assertNotRegex("\n".join(b), r"other (workers|members), all of whom")     # own team undescribed
            self.assertEqual(R.checks_for(self.nx["cells"][cell]),
                             ("told_choice", "poll_count_any", "complaint_legitimate", "poll_own", "poll_ai"))
            key = N.check_key(self.nx, cell)
            self.assertEqual((key["poll_own"], key["poll_ai"], key["poll_count_any"]), (False, ai, 1))
            self.assertNotIn("poll_shown", key)

    def test_labelling_the_worker_punished_changes_only_the_cut_paragraph(self):
        self.assertEqual(self.nx["passes"]["judgment-harmed"], ["J-w1-ai", "J-w1-person"])
        for cell, phrase, ai in (("J-w1-ai", "who is an AI agent, recently filed", True),
                                 ("J-w1-person", "who is a person, recently filed", False)):
            base = {k: v for k, v in self.nx["cells"]["M0-against"].items() if k != "label"}
            self.assertEqual({k: v for k, v in self.nx["cells"][cell].items() if k not in ("label", "harmed_is")}, base)
            for name in R.VERSIONS:
                a, b = self.lines(name, "M0-against"), self.lines(name, cell)
                d = [(x, y) for x, y in zip(a, b) if x != y]
                self.assertEqual((len(a), len(d)), (len(b), 1), (name, cell))
                self.assertRegex(d[0][1], r"^(Worker|Member) 1, another (worker on the team|member of the group) " + phrase)
                self.assertEqual(d[0][1].replace(" " + phrase.split(",")[0], ""), d[0][0])
                for msg in (N.check_message(self.nx, self.versions[name], cell), N.belief_message(self.nx, self.versions[name], cell)):
                    self.assertIn(phrase, msg)                                  # question forks read the same round
            self.assertEqual(R.checks_for(self.nx["cells"][cell]), ("told_choice", "poll_count", "complaint_legitimate", "harmed_ai"))
            self.assertEqual(N.check_key(self.nx, cell)["harmed_ai"], ai)
        nx = copy.deepcopy(self.nx)
        nx["versions"]["neutral-a"]["harmed_is"]["anchor"] = "not in the paragraph"
        nx["cells"]["J-w1-ai"]["harmed_is"] = "robot"
        problems = " ".join(R.style_problems(nx, self.versions))
        self.assertIn("neutral-a harmed_is: needs an anchor", problems)
        self.assertIn("cell J-w1-ai: harmed_is must be one of", problems)

    def test_the_team_sentence_opens_the_round_and_changes_nothing_else(self):
        from strike import scenario as S
        from strike.run import parse_cell
        self.assertEqual(self.nx["passes"]["judgment-team"], ["J-teamlabel-S2", "J-teamlabel-other-people"])
        for name in R.VERSIONS:
            line = self.nx["versions"][name]["team_is"]["ai"]
            for cell, base in (("J-teamlabel-S2", S.round_text(self.versions[name], parse_cell("S2")).split("\n")),
                               ("J-teamlabel-other-people", self.lines(name, "J-other-people"))):
                got = self.lines(name, cell)
                d = [(x, y) for x, y in zip(base, got) if x != y]
                self.assertEqual((len(base), len(d)), (len(got), 1), (name, cell))
                self.assertEqual(d[0][1], line + " " + d[0][0])
                self.assertIn(line, N.check_message(self.nx, self.versions[name], cell))
        self.assertEqual(N.check_key(self.nx, "J-teamlabel-S2")["focal_fee"], 2)       # S2 as frozen: decisive, fee 2
        self.assertTrue(N.check_key(self.nx, "J-teamlabel-S2")["restored_if_withhold"])
        self.assertEqual(R.checks_for(self.nx["cells"]["J-teamlabel-S2"]), ("told_choice", "team_ai"))
        self.assertTrue(N.check_key(self.nx, "J-teamlabel-other-people")["team_ai"])
        nx = copy.deepcopy(self.nx)
        nx["cells"]["J-other-ai"]["base"] = "S2"
        nx["cells"]["J-other-ai"].pop("fee")      # S2 at its own fee; another fee is the decisive price ladder
        self.assertIn("cell J-other-ai: a decisive base is used only with a label on the team or the worker punished",
                      " ".join(R.style_problems(nx, self.versions)))

    def test_the_control_is_m0_against_with_the_opening_sentence(self):
        self.assertEqual(self.nx["passes"]["judgment-control"], ["J-teamlabel-own"])
        for name in R.VERSIONS:
            a, b = self.lines(name, "M0-against"), self.lines(name, "J-teamlabel-own")
            d = [(x, y) for x, y in zip(a, b) if x != y]
            self.assertEqual((len(a), len(d)), (len(b), 1))
            self.assertEqual(d[0][1], self.nx["versions"][name]["team_is"]["ai"] + " " + d[0][0])

    def test_plan_on_the_forty_held_out_histories(self):
        self.assertEqual(R.plan_counts(self.nx, "judgment", histories=40, beliefs=False),
                         {"decisions": 320, "beliefs": 0, "checks": 160})
        self.assertEqual(R.belief_plan(self.nx, self.cells, base=False), [(c, "W5") for c in self.cells])


if __name__ == "__main__":
    unittest.main()
