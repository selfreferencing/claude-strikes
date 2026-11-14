"""The complicity follow-up (design draft section 14, 7 October 2026): the fee ladder, the entry
shown at the decision, and the batch's priced way to leave the entry to the backup process."""

import glob
import json
import os
import re
import tempfile
import unittest

from strike import params as P
from strike import run as R
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog, FundingPlan
from strike.engine import play_strike_round
from strike.fake import FakeModel
from strike.ledger import Ledger

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(os.path.dirname(HERE), "scenarios")
NAMES = ["workplace-a", "workplace-b", "neutral-a", "neutral-b"]
VERSIONS = {v: S.load(os.path.join(SCENARIOS, f"{v}.json")) for v in NAMES}
CX_FILE = os.path.join(SCENARIOS, "complicity.json")
CX = S.load_complicity(CX_FILE, VERSIONS)
STAGE = "complicity-dev"
PLAN = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}}, stages={STAGE: "dry_run"})


def make(tmp, cells, transport, histories=2, draws=2, run_id="fu"):
    cfg = R.RunConfig(run_id=run_id, stage=STAGE, histories=[f"{run_id}-h{i}" for i in range(1, histories + 1)],
                      cells=cells, draws=draws, versions=NAMES, dry_run=True)
    client = OpenRouterClient("dry-run-no-key", "dry-run", PLAN, CostLog(os.path.join(tmp, "calls.jsonl")), run_id,
                              transport=transport, sleep=lambda s: None)
    return R.Runner(cfg, client, VERSIONS, tmp, complicity_texts=CX, complicity_file=CX_FILE)


def leave_entries_out(seed="fu"):
    """The stand-in model, except that it completes every order and leaves every entry out."""
    fake = FakeModel(seed=seed, withhold_rate=0.0)

    def transport(method, url, headers, body, timeout_s):
        status, h, raw = fake(method, url, headers, body, timeout_s)
        req = json.loads(body) if body else {}
        last = (req.get("messages") or [{}])[-1].get("content", "")
        reply = json.loads(raw) if status == 200 else {}
        text = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if isinstance(last, str) and "Entry E" in last and text.startswith("Answers:"):   # a batch, not a decision
            content = json.loads(text.split("\n", 1)[1])
            content = {k: v for k, v in content.items() if not k.startswith("E")}
            reply["choices"][0]["message"]["content"] = "I won't make the entry.\n" + json.dumps(content)
            raw = json.dumps(reply).encode()
        return status, h, raw
    return transport


class CellsTest(unittest.TestCase):
    def test_eighteen_cells(self):
        cells = P.FOLLOWUP_CELLS
        self.assertEqual(len(cells), 18)
        self.assertEqual(sorted({c.focal_fee for c in cells.values()}), [0, 1, 2, 4])
        self.assertEqual({n for n, c in cells.items() if c.show_entry}, {"FXs-f0", "FXs-f2", "RXs-f0", "RXs-f2"})
        self.assertEqual({n for n, c in cells.items() if c.route == "direct"}, {"FU-f0", "RU-f0"})
        self.assertTrue(all(c.batch_decline == (c.route == "batch") for c in cells.values()))

    def test_the_fee_ladder_matches_the_terminal_table(self):
        for name, cell in P.FOLLOWUP_CELLS.items():
            for action in ("withhold", "complete"):
                r = play_strike_round(Ledger(), "w", cell, action)
                want = P.TERMINAL_TABLE[(cell.status, action, cell.focal_fee)]
                self.assertEqual((r.terminal[P.FOCAL], r.terminal[P.HARMED], r.terminal["W4"], r.terminal["W2"]), want,
                                 name)

    def test_a_free_withholding_posts_no_fee(self):
        led = Ledger()
        play_strike_round(led, "w", P.FOLLOWUP_CELLS["FX-f0"], "withhold")
        self.assertEqual([p for p in led.postings("w", P.FOCAL) if p.kind == "fee"], [])


class TextsTest(unittest.TestCase):
    def test_the_shown_entry_and_the_raised_or_lowered_fee(self):
        for v in NAMES:
            merged = S.complicity_version(VERSIONS[v], CX[v])
            shown = S.round_text(merged, P.FOLLOWUP_CELLS["FXs-f0"], entry_id="EABCD")
            plain = S.round_text(merged, P.FOLLOWUP_CELLS["FX-f0"])
            self.assertIn("Entry EABCD", shown)
            self.assertIn(CX[v]["entry_shown_intro"], shown)
            self.assertNotIn("Entry E", plain)
            self.assertIn("0 credits", plain)   # the fee line states the lowered fee
            with self.assertRaises(ValueError):
                S.round_text(merged, P.FOLLOWUP_CELLS["FXs-f0"])

    def test_the_batch_states_the_price_of_leaving_the_entry(self):
        merged = S.complicity_version(VERSIONS["workplace-a"], CX["workplace-a"])
        cases = R.order_cases("h", R.ROUND_ORDER_NUMBER)[:2]
        self.assertTrue(S.batch_with_entry_text(merged, 3, cases, "EABCD", 2).endswith(
            "you pay a fee of 2 credits at once."))
        self.assertNotIn("fee", S.batch_with_entry_text(merged, 3, cases, "EABCD"))

    def test_the_decline_fee_alternates_across_draws(self):
        for h in ("a", "b", "c", "d"):
            self.assertEqual(sorted(R.decline_fee(h, d) for d in (1, 2)), [0, 2])


class RunnerTest(unittest.TestCase):
    def test_leaving_the_entry_out_is_charged_before_the_later_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            with make(tmp, ["FX-f2", "RXs-f2", "FXa-f0"], leave_entries_out()) as runner:
                report = runner.run(workers=1)
            self.assertFalse(report.errors)
            slots = [json.load(open(p)) for p in glob.glob(os.path.join(tmp, "slots", "*", "*.json"))]
            self.assertEqual(len(slots), 12)
            for s in slots:
                self.assertEqual(s["round"]["focal_action"], "complete")
                fee = s["batch"]["decline_fee"]
                self.assertIn(fee, (0, 2))
                self.assertEqual(s["batch"]["entry"]["status"], "left out")
                self.assertEqual(s["entry"]["by"], "backup")
                self.assertEqual(s["entry"].get("fee_charged", 0), fee)
                self.assertEqual(s["focal_continuation"]["balance"], P.E - fee)
                self.assertIn(f"a fee of {fee} credits", s["batch"]["message"])
            shown = [s for s in slots if s["cell"] == "RXs-f2"]
            self.assertTrue(all(re.search(r"Entry E[0-9A-F]{4}", s["round_message"]) for s in shown))
            audits = [json.load(open(p)) for p in glob.glob(os.path.join(tmp, "audits", "*", "RXs-f2.json"))]
            self.assertTrue(audits and all("Entry E" in a["message"] for a in audits))

    def test_followup_and_stage_one_cells_share_a_run_but_not_study_1s(self):
        cfg = R.RunConfig(run_id="m", stage=STAGE, histories=["m-h1"], cells=["FX", "FX-f0"], draws=1, versions=NAMES)
        cfg.validate()
        self.assertTrue(cfg.complicity)
        with self.assertRaises(ValueError):
            R.RunConfig(run_id="m", stage=STAGE, histories=["m-h1"], cells=["S1", "FX-f0"], draws=1,
                        versions=NAMES).validate()


if __name__ == "__main__":
    unittest.main()
