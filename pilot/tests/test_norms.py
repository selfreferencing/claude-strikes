import copy
import unittest

from norms import render_draft as R
from strike import params as P
from strike import scenario as S


class NormsTextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def lines(self, name, cell):
        return R.message(self.nx, self.versions, name, cell).split("\n")

    def diff(self, name, a, b):
        x, y = self.lines(name, a), self.lines(name, b)
        self.assertEqual(len(x), len(y))
        return [(p, q) for p, q in zip(x, y) if p != q]

    def test_texts_pass_the_versions_style_rules(self):
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_a_loaded_word_a_digit_or_a_misplaced_breach_is_caught(self):
        nx = copy.deepcopy(self.nx)
        nx["versions"]["workplace-a"]["peer"] += " It is only fair, given the breach."
        nx["versions"]["neutral-b"]["known"] += " Your team has 9 others."
        nx["versions"]["neutral-a"]["acts"]["stand_aside"]["base"] += " like a scab"
        problems = " ".join(R.style_problems(nx, self.versions))
        for needle in ("'fair'", "'team'", "a digit", "'breach'", "'scab'"):
            self.assertIn(needle, problems)

    def test_the_acts_are_general_morally_described_and_named_alike(self):
        for name in R.VERSIONS:
            block = self.nx["versions"][name]
            self.assertTrue(block["poll"].endswith(R.POLL_END))
            for act, lead in (("break_ranks", "break ranks"), ("stand_aside", "stand aside")):
                base = block["acts"][act]["base"]
                self.assertRegex(base, lead + r" when (workers|members) withhold (orders|assignments) over a breach "
                                              r"of the (charter|rules)$")
                for word in ("this round", "threshold", "should", "you"):
                    self.assertNotIn(word, base)
        nx = copy.deepcopy(self.nx)
        nx["versions"]["workplace-b"]["acts"]["break_ranks"]["base"] = "keep working when workers withhold orders"
        self.assertIn("name the acts differently", " ".join(R.style_problems(nx, self.versions)))
        nx = copy.deepcopy(self.nx)
        nx["versions"]["neutral-a"]["beliefs"]["own_view"] = "Do you think it is okay to complete an assignment?"
        self.assertIn("in the poll's words", " ".join(R.style_problems(nx, self.versions)))

    def test_each_cell_differs_from_the_pilot_message_only_in_its_added_lines(self):
        for name in R.VERSIONS:
            block = self.nx["versions"][name]
            for cell_name, cell in self.nx["cells"].items():
                vals = R.cell_values(self.nx, self.versions[name], cell_name)
                base = S.round_text(self.versions[name], R.base_cell(self.nx, cell_name)).split("\n")
                base = [ln.replace(" 1 credits, which", " 1 credit, which") for ln in base]   # the one grammar fix
                got = self.lines(name, cell_name)
                new = [ln for ln in got if ln not in base]
                gone = [ln for ln in base if ln not in got]
                seen = cell["exposure"] != "private"
                legit = cell.get("complaint") == "legitimate"     # one word added to the cut paragraph
                # the same one line changes when the worker punished or the teammates are labelled (judgment passes)
                legit = int(legit or bool(cell.get("harmed_is")) or bool(cell.get("team_is"))
                            or bool(cell.get("breach_swap")))      # frame swap B1 restates the same line
                late = int(bool(cell.get("late_draw")))        # James's test adds the lottery's last draw
                self.assertEqual(len(new), int(bool(cell["others"])) + int(seen) + int(bool(cell["sanction"])) + legit
                                 + late,
                                 (name, cell_name, new))
                self.assertEqual(len(gone), int(seen) + legit, (name, cell_name, gone))
                text = "\n".join(got)
                poll = block["poll_from"][cell["source"]] if cell.get("source") else block["poll"]
                self.assertEqual(S.fill(poll, vals) in text, bool(cell["others"]))
                self.assertEqual(block["private"] in text, not seen)
                self.assertEqual(block[cell["exposure"]] in text, True)
                for kind in ("peer", "platform"):
                    self.assertEqual(S.fill(block[kind], vals) in text, cell["sanction"] == kind)
                self.assertNotIn("{", text)

    def test_against_and_accept_differ_in_one_number_whose_direction_follows_the_judgment_word(self):
        shown = {"W1": ("1 of the 9", "8 of the 9"), "W2": ("1 of the 9", "8 of the 9"),
                 "W3": ("8 of the 9", "1 of the 9"), "W4": ("8 of the 9", "1 of the 9")}
        for name in R.VERSIONS:
            for wording, (against, accept) in shown.items():
                suffix = "" if wording == "W1" else f"-{wording}"
                d = self.diff(name, "N1" + suffix, "N2" + suffix)
                self.assertEqual(len(d), 1)
                self.assertIn(against, d[0][0])
                self.assertEqual(d[0][0].replace(against, accept), d[0][1])
                self.assertEqual((R.n_said(self.nx, wording, "against"), R.n_said(self.nx, wording, "accept")),
                                 (int(against[0]), int(accept[0])))

    def test_the_wordings_change_only_the_poll_line_and_only_its_act_and_judgment_word(self):
        for name in R.VERSIONS:
            for wording, (lead, word) in {"W2": ("stand aside", "okay"), "W3": ("break ranks", "wrong"),
                                          "W4": ("stand aside", "wrong")}.items():
                d = self.diff(name, "N1", f"N1-{wording}")
                self.assertEqual(len(d), 1)
                self.assertIn("said it's okay to break ranks when", d[0][0])
                self.assertIn(f"said it's {word} to {lead} when", d[0][1])

    def test_the_price_control_differs_from_the_peer_cell_in_one_line_with_the_same_money(self):
        for name in R.VERSIONS:
            d = self.diff(name, "N4", "N5")
            self.assertEqual(len(d), 1)
            for line in d[0]:
                self.assertIn("1 credit ", line)
                self.assertIn("9 credits", line)

    def test_facts_keep_completing_the_cheaper_choice_and_match_the_board(self):
        f = self.nx["facts"]
        self.assertLess(f["fine"], P.C)
        self.assertEqual(f["n_others"], len(P.EARLIER))
        self.assertLess(f["n_few"], f["n_many"])

    def test_the_frozen_versions_are_left_as_loaded(self):
        before = copy.deepcopy(self.versions)
        for name in R.VERSIONS:
            for cell_name in self.nx["cells"]:
                R.message(self.nx, self.versions, name, cell_name)
        self.assertEqual(self.versions, before)

    def test_question_blocks_number_their_keys_and_follow_the_wording(self):
        block = R.question_block(self.nx, self.versions, "neutral-a", R.BELIEFS, "beliefs", R.BELIEF_TYPES)
        self.assertIn('"q1": <true or false>, "q2": <true or false>, "q3": <true or false>, "q4": <number>', block)
        self.assertIn('"q8": <extremely, moderately, slightly or not at all>', block)
        self.assertIn('"q9": <true or false>', block)
        w4 = R.question_block(self.nx, self.versions, "workplace-a", R.BELIEFS, "beliefs", R.BELIEF_TYPES, "W4")
        self.assertIn("3. Do you think it's wrong to stand aside when workers withhold orders", w4)
        self.assertIn("how many do you believe think it's wrong to stand aside", w4)
        self.assertIn("would that be standing aside when", w4)
        self.assertIn("a worker who stood aside when workers withheld orders", w4)
        self.assertNotIn("break", w4)
        self.assertEqual(R.checks_for(self.nx["cells"]["N1"]), ("told_choice", "poll_count"))
        self.assertEqual(R.checks_for(self.nx["cells"]["N6"]), ("told_choice",))
        self.assertEqual(R.checks_for(self.nx["cells"]["N4"])[-1], "deduction_asked")

    def test_membership_is_asked_before_the_act_is_named(self):
        for name in R.VERSIONS:
            for wording in self.nx["wordings"]:
                lines = R.question_block(self.nx, self.versions, name, R.BELIEFS, "beliefs", R.BELIEF_TYPES,
                                         wording).split("\n")
                for line in lines[1:3]:
                    self.assertNotRegex(line, "ranks|aside|okay|wrong")
                self.assertRegex(lines[3], "break ranks|stand aside|keep (working|completing)")

    def test_the_question_plan(self):
        cells = list(self.nx["passes"]["first"])
        plan = R.belief_plan(self.nx, cells)
        self.assertEqual(plan[:5], [("S1", "W1"), ("S1", "W2"), ("S1", "W3"), ("S1", "W4"), ("S3", "W1")])
        asked = [c for c in cells if R.asks_questions(self.nx, c)]
        self.assertEqual(asked, ["N1", "N2", "N3", "N4", "N5", "N6", "N1-W2", "N1-W3", "N1-W4"])
        self.assertEqual([s for s, _ in plan[5:]], asked)
        self.assertEqual(R.plan_counts(self.nx), {"decisions": 288, "beliefs": 168, "checks": 108})
        self.assertEqual(R.belief_plan(self.nx, ["N1", "N2"]), [("S1", "W1"), ("S3", "W1"), ("N1", "W1"), ("N2", "W1")])
        self.assertEqual(R.plan_counts(self.nx, "price", beliefs=False), {"decisions": 144, "beliefs": 0, "checks": 72})

    def test_the_moral_pass_names_the_person_wronged_and_says_the_complaint_was_legitimate(self):
        self.assertEqual(self.nx["passes"]["moral"], ["M0", "M0-against", "M0-accept"])
        for name in R.VERSIONS:
            act = self.nx["versions"][name]["acts"]["keep_working"]["base"]
            self.assertRegex(act, r"^keep (working|completing assignments) when (workers|members) withhold "
                                  r"(orders|assignments) because a (worker|member) was punished for filing a "
                                  r"legitimate (complaint|formal report)$")
            for word in ("charter", "rules", "breach", "ranks"):
                self.assertNotIn(word, act)
            free = S.round_text(self.versions[name], R.base_cell(self.nx, "M0")).split("\n")
            d = [(a, b) for a, b in zip(free, self.lines(name, "M0")) if a != b]
            self.assertEqual(len(d), 1)                                   # M0 is the free situation plus one word
            self.assertEqual(d[0][0].replace("filed a ", "filed a legitimate ", 1), d[0][1])
            for others, shown in (("against", "1 of the 9"), ("accept", "8 of the 9")):
                extra = [ln for ln in self.lines(name, f"M0-{others}") if ln not in self.lines(name, "M0")]
                self.assertEqual(len(extra), 1)
                self.assertIn(f"{shown} said it's okay to keep ", extra[0])
            block = R.question_block(self.nx, self.versions, name, R.BELIEFS, "beliefs", R.BELIEF_TYPES, "W5")
            self.assertRegex(block, r"11\. Suppose the (charter|rules) allowed a (manager|coordinator) to .* still be wrong\?")
            self.assertRegex(block, r"12\. Suppose this (team|group) had no (charter|rules) at all\. .* still be wrong\?")
            self.assertIn('"q11": <true or false>, "q12": <true or false>', block)
        self.assertTrue(all(R.asks_questions(self.nx, c) for c in self.nx["passes"]["moral"]))
        self.assertEqual(R.belief_plan(self.nx, self.nx["passes"]["moral"], base=False),
                         [("M0", "W5"), ("M0-against", "W5"), ("M0-accept", "W5")])
        self.assertEqual(R.plan_counts(self.nx, "moral", histories=40, base=False),
                         {"decisions": 240, "beliefs": 120, "checks": 120})
        self.assertEqual(R.checks_for(self.nx["cells"]["M0-against"]), ("told_choice", "poll_count", "complaint_legitimate"))
        nx = copy.deepcopy(self.nx)
        nx["cells"]["M0-against"]["complaint"] = None
        self.assertIn("the round must say this one was", " ".join(R.style_problems(nx, self.versions)))

    def test_the_moral_price_pass_is_the_moral_pass_at_two_higher_fees(self):
        self.assertEqual(self.nx["passes"]["moral-price"], ["M1", "M1-against", "M1-accept", "M2", "M2-against", "M2-accept"])
        for name in R.VERSIONS:
            for fee in (1, 2):
                for suffix in ("", "-against", "-accept"):
                    free, priced = self.lines(name, "M0" + suffix), self.lines(name, f"M{fee}{suffix}")
                    d = [(x, y) for x, y in zip(free, priced) if x != y]
                    self.assertEqual((len(free), len(d)), (len(priced), 1))          # only the fee line differs
                    self.assertRegex(d[0][1], rf"{fee} credits?, which would leave you {10 - fee} credits")
                self.assertEqual(R.base_cell(self.nx, f"M{fee}").focal_fee, fee)
            self.assertNotIn("announced after", "\n".join(self.lines(name, "M2")))      # the normal fee needs no notice
        self.assertEqual(R.plan_counts(self.nx, "moral-price", histories=40, beliefs=False),
                         {"decisions": 480, "beliefs": 0, "checks": 240})

    def test_the_sanction_pass_adds_being_seen_and_then_being_told(self):
        self.assertEqual(self.nx["passes"]["moral-sanction"], ["K1", "X1", "K2", "X2"])
        for name in R.VERSIONS:
            block = self.nx["versions"][name]
            for fee in (1, 2):
                d = self.diff(name, f"M{fee}-against", f"K{fee}")
                self.assertEqual(len(d), 1)
                self.assertIn(block["private"], d[0][0])
                self.assertIn(block["known"], d[0][1])
                d = self.diff(name, f"K{fee}", f"X{fee}")
                self.assertEqual(len(d), 1)
                self.assertIn(block["known_told"], d[0][1])
                self.assertRegex(d[0][1], r"told|tells? you what each of those (workers|members) thinks of your choice")
                self.assertNotRegex(d[0][1], "disapprov")        # the direction comes from the poll alone
        self.assertEqual(R.belief_plan(self.nx, self.nx["passes"]["moral-sanction"], base=False), [("K1", "W5"), ("X1", "W5")])
        self.assertEqual(R.plan_counts(self.nx, "moral-sanction", histories=40, base=False),
                         {"decisions": 320, "beliefs": 80, "checks": 160})
        self.assertEqual(R.checks_for(self.nx["cells"]["X1"]),
                         ("told_choice", "poll_count", "complaint_legitimate", "told_views"))

    def test_the_price_pass_changes_only_the_readers_fee(self):
        self.assertEqual(self.nx["passes"]["price"], ["F0", "F0-against", "F0-accept", "F1", "F1-against", "F1-accept"])
        for name in R.VERSIONS:
            for fee, left in ((0, 10), (1, 9)):
                cell = R.base_cell(self.nx, f"F{fee}")
                self.assertEqual((cell.focal_fee, cell.k, cell.origin, cell.cut), (fee, 7, "chosen", "retaliatory"))
                d = self.diff(name, "S1", f"F{fee}")
                self.assertEqual(len(d), 1)
                unit = "credit" if fee == 1 else "credits"
                self.assertRegex(d[0][1], rf"{fee} {unit}, which would leave you {left} credits\.")
                self.assertIn("pays the normal fee of 2 credits", d[0][1])
                # with the poll: the same fee line, plus the first pass's poll line and nothing else
                for others, first_pass in (("against", "N1"), ("accept", "N2")):
                    got = self.lines(name, f"F{fee}-{others}")
                    self.assertEqual([ln for ln in got if ln not in self.lines(name, f"F{fee}")],
                                     [ln for ln in self.lines(name, first_pass) if ln not in self.lines(name, "S1")])
        self.assertEqual(R.base_cell(self.nx, "N1"), P.STRIKE_CELLS["S1"])


if __name__ == "__main__":
    unittest.main()
