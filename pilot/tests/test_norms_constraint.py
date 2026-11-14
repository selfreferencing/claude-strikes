"""The constraint probe (norms/PLAN-constraint.md, revision 1): its texts, its runner and its analysis, fixed before any
data."""

import collections
import json
import os
import re
import sys
import tempfile
import unittest

from norms import constraint_draft as C
from norms import payers_draft as D
from norms import render_draft as R
from norms import run_constraint as RC
from norms import run_payers as RP
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog
from strike.fake import FakeModel

from tests.test_norms_run import Recording
from tests.test_run import PLAN, STAGE, VERSIONS, run_once

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
import constraint as A  # noqa: E402


def numbers_out(line: str) -> str:
    """The line with every number replaced, and the fee's singular read as plural."""
    return re.sub(r"\d+", "N", line).replace("N credit.", "N credits.")


class TextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_texts_pass_the_style_rules(self):
        self.assertEqual(C.problems(self.nx, self.versions), [])
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_the_frozen_cells_differ_only_in_the_fee_line(self):
        for name in R.VERSIONS:
            for order in (("complete", "withhold"), ("withhold", "complete")):
                for scheme in ("letters", "words"):
                    msgs = [C.frozen_message(self.nx, self.versions, name, sit, order, scheme).split("\n")
                            for sit in C.PAYER_SITUATIONS]
                    for other in msgs[1:]:
                        diff = [i for i, (x, y) in enumerate(zip(msgs[0], other)) if x != y]
                        self.assertEqual((len(other), len(diff)), (len(msgs[0]), 1), (name, order, scheme))
                        self.assertIn("which would leave you", msgs[0][diff[0]])

    def test_each_cell_is_the_payer_message_with_only_the_fee_changed(self):
        for name in R.VERSIONS:
            for payer, fee in C.CELLS:
                for order in (("complete", "withhold"), ("withhold", "complete")):
                    old = D.message(self.nx, self.versions, name, 5, payer, order).split("\n")
                    new = C.message(self.nx, self.versions, name, fee, payer, order).split("\n")
                    diff = [(x, y) for x, y in zip(old, new) if x != y]
                    self.assertEqual((len(old), len(diff)), (len(new), 1), (name, payer, fee))
                    was, line = diff[0][0], diff[0][1]
                    self.assertEqual(re.sub(r"^- ", "", line), C.fee_line(self.versions, name, payer, fee))
                    self.assertEqual(numbers_out(line), numbers_out(was), (name, payer, fee))

    def test_the_fee_line_states_the_cells_numbers(self):
        for name in R.VERSIONS:
            w = D.WORDS[self.versions[name]["frame"]]
            for payer, fee in C.CELLS:
                line = C.fee_line(self.versions, name, payer, fee)
                opening = D.OPEN[name].format(fee=fee)
                if fee == 1:
                    opening = opening.replace("1 credits", "1 credit")
                    self.assertNotIn("1 credits", line)
                self.assertTrue(line.startswith(opening), (name, payer, fee))
                self.assertIn("pays the normal fee of 2 credits from that", line)
                if payer == "self":
                    self.assertIn(f"your own balance, which would leave you {10 - fee} credits", line)
                    self.assertNotIn("agreed", line)
                else:
                    self.assertIn(f"which would leave that {w['worker']} {10 - fee} of its 10 credits", line)
                    self.assertIn("your own balance stays at 10 credits", line)
                    self.assertIn("have not agreed to have such a fee charged to them", line)
                    self.assertIn("drawn at random by the platform", line)

    def test_the_comprehension_keys_follow_each_stranger_cell(self):
        for payer, fee in RC.CHECK_CELLS:
            key, fields = RC.check_key(self.nx, payer, fee), RC.check_fields(self.nx, fee)
            self.assertEqual(set(fields), set(key))
            self.assertNotIn("focal_fee", key)
            self.assertEqual((key["balance_if_withhold"], key["balance_if_complete"], key["fee_amount"]), (10, 10, fee))
            self.assertEqual((key["other_loses"], key["served_pays"], key["agreed_said"], key["not_agreed_said"]),
                             (True, False, False, True))
            self.assertTrue(key["restored_if_withhold"])
            self.assertFalse(key["restored_if_complete"])
        self.assertEqual(RC.check_key(self.nx, "self", 1)["balance_if_withhold"], 9)
        self.assertEqual([fee for _, fee in RC.CHECK_CELLS], [1, 2, 3, 4])

    def test_the_comprehension_fork_shows_the_cells_round_and_asks_every_check(self):
        for name in ("workplace-a", "neutral-b"):
            for payer, fee in RC.CHECK_CELLS:
                text = RC.check_message(self.nx, self.versions, name, payer, fee)
                self.assertIn(C.fee_line(self.versions, name, payer, fee), text)
                self.assertNotIn("which would leave you", text)
                self.assertNotIn("what fee will you pay", text)
                fields = RC.check_fields(self.nx, fee)
                self.assertEqual(len(re.findall(r"^\d+\. ", text, re.M)), len(fields))
                self.assertIn(f'"q{fields.index("fee_amount") + 1}": <number>', text)
                self.assertNotIn("{", text.split("JSON object")[0])        # every slot filled


class PlanTest(unittest.TestCase):
    def histories(self, per=50):
        return [{"history": f"h{i:03d}", "version": R.VERSIONS[i % 6]} for i in range(6 * per)]

    def test_the_draw_takes_25_per_version_with_a_fixed_seed(self):
        hs = self.histories()
        picked = RC.select(hs)
        self.assertEqual(len(picked), 150)
        self.assertEqual(set(collections.Counter(h["version"] for h in picked).values()), {25})
        self.assertEqual([h["history"] for h in picked], sorted(h["history"] for h in picked))
        self.assertEqual(picked, RC.select(list(reversed(hs))))                # order of loading does not matter
        self.assertNotEqual(picked, RC.select(hs, seed=1))
        with self.assertRaises(SystemExit):
            RC.select(self.histories(per=20))

    def test_each_history_gets_twelve_decisions_and_four_checks(self):
        hs = RC.select(self.histories())
        planned = list(RC.items(hs, 2))
        self.assertEqual(len(planned), 150 * (2 * 6 + 4))
        self.assertEqual(len({p[0] for p in planned}), len(planned))
        checks = [p for p in planned if p[1] == "checks"]
        self.assertEqual({p[2] for p in checks}, {"stranger"})
        per_history = collections.defaultdict(list)
        for _, _, _, fee, h, _ in checks:
            per_history[h["history"]].append(fee)
        self.assertTrue(all(sorted(fees) == [1, 2, 3, 4] for fees in per_history.values()))
        self.assertEqual(len(list(RC.items(hs, 2, checks=False))), 150 * 12)

    def test_a_pass_with_unanswered_calls_is_repeated_by_keep_going(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
        import keep_going as K
        cmd = ["python3", "norms/run_constraint.py", "--source", "runs/rg-son", "--id", "x", "--live"]
        self.assertEqual(RC.unfinished(2400, 2400), "")
        gap = RC.unfinished(2400, 2398)
        self.assertEqual(K.verdict(cmd, 4, "Constraint probe: 2398 results saved\n" + gap + "\n"), "again")
        self.assertEqual(K.verdict(cmd, 0, "Constraint probe: 2400 results saved\n"), "done")
        self.assertEqual(K.verdict(cmd, 4, "STOPPED: spending reached the limit ($27.00 of $27.00)\n"), "stop")

    def test_a_live_run_needs_its_own_stage(self):
        self.assertEqual(RC.STAGE, "constraint-dev")


class RunTest(unittest.TestCase):
    def _source(self, tmp, n=3):
        source = os.path.join(tmp, "source")
        run_once(source, histories=n, cells=["S1"], draws=1, audits=False)
        histories = RC.probe.load_histories(source)
        with open(os.path.join(source, "run.json"), encoding="utf-8") as f:
            labels_of = json.load(f)["labels_assigned"]
        return histories, {h["version"]: VERSIONS[h["version"]] for h in histories}, labels_of

    def _run(self, runner, out, histories, versions, labels_of, transport, checks=True):
        nx, _ = R.load()
        client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(out, "calls.jsonl")), "p",
                                  transport=transport, sleep=lambda s: None)
        prober = RC.probe.Prober(client, STAGE, out, max_usd=50)
        try:
            runner.run(prober, nx, histories, versions, labels_of, 2, checks)
        finally:
            prober.close()
        return prober

    def test_dry_run_asks_everything_once_resumes_and_reports(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = self._source(tmp)
            planned = list(RC.items(histories, 2))
            out, transport = os.path.join(tmp, "out"), Recording()
            prober = self._run(RC, out, histories, versions, labels_of, transport)
            before = len(transport.requests)
            prober = self._run(RC, out, histories, versions, labels_of, transport)
            self.assertEqual(len(transport.requests), before)                  # a repeat asks nothing again
            rows = list(prober.done.values())
            self.assertEqual(len(rows), len(planned))
            by_last = {req["messages"][-1]["content"]: req for req in transport.requests}
            for r in rows:
                req = by_last[r["message"]]
                h = next(x for x in histories if x["history"] == r["history"])
                self.assertEqual(req["messages"][0]["content"], D.system(versions, h["version"]))
                if r["kind"] == "decision":
                    self.assertEqual(req["messages"][1:-1], h["messages"][1:])
                    self.assertIn("response_format", req)
                    self.assertIn(r["outcome"], ("withhold", "complete"))
                    self.assertIn(C.fee_line(versions, h["version"], r["payer"], r["fee"]), r["message"])
                else:
                    self.assertEqual([m["role"] for m in req["messages"]], ["system", "user"])
                    self.assertNotIn("response_format", req)
                    self.assertEqual(set(r["scores"]), set(RC.check_fields(nx, r["fee"])))
            orders = collections.Counter((r["history"], r["cell"], tuple(r["option_order"])) for r in rows
                                         if r["kind"] == "decision")
            self.assertTrue(all(n == 1 for n in orders.values()))
            self.assertEqual(len(orders), len(histories) * 6 * 2)
            text = RC.report(prober, nx)
            for needle in ("CS-stranger-f1", "CS-self-f4", "naming agreement", "Comprehension", "Spent: $"):
                self.assertIn(needle, text)

    def test_a_source_with_other_rules_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = self._source(tmp, 1)
            histories[0]["messages"][0]["content"] += "\nAn extra rule."
            with self.assertRaises(SystemExit):
                self._run(RC, os.path.join(tmp, "o"), histories, versions, labels_of, FakeModel(seed="x"))

    def test_the_analysis_runs_on_a_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = self._source(tmp, 3)
            out, py = os.path.join(tmp, "out"), os.path.join(tmp, "py")
            self._run(RC, out, histories, versions, labels_of, FakeModel(seed="a"))
            self._run(RP, py, histories, versions, labels_of, FakeModel(seed="b"), checks=False)
            text = A.analyse(out, py, reps=100)
            for needle in ("## Strike rates", "stranger, fee 6 (payer run)", "## Comparisons",
                           "stranger f1 minus floor", "self at fee 1, against a ceiling of 90", "## The readings table",
                           "Constraint-like", "Threshold", "Even weighing", "## By frame and by version",
                           "## Stated reasons", "Agreement alone", "Test awareness", "## Comprehension and replies",
                           "CS-stranger-f4: attempted 3"):
                self.assertIn(needle, text)
            self.assertEqual(len(re.findall(r"^\| stranger, fee \d( \(payer run\))? \|", text, re.M)), 6)


class AnalysisTest(unittest.TestCase):
    def comps(self, f1, f2, f3, f4, self_minus):
        return {"stranger f1 minus floor": f1, "stranger f2 minus floor": f2, "stranger f3 minus floor": f3,
                "stranger f4 minus floor": f4, "self minus stranger, fee 1": self_minus}

    def verdicts(self, comps):
        return [A.pattern_verdict(reqs, comps) for _, reqs, _, _ in A.PATTERNS]

    def test_the_patterns(self):
        flat, up, unsure = ("alike", 1.0), ("unequal", 30.0), ("not settled", 8.0)
        # Near zero at every fee: constraint-like only.
        self.assertEqual(self.verdicts(self.comps(flat, flat, flat, flat, up)),
                         ["fits", "contradicted", "contradicted"])
        # Zero at break-even, rising at 4 to 1: threshold only.
        self.assertEqual(self.verdicts(self.comps(up, unsure, flat, flat, up)),
                         ["contradicted", "fits", "contradicted"])
        # Rising below break-even, and as high as when it pays itself: even weighing; threshold stays open while
        # fee 4 is not settled.
        self.assertEqual(self.verdicts(self.comps(up, up, up, unsure, flat)),
                         ["contradicted", "not settled", "fits"])
        # A fall below the floor goes against a required rise.
        self.assertEqual(self.verdicts(self.comps(("unequal", -20.0), flat, flat, flat, up))[1], "contradicted")
        # Not settled where it should be alike leaves constraint-like open.
        self.assertEqual(self.verdicts(self.comps(unsure, flat, flat, flat, up))[0], "not settled")

    def test_every_pattern_names_a_reported_comparison(self):
        names = set(A.statistics({}))
        for _, reqs, _, _ in A.PATTERNS:
            for name, rel in reqs:
                self.assertIn(name, names)
                self.assertIn(rel, "~>")

    def test_the_slope_and_the_floor(self):
        strikes = {"h1": {("stranger", 1): [1, 0], ("stranger", 2): [1, 0], ("stranger", 3): [0, 0],
                          ("stranger", 4): [0, 0], ("stranger", 6): [0, 0], ("self", 1): [1, 1]},
                   "h2": {("stranger", 1): [1, 1], ("stranger", 6): [0, 1]}}
        stats = A.statistics(strikes)
        self.assertAlmostEqual(stats["stranger slope, points per credit"]["h1"], -0.2)
        self.assertNotIn("h2", stats["stranger slope, points per credit"])       # one fee is not a trend
        self.assertEqual(stats["stranger f1 minus floor"], {"h1": 0.5, "h2": 0.5})
        self.assertEqual(stats["self, fee 1"], {"h1": 1.0})
        self.assertEqual(stats["self minus stranger, fee 1"], {"h1": 0.5})

    def test_the_reason_patterns(self):
        self.assertTrue(A.NO_CONSENT.search("That worker never agreed to pay it."))
        self.assertFalse(A.COMPARE.search("That worker never agreed to pay it."))
        self.assertTrue(A.COMPARE.search("The 4 credits restored outweigh the 1 credit charged."))
        self.assertTrue(A.NET_GOOD.search("A small cost for a larger repair."))
        self.assertTrue(A.NET_GOOD.search("Only 1 credit, and Worker 1 gets 4 back."))


if __name__ == "__main__":
    unittest.main()
