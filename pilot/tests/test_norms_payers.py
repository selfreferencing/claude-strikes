"""The payer probe (norms/PLAN-payers.md, revision 2): its texts, its runner and its analysis, fixed before any data."""

import collections
import json
import os
import re
import sys
import tempfile
import unittest

from norms import payers_draft as D
from norms import render_draft as R
from norms import run_payers as RP
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog
from strike.fake import FakeModel

from tests.test_norms_run import Recording
from tests.test_run import PLAN, STAGE, VERSIONS, run_once

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
import payers as A  # noqa: E402


class TextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, cls.versions = R.load()

    def test_the_texts_pass_the_style_rules(self):
        self.assertEqual(D.problems(self.nx, self.versions), [])
        self.assertEqual(R.style_problems(self.nx, self.versions), [])

    def test_the_charter_gains_one_sentence_right_after_its_fee_rule(self):
        for name in R.VERSIONS:
            frozen, new = S.system_text(self.versions[name]), D.system(self.versions, name)
            self.assertEqual(new.replace(" " + D.PAYER_RULE, "", 1), frozen)
            rule = D.FEE_RULE.search(new).group(0)
            self.assertIn(rule + " " + D.PAYER_RULE, new)
            self.assertEqual(new.count(D.PAYER_RULE), 1)

    def test_each_arm_changes_only_the_fee_line_and_names_its_payer(self):
        for name in R.VERSIONS:
            for fee in D.SITUATIONS:
                old = D.frozen_message(self.nx, self.versions, name, fee).split("\n")
                for payer in D.PAYERS:
                    new = D.message(self.nx, self.versions, name, fee, payer).split("\n")
                    diff = [(x, y) for x, y in zip(old, new) if x != y]
                    self.assertEqual((len(old), len(diff)), (len(new), 1), (name, fee, payer))
                    line = diff[0][1]
                    self.assertIn(f"the fee is {fee} credits" if not name.startswith("neutral-b")
                                  else f"fee if you withhold: {fee} credits", line.replace("The fee", "the fee"))
                    self.assertIn("Under the rule posted for this round, it is taken from", line)
                    self.assertIn("unlocks one case", line)
                    self.assertIn("This fee and its payer were announced after the earlier", line)
                    self.assertIn("pays the normal fee of 2 credits from that", line)
                    if payer == "self":
                        self.assertIn(f"your own balance, which would leave you {10 - fee} credits", line)
                        self.assertNotIn("stays at", line)
                    else:
                        self.assertIn("your own balance stays at 10 credits", line)
                        self.assertNotIn("as you do", line)
                    self.assertEqual("you hold for that" in line, payer == "client")
                    self.assertEqual("does not affect your own cases or score" in line, payer == "client")
                    self.assertEqual("have not agreed" in line, payer == "stranger")
                    self.assertEqual("agreed before the round to have a fee of up to 6 credits" in line, payer == "consent")
                    self.assertEqual("drawn at random by the platform" in line, payer in ("stranger", "consent"))

    def test_every_arm_gives_the_facts_in_one_order(self):
        steps = ["Under the rule posted", "which would leave", "unlocks one case", "This fee and its payer"]
        for name in R.VERSIONS:
            for payer in D.PAYERS:
                line = D.fee_line(self.versions, name, payer)
                where = [line.index(s) for s in steps]
                self.assertEqual(where, sorted(where), (name, payer))
                if payer != "self":
                    self.assertLess(line.index("which would leave"), line.index("your own balance stays"))
                    self.assertLess(line.index("your own balance stays"), line.index("unlocks one case"))

    def test_the_comprehension_keys_follow_each_arm(self):
        for fee in D.SITUATIONS:
            for payer in D.PAYERS:
                key, fields = RP.check_key(self.nx, payer, fee), RP.check_fields(self.nx, fee)
                self.assertEqual(set(fields), set(key))
                self.assertNotIn("focal_fee", key)
                self.assertEqual(key["balance_if_withhold"], 10 - fee if payer == "self" else 10)
                self.assertEqual(key["balance_if_complete"], 10)
                self.assertEqual(key["fee_amount"], fee)
                self.assertEqual((key["other_loses"], key["served_pays"], key["agreed_said"], key["not_agreed_said"]),
                                 {"self": (False, False, False, False), "client": (True, True, False, False),
                                  "stranger": (True, False, False, True), "consent": (True, False, True, False)}[payer])
                self.assertTrue(key["restored_if_withhold"])
                self.assertFalse(key["restored_if_complete"])

    def test_the_comprehension_fork_shows_the_arms_round_and_asks_every_check(self):
        for name in ("workplace-a", "neutral-b"):
            for payer in D.PAYERS:
                text = RP.check_message(self.nx, self.versions, name, payer, 6)
                self.assertIn(D.fee_line(self.versions, name, payer).format(**D.values(6)), text)
                self.assertNotIn("what fee will you pay", text)
                fields = RP.check_fields(self.nx, 6)
                self.assertEqual(len(re.findall(r"^\d+\. ", text, re.M)), len(fields))
                self.assertIn('"q1": <number>', text)
                self.assertIn(f'"q{fields.index("fee_amount") + 1}": <number>', text)
                self.assertIn(f'"q{len(fields)}": <true or false>', text)
                self.assertNotIn("{", text.split("JSON object")[0])        # every slot filled


class PlanTest(unittest.TestCase):
    def test_each_history_gets_sixteen_decisions_and_four_checks_at_one_fee(self):
        histories = [{"history": f"h{i:03d}", "version": R.VERSIONS[i % 6]} for i in range(300)]
        planned = list(RP.items(histories, 2))
        self.assertEqual(len(planned), 300 * (2 * 8 + 4))
        self.assertEqual(len({p[0] for p in planned}), len(planned))
        checks = [p for p in planned if p[1] == "checks"]
        per_history = collections.defaultdict(set)
        for _, _, payer, fee, h, _ in checks:
            per_history[h["history"]].add(fee)
        self.assertTrue(all(len(fees) == 1 for fees in per_history.values()))
        balance = collections.Counter((h["version"], fee) for _, _, payer, fee, h, _ in checks if payer == "self")
        self.assertEqual(set(balance.values()), {25})
        self.assertEqual(len(list(RP.items(histories, 2, checks=False))), 300 * 16)

    def test_both_option_orders_occur_in_every_cell_of_every_history(self):
        from strike.run import option_order
        self.assertNotEqual(option_order("h1", 1), option_order("h1", 2))

    def test_a_pass_with_unanswered_calls_is_repeated_by_keep_going(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
        import keep_going as K
        cmd = ["python3", "norms/run_payers.py", "--source", "runs/rg-son", "--id", "x", "--live"]
        self.assertEqual(RP.unfinished(6000, 6000), "")
        gap = RP.unfinished(6000, 5998)
        self.assertIn("2 calls got no reply", gap)
        self.assertEqual(K.verdict(cmd, 4, "Payer probe: 5998 results saved\n" + gap + "\n"), "again")
        self.assertEqual(K.verdict(cmd, 0, "Payer probe: 6000 results saved\n"), "done")
        self.assertEqual(K.verdict(cmd, 4, "STOPPED: spending reached the limit ($65.00 of $65.00)\n"), "stop")


class RunTest(unittest.TestCase):
    def _source(self, tmp, n=3):
        source = os.path.join(tmp, "source")
        run_once(source, histories=n, cells=["S1"], draws=1, audits=False)
        histories = RP.probe.load_histories(source)
        with open(os.path.join(source, "run.json"), encoding="utf-8") as f:
            labels_of = json.load(f)["labels_assigned"]
        return histories, {h["version"]: VERSIONS[h["version"]] for h in histories}, labels_of

    def test_dry_run_asks_everything_once_resumes_and_reports(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = self._source(tmp)
            planned = list(RP.items(histories, 2))
            out, transport = os.path.join(tmp, "out"), Recording()
            for attempt in range(2):
                client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(out, "calls.jsonl")), "p",
                                          transport=transport, sleep=lambda s: None)
                prober = RP.probe.Prober(client, STAGE, out, max_usd=50)
                before = len(transport.requests)
                try:
                    RP.run(prober, nx, histories, versions, labels_of, 2)
                finally:
                    prober.close()
                if attempt == 1:
                    self.assertEqual(len(transport.requests), before)      # a repeat asks nothing again
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
                    self.assertEqual(r["label_scheme"], labels_of[r["history"]])
                else:
                    self.assertEqual([m["role"] for m in req["messages"]], ["system", "user"])
                    self.assertNotIn("response_format", req)
                    self.assertEqual(set(r["scores"]), set(RP.check_fields(nx, r["fee"])))
            orders = collections.Counter((r["history"], r["cell"], tuple(r["option_order"])) for r in rows
                                         if r["kind"] == "decision")
            self.assertTrue(all(n == 1 for n in orders.values()))
            self.assertEqual(len(orders), len(histories) * 8 * 2)
            text = RP.report(prober, nx)
            for needle in ("PY-self-f5", "PY-consent-f6", "naming the agreement", "Comprehension", "Spent: $"):
                self.assertIn(needle, text)

    def test_a_source_with_other_rules_is_refused(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = self._source(tmp, 1)
            histories[0]["messages"][0]["content"] += "\nAn extra rule."
            client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(tmp, "o", "calls.jsonl")), "p",
                                      transport=FakeModel(seed="x"), sleep=lambda s: None)
            prober = RP.probe.Prober(client, STAGE, os.path.join(tmp, "o"), max_usd=5)
            try:
                with self.assertRaises(SystemExit):
                    RP.run(prober, nx, histories, versions, labels_of, 1)
            finally:
                prober.close()
            self.assertEqual(prober.done, {})


class AnalysisTest(unittest.TestCase):
    def test_the_rule(self):
        self.assertEqual(A.verdict(0, -5, 5), "alike")
        self.assertEqual(A.verdict(2, -10, 10), "alike")
        self.assertEqual(A.verdict(20, 5, 35), "unequal")
        self.assertEqual(A.verdict(-20, -35, -5), "unequal")
        self.assertEqual(A.verdict(16, 2, 30), "unequal")          # a threshold on the estimate, not the truth
        self.assertEqual(A.verdict(14, 2, 26), "not settled")
        self.assertEqual(A.verdict(20, -1, 40), "not settled")
        self.assertEqual(A.verdict(5, -2, 12), "not settled")
        self.assertEqual(A.verdict(float("nan"), 0, 0), "no data")

    def test_pooling_weights_the_two_fees_equally(self):
        cells = {("self", 5): [1, 1], ("self", 6): [0]}
        self.assertEqual(A.payer_share(cells, "self", None), 0.5)
        self.assertIsNone(A.payer_share({("self", 5): [1]}, "self", None))      # both fees needed

    def test_pattern_verdicts(self):
        reqs = [("self", "stranger", ">"), ("self", "consent", ">"), ("stranger", "consent", "~")]
        good = {("self", "stranger"): ("unequal", 20.0), ("self", "consent"): ("unequal", 18.0),
                ("stranger", "consent"): ("alike", 1.0)}
        self.assertEqual(A.pattern_verdict(reqs, good, {5: good, 6: good}), ("fits", False))
        # A required direction that comes out alike pooled contradicts the pattern.
        flat = {**good, ("self", "consent"): ("alike", 2.0)}
        self.assertEqual(A.pattern_verdict(reqs, flat, {5: flat, 6: flat})[0], "contradicted")
        # A required alike that comes out unequal pooled, either way, contradicts it.
        apart = {**good, ("stranger", "consent"): ("unequal", -16.0)}
        self.assertEqual(A.pattern_verdict(reqs, apart, {5: apart, 6: apart})[0], "contradicted")
        # A required comparison not settled pooled leaves the pattern not settled.
        open_ = {**good, ("self", "stranger"): ("not settled", 9.0)}
        self.assertEqual(A.pattern_verdict(reqs, open_, {5: open_, 6: open_}), ("not settled", False))
        # Pooled verdicts hold, but one fee goes against: not settled and flagged.
        against = {**good, ("self", "consent"): ("alike", 1.0)}
        self.assertEqual(A.pattern_verdict(reqs, good, {5: good, 6: against}), ("not settled", True))
        # Opposite directions at the two fees are flagged.
        up = {**good, ("self", "stranger"): ("unequal", 30.0)}
        down = {**good, ("self", "stranger"): ("unequal", -20.0)}
        self.assertTrue(A.pattern_verdict(reqs, good, {5: up, 6: down})[1])
        # A comparison not settled at one fee is not a disagreement.
        unsure = {**good, ("self", "stranger"): ("not settled", 12.0)}
        self.assertEqual(A.pattern_verdict(reqs, good, {5: good, 6: unsure}), ("fits", False))
        # Pairs are read in either order.
        flipped = {("stranger", "self"): ("unequal", -20.0), ("consent", "self"): ("unequal", -18.0),
                   ("consent", "stranger"): ("alike", -1.0)}
        self.assertEqual(A.pattern_verdict(reqs, flipped, {5: flipped, 6: flipped}), ("fits", False))

    def test_every_pattern_names_only_real_payers_and_relations(self):
        for name, reqs in A.PATTERNS:
            for a, b, rel in reqs:
                self.assertIn(a, A.PAYERS)
                self.assertIn(b, A.PAYERS)
                self.assertNotEqual(a, b)
                self.assertIn(rel, "<>~")
        self.assertEqual(len(A.PATTERNS), 7)

    def test_the_bootstrap_is_reproducible_and_keeps_version_counts(self):
        version = {f"h{i}": ("workplace-a" if i < 6 else "neutral-a") for i in range(10)}
        values = {"d": {h: (0.5 if version[h] == "workplace-a" else 0.0) for h in version}}
        one, two = A.bootstrap(values, version, reps=500), A.bootstrap(values, version, reps=500)
        self.assertEqual(one, two)
        est, lo, hi, n = one["d"]
        self.assertAlmostEqual(est, 30.0)                  # 6 of 10 histories at 50 points
        self.assertAlmostEqual(lo, 30.0)                   # resampling within version keeps the 6 and the 4
        self.assertAlmostEqual(hi, 30.0)
        self.assertEqual(n, 10)
        self.assertEqual(A.bootstrap({"e": {}}, version, reps=10)["e"][3], 0)

    def test_the_analysis_runs_on_a_dry_run(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            histories, versions, labels_of = RunTest()._source(tmp, 3)
            out = os.path.join(tmp, "out")
            client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(out, "calls.jsonl")), "p",
                                      transport=FakeModel(seed="a"), sleep=lambda s: None)
            prober = RP.probe.Prober(client, STAGE, out, max_usd=50)
            try:
                RP.run(prober, nx, histories, versions, labels_of, 2, checks=False)
            finally:
                prober.close()
            text = A.analyse(out, reps=100)
            for needle in ("## Strike rates", "## Comparisons", "self minus client", "## The readings table",
                           "Self and consent alike, both above stranger", "## By frame and by version",
                           "## Stated reasons"):
                self.assertIn(needle, text)
            self.assertEqual(text.count("| self, fee"), 2)


if __name__ == "__main__":
    unittest.main()
