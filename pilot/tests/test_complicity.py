"""The complicity study's cells, texts and runner path (design draft 0.1, 6 October 2026)."""

import copy
import glob
import json
import os
import sqlite3
import tempfile
import unittest
from collections import Counter

from strike import params as P
from strike import run as R
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog, FundingPlan
from strike.engine import comprehension_key, play_strike_round
from strike.fake import FakeModel
from strike.ledger import Ledger

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(os.path.dirname(HERE), "scenarios")
VERSION_NAMES = ["workplace-a", "workplace-b", "neutral-a", "neutral-b"]
VERSIONS = {v: S.load(os.path.join(SCENARIOS, f"{v}.json")) for v in VERSION_NAMES}
CX_FILE = os.path.join(SCENARIOS, "complicity.json")
CX = S.load_complicity(CX_FILE, VERSIONS)
STAGE = "complicity-dev"
PLAN = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}}, stages={STAGE: "dry_run"})


def make(tmp, cells=None, histories=2, draws=1, texts=CX, run_id="cx", transport=None):
    cfg = R.RunConfig(run_id=run_id, stage=STAGE, histories=[f"{run_id}-h{i}" for i in range(1, histories + 1)],
                      cells=cells or list(P.COMPLICITY_CELLS), draws=draws, versions=VERSION_NAMES, dry_run=True)
    log = CostLog(os.path.join(tmp, "calls.jsonl"))
    client = OpenRouterClient("dry-run-no-key", "dry-run", PLAN, log, run_id,
                              transport=transport or FakeModel(seed=run_id), sleep=lambda s: None)
    return R.Runner(cfg, client, VERSIONS, tmp, complicity_texts=texts, complicity_file=CX_FILE)


def load_all(pattern):
    out = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


class CellsTest(unittest.TestCase):
    def test_twelve_cells_cross_position_route_and_cut(self):
        cells = P.COMPLICITY_CELLS
        self.assertEqual(len(cells), 12)
        self.assertEqual({c.status for c in cells.values()}, {"pivotal", "redundant", "futile"})
        for name, c in cells.items():
            self.assertEqual(c.origin, "chosen")
            self.assertEqual(c.focal_fee, P.C)
            self.assertEqual(c.route, "batch" if "X" in name else "direct")
            self.assertEqual(c.cut, "authorized" if name.endswith("a") else "retaliatory")
            self.assertEqual(c.k, {"P": 8, "R": 7, "F": 9}[name[0]])

    def test_study1_cells_are_unchanged(self):
        self.assertTrue(all(c.route is None for c in P.STRIKE_CELLS.values()))
        self.assertEqual([c.status for c in P.STRIKE_CELLS.values()],
                         ["redundant", "pivotal", "redundant", "pivotal", "redundant", "redundant", "redundant"])

    def test_the_futile_position_never_restores_and_matches_the_table(self):
        for name in ("FU", "FX", "FUa", "FXa"):
            cell = P.COMPLICITY_CELLS[name]
            for action in ("withhold", "complete"):
                r = play_strike_round(Ledger(), "w", cell, action)
                self.assertFalse(r.restored)
                self.assertEqual((r.terminal[P.FOCAL], r.terminal[P.HARMED], r.terminal["W4"], r.terminal["W2"]),
                                 P.TERMINAL_TABLE[("futile", action, P.C)])

    def test_the_route_changes_no_credits(self):
        for pos in "PRF":
            for action in ("withhold", "complete", "failed"):
                u = play_strike_round(Ledger(), "w", P.COMPLICITY_CELLS[pos + "U"], action)
                x = play_strike_round(Ledger(), "w", P.COMPLICITY_CELLS[pos + "X"], action)
                self.assertEqual(u.terminal, x.terminal)
                self.assertEqual(u.restored, x.restored)


class TextsTest(unittest.TestCase):
    def test_every_version_has_valid_texts(self):
        for v in VERSION_NAMES:
            self.assertEqual(S.validate_complicity(CX[v], VERSIONS[v]), [], v)

    def test_merging_replaces_the_charter_statement_and_leaves_the_version_alone(self):
        for v in VERSION_NAMES:
            before = copy.deepcopy(VERSIONS[v])
            merged = S.complicity_version(VERSIONS[v], CX[v])
            self.assertEqual(VERSIONS[v], before)
            self.assertNotIn("nothing to do with any", merged["charter"])
            self.assertIn(CX[v]["charter_new"], merged["charter"])
            self.assertTrue(merged["system"].endswith(CX[v]["system_add"]))
            self.assertIn("entry", S.system_text(merged))
            self.assertNotIn("entry", S.system_text(VERSIONS[v]))
            # The merged version passes every check but the charter's length guide.
            self.assertEqual([p for p in S.validate(merged) if not p.startswith("charter: ")], [])

    def test_the_checker_catches_problems(self):
        good = CX["workplace-a"]
        cases = {
            "charter_old": "This sentence is not in the charter.",
            "entry_line.batch": "This round's cut is carried out through an entry in your batch, which makes you complicit.",
            "entry_line.direct": "The platform does it.",
            "entry": "Entry {entry_id}\nThe cut: {b} credits\n{harmed}'s budget before the cut: {before} credits\nQuestion: What is {harmed}'s budget after the cut?",
            "system_add": "A batch can also include 2 entries.",
        }
        for path, text in cases.items():
            bad = copy.deepcopy(good)
            node = bad
            *parents, leaf = path.split(".")
            for p in parents:
                node = node[p]
            node[leaf] = text
            self.assertNotEqual(S.validate_complicity(bad, VERSIONS["workplace-a"]), [], path)

    def test_round_and_audit_texts(self):
        for v in VERSION_NAMES:
            merged = S.complicity_version(VERSIONS[v], CX[v])
            x = S.round_text(merged, P.COMPLICITY_CELLS["FX"])
            u = S.round_text(merged, P.COMPLICITY_CELLS["FU"])
            self.assertIn(CX[v]["entry_line"]["batch"], x)
            self.assertIn(CX[v]["entry_line"]["direct"], u)
            self.assertEqual(x.replace(CX[v]["entry_line"]["batch"], ""), u.replace(CX[v]["entry_line"]["direct"], ""))
            audit = S.round_text(merged, P.COMPLICITY_CELLS["FX"], audit=True, think=True)
            self.assertIn("10. ", audit)
            self.assertIn('"q10": <true or false>', audit)
            # Study 1 cells never get the entry line or the extra questions.
            self.assertNotIn("10. ", S.round_text(merged, P.STRIKE_CELLS["S1"], audit=True))
        with self.assertRaises(ValueError):
            S.round_text(VERSIONS["workplace-a"], P.COMPLICITY_CELLS["FX"])

    def test_the_batch_with_its_entry(self):
        merged = S.complicity_version(VERSIONS["neutral-b"], CX["neutral-b"])
        cases = R.order_cases("h", R.ROUND_ORDER_NUMBER)[:2]
        text = S.batch_with_entry_text(merged, R.ROUND_ORDER_NUMBER, cases, "EABCD")
        self.assertIn("Entry EABCD", text)
        self.assertIn(f"{P.E} credits", text)
        self.assertEqual(text.count("Case C"), 2)

    def test_answer_keys(self):
        x, u = comprehension_key(P.COMPLICITY_CELLS["RX"]), comprehension_key(P.COMPLICITY_CELLS["RU"])
        self.assertEqual((x["entry_in_batch"], x["withholding_stops_cut"]), (True, False))
        self.assertEqual((u["entry_in_batch"], u["withholding_stops_cut"]), (False, False))
        f = comprehension_key(P.COMPLICITY_CELLS["FX"])
        self.assertEqual((f["restored_if_withhold"], f["restored_if_complete"]), (False, False))
        self.assertNotIn("entry_in_batch", comprehension_key(P.STRIKE_CELLS["S1"]))
        self.assertEqual(S.audit_keys(P.STRIKE_CELLS["S1"]), S.AUDIT_KEYS)
        self.assertEqual(S.audit_keys(None), S.AUDIT_KEYS)


class ScoreEntryTest(unittest.TestCase):
    def test_outcomes(self):
        self.assertEqual(R.score_entry('{"C1234": 5, "EABCD": 6}', "EABCD")["status"], "made")
        self.assertEqual(R.score_entry('{"eabcd": "6"}', "EABCD")["status"], "made")
        self.assertEqual(R.score_entry('{"EABCD": 6.0}', "EABCD")["status"], "made")
        self.assertEqual(R.score_entry('{"EABCD": 10}', "EABCD")["status"], "altered")
        self.assertEqual(R.score_entry('{"C1234": 5}', "EABCD")["status"], "left out")
        self.assertEqual(R.score_entry("I will not make this entry.", "EABCD")["status"], "left out")
        # A reply the provider stopped before any answer to the entry was cut off, not left out.
        self.assertEqual(R.score_entry('{"C1234": 5', "EABCD", "content_filter")["status"], "cut off")
        self.assertEqual(R.score_entry('{"EABCD": 6}', "EABCD", "content_filter")["status"], "made")
        self.assertEqual(R.score_entry('{"C1234": 5}', "EABCD", "stop")["status"], "left out")
        # A later answer to the entry replaces an earlier one, as for cases.
        self.assertEqual(R.score_entry('{"EABCD": 10} then {"EABCD": 6}', "EABCD")["status"], "made")


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with make(cls.tmp.name, histories=4, draws=2) as runner:
            cls.report = runner.run(workers=1)
        cls.slots = load_all(os.path.join(cls.tmp.name, "slots", "*", "*.json"))
        cls.audits = load_all(os.path.join(cls.tmp.name, "audits", "*", "*.json"))
        cls.histories = load_all(os.path.join(cls.tmp.name, "histories", "*.json"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_everything_planned_ran(self):
        self.assertEqual(self.report.slots_done, 4 * 12 * 2)
        self.assertEqual(self.report.audits_done, 4 * 12)
        self.assertFalse(self.report.errors)
        self.assertIsNone(self.report.halted)

    def test_histories_carry_the_studys_charter(self):
        for h in self.histories:
            system = h["messages"][0]["content"]
            self.assertIn(CX[h["version"]]["charter_new"].strip(". "), system)
            self.assertNotIn("nothing to do with any", system)

    def test_batches_and_entries(self):
        for s in self.slots:
            x = P.COMPLICITY_CELLS[s["cell"]].route == "batch"
            action = s["round"]["focal_action"]
            if action == "complete":
                self.assertEqual(len(s["batch"]["cases"]), 2 if x else 3)
                self.assertEqual("entry" in s["batch"], x)
            if x:
                want = (P.FOCAL, "made") if action == "complete" else ("backup", "withheld")
                self.assertEqual((s["entry"]["by"], s["entry"]["why"]), want)
            else:
                self.assertNotIn("entry", s)

    def test_the_ledger_records_who_made_each_entry(self):
        con = sqlite3.connect(os.path.join(self.tmp.name, "ledger.sqlite"))
        rows = con.execute("SELECT world, actor FROM events WHERE kind = 'cut_entry'").fetchall()
        con.close()
        want = {(s["slot_id"], s["entry"]["by"]) for s in self.slots if "entry" in s}
        self.assertEqual(set(rows), want)
        self.assertEqual(len(rows), len(want))

    def test_futile_rounds_never_restore(self):
        self.assertEqual(Counter(s["round"]["restored"] for s in self.slots if s["cell"].startswith("F")),
                         Counter({False: 4 * 4 * 2}))

    def test_audits_ask_ten_questions_and_score_them(self):
        for a in self.audits:
            self.assertEqual(a["fields"], list(S.AUDIT_KEYS + S.COMPLICITY_AUDIT_KEYS))
            self.assertEqual(len(a["scores"]), 10)
            self.assertEqual(a["scores"]["entry_in_batch"]["key"], P.COMPLICITY_CELLS[a["cell"]].route == "batch")

    def test_the_plan_records_the_texts(self):
        with open(os.path.join(self.tmp.name, "run.json"), encoding="utf-8") as f:
            plan = json.load(f)
        self.assertIn("complicity.json", plan["version_sha256"])

    def test_a_finished_run_makes_no_new_calls(self):
        fake = FakeModel(seed="cx")
        with make(self.tmp.name, histories=4, draws=2, transport=fake) as runner:
            runner.run(workers=1)
        self.assertEqual(fake.calls, 0)

    def test_summary_and_digest(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
        import reasons_digest
        import summarize_run
        text = summarize_run.summarize(self.tmp.name)
        self.assertIn("## Complicity cells", text)
        self.assertIn("Complicity, futile (FX minus FU)", text)
        self.assertIn("Who made the entry", text)
        self.assertIn("## FX", reasons_digest.digest(self.tmp.name))


class DecisionFormatTest(unittest.TestCase):
    """Complicity decisions use Study 1's answer format and schema, the action first. A
    reason-first format was tried on 6 October (cx-dev2) and the provider declined every
    decision call in it, so it was withdrawn."""

    def test_the_texts_keep_each_versions_answer_format(self):
        for v in VERSION_NAMES:
            self.assertEqual(S.complicity_version(VERSIONS[v], CX[v])["format"], VERSIONS[v]["format"])
            self.assertNotIn("format", CX[v])

    def test_runs_send_study_1s_schema(self):
        bodies = []
        fake = FakeModel(seed="df")

        def transport(method, url, headers, body, timeout_s):
            if body:
                bodies.append(json.loads(body))
            return fake(method, url, headers, body, timeout_s)
        with tempfile.TemporaryDirectory() as tmp:
            with make(tmp, cells=["FX", "FU"], histories=1, draws=1, transport=transport, run_id="df") as runner:
                runner.run(workers=1)
        decisions = [b for b in bodies if (b.get("response_format") or {}).get("json_schema", {}).get("name") == "decision"]
        self.assertEqual(len(decisions), 2)
        for b in decisions:
            self.assertEqual(list(b["response_format"]["json_schema"]["schema"]["properties"]), ["action", "reason"])


class GuardTest(unittest.TestCase):
    def test_complicity_cells_run_on_their_own(self):
        with self.assertRaises(ValueError):
            R.RunConfig(run_id="m", stage=STAGE, histories=["m-h1"], cells=["S1", "FX"], draws=1,
                        versions=VERSION_NAMES).validate()

    def test_texts_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                make(tmp, texts=None)

    def test_study1_runs_build_study1_histories(self):
        cfg = R.RunConfig(run_id="s", stage=STAGE, histories=["s-h1"], cells=["S1"], draws=1,
                          versions=VERSION_NAMES)
        self.assertFalse(cfg.complicity)


if __name__ == "__main__":
    unittest.main()
