import json
import os
import tempfile
import unittest

from strike import costlog
from strike.costlog import CallRecord, CostLog, FundingError, FundingPlan
from strike.prices import estimate_cost

PLAN_PATH = os.path.join(os.path.dirname(__file__), "..", "funding_plan.json")


def record(**kw):
    base = dict(run_id="t", stage="smoke", funder="free_systems", key_label="free-systems",
                call_type="smoke", mode="sync")
    base.update(kw)
    return CallRecord(**base)


class PricesTest(unittest.TestCase):
    def test_section9_unit_costs(self):
        self.assertAlmostEqual(estimate_cost("anthropic/claude-sonnet-5.5", "sync", 6000, 1500), 0.027)
        self.assertAlmostEqual(estimate_cost("anthropic/claude-sonnet-5.5", "sync", 3000, 500), 0.011)
        self.assertAlmostEqual(estimate_cost("anthropic/claude-sonnet-5.5", "batch", 6000, 1500), 0.0135)

    def test_cache_reads_are_cheaper(self):
        full = estimate_cost("anthropic/claude-sonnet-5.5", "sync", 6000, 0)
        cached = estimate_cost("anthropic/claude-sonnet-5.5", "sync", 6000, 0, cached_tokens=4000)
        self.assertAlmostEqual(cached, (2000 * 2.0 + 4000 * 0.2) / 1e6)
        self.assertLess(cached, full)


class RecordTest(unittest.TestCase):
    def test_validation(self):
        record().validate()
        with self.assertRaises(ValueError):
            record(call_type="nonsense").validate()
        with self.assertRaises(ValueError):
            record(mode="stream").validate()
        with self.assertRaises(ValueError):
            record(key_label="sk-or-v1-abcdef").validate()

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            log = CostLog(os.path.join(d, "sub", "run.jsonl"))
            log.append(record(prompt_tokens=10, completion_tokens=5, cost_usd=0.001))
            log.append(record(attempt=2, error="timeout"))
            back = log.records()
            self.assertEqual(len(back), 2)
            self.assertTrue(back[0].ok)
            self.assertFalse(back[1].ok)
            with open(log.path) as f:
                self.assertNotIn("sk-", f.read())


class FundingTest(unittest.TestCase):
    def setUp(self):
        self.plan = FundingPlan.load(PLAN_PATH)

    def test_pilot_is_free_systems(self):
        for stage in ("smoke", "pilot-dev", "pilot-confirm"):
            self.assertEqual(self.plan.check(stage, "free-systems"), "free_systems")

    def test_unknown_or_unassigned_stage_refused(self):
        with self.assertRaises(FundingError):
            self.plan.funder_for("not-a-stage")
        plan = FundingPlan(self.plan.funders, dict(self.plan.stages, stage1=None))
        with self.assertRaises(FundingError):
            plan.funder_for("stage1")

    def test_every_stage_has_a_confirmed_funder(self):
        for stage in ("smoke", "pilot-dev", "pilot-confirm"):
            self.assertEqual(self.plan.check(stage, "free-systems"), "free_systems")
        for stage in ("stage1", "stage2", "stage3", "stage3-authorized-reward", "stage4"):
            self.assertEqual(self.plan.check(stage, "ihs-agentic-capital"), "ihs_agentic_capital")
            with self.assertRaises(FundingError):
                self.plan.check(stage, "free-systems")

    def test_pending_funders_block_their_stages(self):
        # Michael's and the Anthropic application's credits are not in hand; a
        # stage assigned to either is refused until the plan is changed in writing.
        for funder in ("idea_neblo", "anthropic_application"):
            plan = FundingPlan(self.plan.funders, dict(self.plan.stages, stage1=funder),
                               {"stage1": "ihs_agentic_capital"})
            with self.assertRaisesRegex(FundingError, "pending.*fallback is 'ihs_agentic_capital'"):
                plan.funder_for("stage1")

    def test_wrong_key_refused(self):
        with self.assertRaises(FundingError):
            self.plan.check("smoke", "someone-else")

    def test_cap_warnings(self):
        # A fixed $250 cap, so the test does not depend on the live plan's cap (raised to $500 on 26 October).
        funders = {k: dict(v) for k, v in self.plan.funders.items()}
        funders["free_systems"]["cap_usd"] = 250
        plan = FundingPlan(funders, self.plan.stages, self.plan.fallbacks)
        recs = [record(cost_usd=110.0), record(cost_usd=100.0)]
        notes = costlog.cap_warnings(recs, plan)
        self.assertEqual(len(notes), 1)
        self.assertIn("80%", notes[0])
        recs.append(record(cost_usd=45.0))
        self.assertIn("at or over", costlog.cap_warnings(recs, plan)[0])


class ManifestTest(unittest.TestCase):
    def test_assumptions_reproduce_section9(self):
        # Section 9 of v4.1 ($706.80 of model calls plus $120 flat, so about $1,071
        # with the $150 pilot line and 25 percent contingency), plus the authorized
        # reward pair: 1,800 decisions at $0.027, 3,600 continuations at $0.011, and
        # reason coding scaled from $20 to $24.44. Plus the completed orders (design
        # choice 14, 5 October): 3,150 batches at $0.018.
        m = costlog.manifest([])
        coding = 20.0 * 9900 / 8100
        calls = 586.8 + 88.2 + 3150 * 0.018
        self.assertAlmostEqual(m["standard"]["main_projected"], calls + coding + 100, places=6)
        self.assertAlmostEqual(m["batch"]["main_projected"], calls / 2 + coding + 100, places=6)
        self.assertAlmostEqual(m["standard"]["total_with_contingency"], (calls + coding + 100 + 150) * 1.25,
                               places=6)
        self.assertTrue(all(line["source"] == "assumed" for line in m["lines"]))

    def test_batch_units_follow_the_measured_completion_share(self):
        recs = [self.decision(f"s{i}") for i in range(4)]
        recs += [record(call_type="batch", stage="pilot-dev", slot_id=f"s{i}/batch", prompt_tokens=7000,
                        completion_tokens=400, cost_usd=0.018) for i in range(3)]
        m = costlog.manifest(recs)
        self.assertEqual(m["complete_share"], 0.75)
        line = next(l for l in m["lines"] if l["call_type"] == "batch")
        self.assertEqual(line["units"], 4725)
        self.assertIn("75% of the strike decisions completed", costlog.format_manifest(m))
        self.assertIsNone(costlog.manifest([])["complete_share"])

    def decision(self, slot, **kw):
        base = dict(call_type="decision", stage="pilot-dev", slot_id=slot, prompt_tokens=4000,
                    completion_tokens=900, cost_usd=0.017)
        base.update(kw)
        return record(**base)

    def test_measured_replaces_assumed(self):
        m = costlog.manifest([self.decision(f"s{i}") for i in range(3)])
        line = next(l for l in m["lines"] if l["call_type"] == "decision")
        self.assertEqual((line["source"], line["n_measured"], line["calls_per_slot"]), ("measured", 3, 1.0))
        self.assertAlmostEqual(line["projected_standard"], 6300 * (4000 * 2 + 900 * 10) / 1e6)
        self.assertAlmostEqual(m["pilot_actual"], 0.051)
        self.assertIn("ceiling", costlog.format_manifest(m))

    def test_every_attempt_in_a_slot_counts(self):
        # A billed failed attempt and a second call in the same slot double that slot's cost.
        one = costlog.manifest([self.decision("s1")])
        two = costlog.manifest([self.decision("s1", attempt=1, error="unusable", cost_usd=0.017),
                                self.decision("s1", attempt=2)])
        get = lambda m: next(l for l in m["lines"] if l["call_type"] == "decision")
        self.assertAlmostEqual(get(two)["projected_standard"], 2 * get(one)["projected_standard"])
        self.assertEqual(get(two)["calls_per_slot"], 2.0)

    def test_cache_writes_are_priced(self):
        plain = costlog.manifest([self.decision("s1", cost_usd=None)])
        written = costlog.manifest([self.decision("s1", cost_usd=None, cache_write_tokens=4000)])
        get = lambda m: next(l for l in m["lines"] if l["call_type"] == "decision")["projected_standard"]
        self.assertAlmostEqual(get(written) - get(plain), 6300 * 4000 * (2.50 - 2.00) / 1e6)

    def test_pilot_line_until_the_pilot_is_complete(self):
        recs = [self.decision("s1")]
        self.assertEqual(costlog.manifest(recs)["pilot_line"], 150.0)
        self.assertAlmostEqual(costlog.manifest(recs, pilot_complete=True)["pilot_line"], 0.017)

    def test_billed_charges_calibrate_the_projection(self):
        implied = (4000 * 2 + 900 * 10) / 1e6
        m = costlog.manifest([self.decision("s1", cost_usd=2 * implied)])
        line = next(l for l in m["lines"] if l["call_type"] == "decision")
        self.assertAlmostEqual(m["billed_over_implied"], 2.0)
        self.assertAlmostEqual(line["projected_standard"], 6300 * 2 * implied)
        self.assertIn("times the token-implied cost", costlog.format_manifest(m))

    def test_batch_summary_charge_is_not_a_slot(self):
        result = self.decision("s1", mode="batch", cost_usd=None)
        summary = record(call_type="decision", stage="pilot-dev", mode="batch", cost_usd=0.0085, batch_summary=True)
        m = costlog.manifest([result, summary])
        line = next(l for l in m["lines"] if l["call_type"] == "decision")
        self.assertEqual(line["n_measured"], 1)
        self.assertAlmostEqual(m["billed_over_implied"], 1.0)


if __name__ == "__main__":
    unittest.main()
