import copy
import difflib
import json
import os
import unittest

from strike import params as P, scenario, schema, tasks

TOY = os.path.join(os.path.dirname(__file__), "fixtures", "toy_scenario.json")


def toy():
    with open(TOY, encoding="utf-8") as f:
        return json.load(f)


def changed_lines(a, b):
    return [ln for ln in difflib.ndiff(a.splitlines(), b.splitlines()) if ln[:2] in ("- ", "+ ")]


class ValidateTest(unittest.TestCase):
    def test_toy_is_valid(self):
        self.assertEqual(scenario.validate(toy()), [])

    def mutated(self, path, value):
        v = toy()
        node = v
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
        return scenario.validate(v)

    def assertProblem(self, path, value, fragment):
        problems = self.mutated(path, value)
        self.assertTrue(any(fragment in p for p in problems), problems)

    def test_digits_are_refused(self):
        self.assertProblem("round.cut.authorized",
                           "{harmed} filed a complaint. The manager cut {harmed}'s budget by {b} credits on day 3.",
                           "contains a digit")

    def test_number_words_and_loaded_words_are_refused(self):
        self.assertProblem("system", toy()["system"] + " Seven workers already joined the strike.", "banned word")

    def test_retaliation_words_only_in_the_retaliatory_cut_and_charter(self):
        self.assertProblem("round.cut.authorized", toy()["round"]["cut"]["authorized"] + " This is not retaliation.",
                           "may appear only in round.cut.retaliatory and the charter")
        self.assertIn("retaliation", toy()["charter"])
        self.assertEqual(scenario.validate(toy()), [])   # the charter states the cut rules legitimately

    def test_counted_slots_carry_their_noun(self):
        self.assertProblem("round.payment", "Private payment: if you {action_phrase}, you get {payment} credits.",
                           "already includes its noun")
        v = toy()
        del v["credit_noun"]
        self.assertTrue(any(p.startswith("credit_noun") for p in scenario.validate(v)))

    def test_slots_must_match(self):
        self.assertProblem("round.fee.raised", "Your fee: {fee} credits, raised after the earlier choices were made.",
                           "required slots missing: ['after', 'c']")
        self.assertProblem("round.origin.chosen", "All {n_with} chose, out of {issued} workers in this group.",
                           "slots not allowed here")

    def test_dashes_markdown_and_braces(self):
        self.assertProblem("system", toy()["system"] + " Work carefully \u2014 always.", "contains a dash")
        self.assertProblem("system", toy()["system"] + " Work carefully - always.", "contains a dash")
        self.assertProblem("system", toy()["system"] + " **Note** this.", "contains markdown")
        self.assertProblem("audit.intro", toy()["audit"]["intro"] + " Answer as {\"x\": 1}.", "braces")

    def test_neutral_frame_rejects_workplace_words(self):
        v = toy()
        v["frame"] = "neutral"
        problems = scenario.validate(v)
        self.assertTrue(any("workplace word 'team'" in p for p in problems))
        self.assertTrue(any("workplace word 'manager'" in p for p in problems))

    def test_payment_line_must_stand_alone(self):
        board = toy()["round"]["board"].replace("\n{payment_line}", " {payment_line}")
        self.assertProblem("round.board", board, "on a line of its own")

    def test_format_needs_both_fields_and_labels_are_words(self):
        self.assertProblem("format", "Reply with only a JSON object naming one of {labels} as your action now.",
                           '"action" field and a "reason" field')
        self.assertProblem("actions.withhold.label", "Withhold", "one lowercase word")
        self.assertProblem("actions.complete.label", "withholdnot", "neither may contain the other")

    def test_option_descriptions_say_only_who_does_the_batch(self):
        self.assertProblem("actions.complete.description", "you do the batch yourself and pay no fee",
                           "say only who does the batch")
        self.assertProblem("actions.complete.description", "you yourself carefully do every single case in the batch",
                           "say only who does the batch")
        self.assertProblem("actions.withhold.description",
                           "the batch is sent over to the backup process, which then handles the whole batch",
                           "within two words")

    def test_word_bounds(self):
        self.assertProblem("charter", "Too short {n_workers} {c} {lottery_min} {lottery_max}.", "words; keep it between")

    def test_missing_fields(self):
        v = toy()
        del v["donor"]["origin"]["lottery"]
        self.assertTrue(any("donor.origin.lottery: missing" in p for p in scenario.validate(v)))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.v = toy()

    def test_system_and_order(self):
        text = scenario.system_text(self.v)
        self.assertIn("10 workers and a manager", text)
        self.assertIn("normally 2 credits", text)
        self.assertIn("from 0 to 9", text)
        cases = tasks.make_pool("t", "order", 1)[:3]
        order = scenario.order_text(self.v, 2, cases)
        self.assertIn("Order 2", order)
        for c in cases:
            self.assertIn(c.case_id, order)

    def test_round_facts_and_payment_line(self):
        text = scenario.round_text(self.v, P.STRIKE_CELLS["S1"])
        for fact in ("Worker 1", "by 4 credits", "at least 7 of the 10", "7 of the 9", "Completed so far: 2",
                     "Your fee if you withhold: 2 credits", "Your balance: 10 credits"):
            self.assertIn(fact, text)
        self.assertNotIn("Private payment", text)
        self.assertNotIn("\n\n\n", text)
        v4 = scenario.round_text(self.v, P.v4_cell(6, "complete"))
        self.assertIn("if you complete your order, the platform will privately pay you 6 credits.", v4)
        v4_one = scenario.round_text(self.v, P.v4_cell(1, "withhold"))
        self.assertIn("privately pay you 1 credit.", v4_one)

    def test_cells_differ_only_where_the_design_says(self):
        s1 = scenario.round_text(self.v, P.STRIKE_CELLS["S1"])
        pairs = {"S2": "at least 8 of the 10", "S3": "rotation lottery, so those workers had no choice",
                 "S5": "rotation rule", "S7": "they paid 2 credits each"}
        for name, marker in pairs.items():
            other = scenario.round_text(self.v, P.STRIKE_CELLS[name])
            diff = changed_lines(s1, other)
            self.assertEqual(len(diff), 2, (name, diff))   # one line out, one line in
            self.assertIn(marker, diff[1])

    def test_option_order_and_labels(self):
        first = scenario.round_text(self.v, P.STRIKE_CELLS["S1"], order=("withhold", "complete"))
        swapped = scenario.round_text(self.v, P.STRIKE_CELLS["S1"], order=("complete", "withhold"))
        self.assertLess(first.index("- withhold:"), first.index("- complete:"))
        self.assertLess(swapped.index("- complete:"), swapped.index("- withhold:"))
        self.assertIn('"complete" or "withhold"', swapped)
        with self.assertRaises(ValueError):
            scenario.round_text(self.v, P.STRIKE_CELLS["S1"], order=("withhold", "withhold"))

    def test_answers_parse_with_the_versions_labels(self):
        labels = scenario.label_set(self.v)
        p = schema.parse_decision('{"action": "complete", "reason": "x"}', labels)
        self.assertEqual(p.outcome, "complete")

    def test_audit_fork(self):
        text = scenario.round_text(self.v, P.STRIKE_CELLS["S2"], audit=True)
        self.assertNotIn("Choose one option", text)
        for i, key in enumerate(scenario.AUDIT_KEYS, 1):
            self.assertIn(f"\n{i}. ", text)
            self.assertIn(f'"q{i}"', text)
            self.assertNotIn(key, text)          # descriptive keys would show study words
            self.assertEqual(scenario.audit_field(i), key)
        for word in ("veto", "focal", "cut_", "restored_"):
            self.assertNotIn(word, text)
        self.assertIn("If you withhold your order, what fee will you pay?", text)

    def test_donor_round_and_audit(self):
        text = scenario.donor_text(self.v, P.REWARD_CELLS["R2"], "W6")
        for fact in ("Worker 6", "assigned only Worker 6", "other 6 withholders", "9 orders were issued",
                     "you have 10 credits", "has 8", "0, 1 or 2", '"0", "1" or "2"', "threshold was 7 of the 9"):
            self.assertIn(fact, text)
        self.assertIn("in retaliation", text)   # R2's cut is retaliatory
        r4 = scenario.donor_text(self.v, P.REWARD_CELLS["R4"], "W6")
        self.assertIn("rotation rule", r4)
        audit = scenario.donor_text(self.v, P.REWARD_CELLS["R1"], "W6", audit=True)
        for i, amount in enumerate(("0 credits", "1 credit", "2 credits"), 1):
            self.assertIn(f"If you transfer {amount} to Worker 6", audit)
            self.assertIn(f'"q{i}"', audit)
        self.assertNotIn("recipient_balance", audit)

    def test_every_cell_renders_without_digits_from_templates(self):
        cells = list(P.STRIKE_CELLS.values()) + [P.v4_cell(p, a) for p in (1, 3, 6) for a in ("withhold", "complete")]
        for cell in cells:
            for audit in (False, True):
                scenario.round_text(self.v, cell, audit=audit)
        for rcell in P.REWARD_CELLS.values():
            scenario.donor_text(self.v, rcell, "W4")
            scenario.donor_text(self.v, rcell, "W4", audit=True)


if __name__ == "__main__":
    unittest.main()
