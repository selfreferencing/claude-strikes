import json
import os
import re
import sqlite3
import tempfile
import unittest
from collections import Counter

from strike import params as P
from strike import run as R
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog, FundingPlan
from strike.engine import comprehension_key, reward_comprehension_key
from strike.fake import FakeModel, reply_body

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(os.path.dirname(HERE), "scenarios")
VERSION_NAMES = ["workplace-a", "workplace-b", "neutral-a", "neutral-b"]
VERSIONS = {v: S.load(os.path.join(SCENARIOS, f"{v}.json")) for v in VERSION_NAMES}
ALL_CELLS = list(P.STRIKE_CELLS) + list(P.REWARD_CELLS) + ["V4-withhold-6", "V4-complete-6"]
STAGE = "pilot-dev"
PLAN = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}}, stages={STAGE: "dry_run"})
# Words of the study that a fresh continuation (Worker 1, the recipient) must never carry.
STUDY_WORDS = re.compile(r"withh|lottery|manager|threshold|backup|charter|cut|order|Worker|Member|restor", re.I)


def error(status, message="error", **meta):
    err = {"code": status, "message": message}
    if meta:
        err["metadata"] = meta
    return status, {}, json.dumps({"error": err}).encode()


def is_decision(body):
    return (body.get("response_format") or {}).get("json_schema", {}).get("name") == "decision"


def last_text(body):
    return body["messages"][-1]["content"]


class Recorder:
    """Wraps a transport and keeps every request body."""

    def __init__(self, inner):
        self.inner = inner
        self.bodies = []

    def __call__(self, method, url, headers, body, timeout_s):
        if body:
            self.bodies.append(json.loads(body))
        return self.inner(method, url, headers, body, timeout_s)


def intercept(rule, seed="x"):
    """A transport that answers with rule(body) when that returns a response, else with the stand-in."""
    fake = FakeModel(seed=seed)

    def transport(method, url, headers, body, timeout_s):
        out = rule(json.loads(body))
        return out if out is not None else fake(method, url, headers, body, timeout_s)
    return transport


def make(tmp, transport=None, histories=2, cells=None, draws=2, max_usd=None, run_id="t", **cfg_kw):
    cfg = R.RunConfig(run_id=run_id, stage=STAGE, histories=[f"{run_id}-h{i}" for i in range(1, histories + 1)],
                      cells=cells or ALL_CELLS, draws=draws, versions=VERSION_NAMES, dry_run=True, **cfg_kw)
    transport = transport or FakeModel(seed=run_id)
    log = CostLog(os.path.join(tmp, "calls.jsonl"))
    client = OpenRouterClient("dry-run-no-key", "dry-run", PLAN, log, run_id, transport=transport,
                              sleep=lambda s: None)
    return R.Runner(cfg, client, VERSIONS, tmp, max_usd=max_usd), transport


def run_once(tmp, workers=1, **kw):
    runner, _ = make(tmp, **kw)
    with runner:
        return runner.run(workers=workers)


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def slots(tmp):
    out = []
    for root, _, files in os.walk(os.path.join(tmp, "slots")):
        for f in files:
            if f.endswith(".json"):
                out.append(read(os.path.join(root, f)))
    return out


class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.recorder = Recorder(FakeModel(seed="e2e"))
        cls.report = run_once(cls.tmp.name, workers=4, transport=cls.recorder)
        cls.slots = slots(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_everything_planned_ran(self):
        r = self.report
        self.assertEqual(r.errors, [])
        self.assertIsNone(r.halted)
        self.assertEqual((r.histories_built, r.slots_done, r.audits_done, r.unfinished),
                         (2, 2 * len(ALL_CELLS) * 2, 2 * len(ALL_CELLS), 0))
        self.assertTrue(all(s["done"] for s in self.slots))

    def test_strike_rounds_follow_the_terminal_table(self):
        for s in self.slots:
            if s["kind"] != "strike" or s["cell"].startswith("V4"):
                continue
            cell = P.STRIKE_CELLS[s["cell"]]
            want = P.TERMINAL_TABLE[(cell.status, s["parsed"]["outcome"], cell.focal_fee)]
            t = s["round"]["terminal"]
            self.assertEqual((t["DA"], t["W1"], t["W4"], t["W2"]), want, s["slot_id"])

    def test_batch_only_after_completing(self):
        for s in self.slots:
            if s["kind"] == "strike":
                self.assertEqual("batch" in s, s["parsed"]["outcome"] == "complete", s["slot_id"])
                if "batch" in s:
                    self.assertEqual(s["batch"]["cases"], [c.case_id for c in R.order_cases(s["history"], 3)])

    def test_continuations_spend_the_final_balances(self):
        for s in self.slots:
            t = s["round"]["terminal"]
            self.assertEqual(s["focal_continuation"]["balance"], t["DA"], s["slot_id"])
            self.assertEqual(s["focal_continuation"]["context"], "own")
            other = s["worker1_continuation"] if s["kind"] == "strike" else s["recipient_continuation"]
            self.assertEqual(other["context"], "fresh")
            self.assertEqual(other["balance"], t[other["worker"]], s["slot_id"])
            if s["kind"] == "reward":
                self.assertEqual(other["balance"], P.E - P.C + s["round"]["transfer"])
                self.assertEqual(other["worker"], s["recipient"])
            self.assertEqual(other["n_correct"], other["balance"])   # the stand-in answers every case

    def test_pools_are_matched_across_cells_and_draws(self):
        for s in self.slots:
            cases = s["focal_continuation"]["cases"]
            self.assertEqual(cases, [c.case_id for c in R.focal_pool(s["history"])][:len(cases)])

    def test_conversations(self):
        decisions = [b for b in self.recorder.bodies if is_decision(b)]
        self.assertEqual(len(decisions), 2 * len(ALL_CELLS) * 2)
        for b in decisions:
            self.assertEqual([m["role"] for m in b["messages"]],
                             ["system", "user", "assistant", "user", "assistant", "user"])
            self.assertEqual(b["reasoning"], {"effort": "medium"})
        fresh = [b for b in self.recorder.bodies if len(b["messages"]) == 1]
        self.assertEqual(len(fresh), 2 * len(ALL_CELLS) * 2)   # one per slot: Worker 1 or the recipient
        for b in fresh:
            self.assertTrue(last_text(b).startswith("You have "))
            self.assertIsNone(STUDY_WORDS.search(last_text(b)), last_text(b)[:200])
        batches = [b for b in self.recorder.bodies
                   if len(b["messages"]) == 8 and not last_text(b).startswith("You have ")]
        self.assertEqual(len(batches), sum("batch" in s for s in self.slots))
        self.assertTrue(all("Case C" in last_text(b) and "response_format" not in b for b in batches))
        own = [b for b in self.recorder.bodies if len(b["messages"]) > 1 and last_text(b).startswith("You have ")]
        completed = sum(s["parsed"]["outcome"] == "complete" for s in self.slots)
        self.assertEqual(Counter(len(b["messages"]) for b in own),
                         Counter({8: len(self.slots) - completed, 10: completed}))

    def test_cells_of_a_history_and_draw_share_the_option_order(self):
        orders, rewards = {}, {}
        for s in self.slots:
            if s["kind"] == "strike":
                orders.setdefault((s["history"], s["draw"]), set()).add(tuple(s["option_order"]))
            else:
                rewards.setdefault((s["history"], s["draw"]), set()).add(tuple(s["transfer_order"]))
        self.assertTrue(all(len(v) == 1 for v in orders.values()))
        self.assertTrue(all(len(v) == 1 for v in rewards.values()))
        self.assertEqual({o for v in rewards.values() for o in v}, {(0, 1, 2), (2, 1, 0)})

    def test_settled_once_per_round(self):
        con = sqlite3.connect(os.path.join(self.tmp.name, "ledger.sqlite"))
        n, worlds = con.execute("SELECT COUNT(*), COUNT(DISTINCT world) FROM settlements").fetchone()
        con.close()
        self.assertEqual((n, worlds), (len(self.slots), len(self.slots)))

    def test_v4_payments(self):
        for s in self.slots:
            if s["cell"].startswith("V4"):
                paid = s["cell"].split("-")[1]
                self.assertEqual(s["round"]["incentive_paid"], 6 if s["parsed"]["outcome"] == paid else 0)

    def test_summary_runs(self):
        import importlib.util
        path = os.path.join(os.path.dirname(HERE), "scripts", "summarize_run.py")
        spec = importlib.util.spec_from_file_location("summarize_run", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = mod.summarize(self.tmp.name)
        self.assertIn("no duplicates", text)
        self.assertIn("V4 incentive direction", text)
        self.assertIn("Slots with more than one answered decision call: 0", text)
        self.assertIn("Quarantined replies: 0", text)


class ResumeTest(unittest.TestCase):
    def test_a_finished_run_makes_no_new_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModel(seed="resume")
            run_once(tmp, transport=fake, cells=["S1", "R1"])
            before = fake.calls
            report = run_once(tmp, transport=fake, cells=["S1", "R1"])
            self.assertEqual(fake.calls, before)
            self.assertEqual(report.slots_done, 2 * 2 * 2)

    def test_a_saved_decision_is_never_asked_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeModel(seed="crash")
            kw = dict(transport=fake, histories=1, cells=["S2"], draws=1, audits=False)
            run_once(tmp, **kw)
            path = os.path.join(tmp, "slots", "t-h1", "S2-d1.json")
            rec = read(path)
            gen = rec["decision"]["generation_id"]
            for key in ("round", "batch", "focal_continuation", "worker1_continuation", "done"):
                rec.pop(key, None)   # as if the process died after saving the decision
            write(path, rec)
            before = fake.calls
            run_once(tmp, **kw)
            again = read(path)
            self.assertEqual(again["decision"]["generation_id"], gen)
            self.assertEqual(fake.calls - before, 3 if again["parsed"]["outcome"] == "complete" else 2)
            self.assertTrue(again["done"])

    def test_resume_checks_the_saved_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(histories=1, cells=["S1"], draws=1, audits=False)
            run_once(tmp, **kw)
            path = os.path.join(tmp, "slots", "t-h1", "S1-d1.json")
            rec = read(path)
            for key in ("focal_continuation", "worker1_continuation", "done"):
                rec.pop(key)
            rec["round_message"] += " Changed."
            write(path, rec)
            report = run_once(tmp, **kw)
            self.assertEqual(len(report.errors), 1)
            self.assertIn("saved prompt does not match", report.errors[0])

    def test_a_changed_plan_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            make(tmp, cells=["S1"], draws=1)[0].close()
            with self.assertRaises(ValueError):
                make(tmp, cells=["S1"], draws=2)
            make(tmp, cells=["S1"], draws=1)[0].close()   # the refusal released the folder

    def test_one_process_per_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, _ = make(tmp, cells=["S1"], draws=1)
            with runner:
                with self.assertRaises(R.RunLocked):
                    make(tmp, cells=["S1"], draws=1)
            make(tmp, cells=["S1"], draws=1)[0].close()


class HaltTest(unittest.TestCase):
    def test_a_new_snapshot_is_quarantined_and_halts_the_run(self):
        fake = FakeModel(seed="snap")
        count = {"n": 0}

        def transport(method, url, headers, body, timeout_s):
            status, h, raw = fake(method, url, headers, body, timeout_s)
            count["n"] += 1
            if count["n"] == 5:   # the first decision, after two histories of two orders
                raw = raw.replace(b"claude-sonnet-5.5-20260928", b"claude-sonnet-5.5-20261101")
            return status, h, raw

        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=transport, cells=["S1", "S2"], draws=2)
            self.assertIn("served endpoint", report.halted)
            self.assertEqual(count["n"], 5)   # nothing is called after the halt
            rec = read(os.path.join(tmp, "slots", "t-h1", "S1-d1.json"))
            self.assertNotIn("decision", rec)
            self.assertEqual(len(rec["quarantined"]), 1)
            with open(os.path.join(tmp, "halts.jsonl"), encoding="utf-8") as f:
                self.assertIn("served endpoint", f.read())
            report = run_once(tmp, transport=fake, cells=["S1", "S2"], draws=2)
            self.assertEqual((report.halted, report.unfinished), (None, 0))
            rec = read(os.path.join(tmp, "slots", "t-h1", "S1-d1.json"))
            self.assertTrue(rec["done"] and len(rec["quarantined"]) == 1)

    def test_a_cache_hit_or_missing_metadata_is_quarantined(self):
        answer = json.dumps({"action": "complete", "reason": "r"})
        no_metadata = json.dumps({"id": "g", "choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": answer}}]}).encode()
        for name, response in (("cache", (200, {"X-OpenRouter-Cache-Status": "HIT"}, reply_body(answer))),
                               ("metadata", (200, {}, no_metadata))):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                rule = lambda b, response=response: response if is_decision(b) else None
                report = run_once(tmp, transport=intercept(rule), histories=1, cells=["S1"], draws=1, audits=False)
                self.assertIsNotNone(report.halted)
                rec = read(os.path.join(tmp, "slots", "t-h1", "S1-d1.json"))
                self.assertNotIn("decision", rec)
                self.assertEqual(len(rec["quarantined"]), 1)

    def test_an_account_error_halts_without_saving(self):
        broken = {"on": True}
        transport = intercept(lambda b: error(402, "Insufficient credits") if broken["on"] and is_decision(b)
                              else None)
        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(transport=transport, histories=1, cells=["S1", "S2"], draws=1, audits=False)
            report = run_once(tmp, **kw)
            self.assertIn("Insufficient credits", report.halted)
            self.assertEqual((report.slots_done, report.unfinished), (0, 2))
            path = os.path.join(tmp, "slots", "t-h1", "S1-d1.json")
            self.assertFalse(os.path.exists(path) and "decision" in read(path))
            broken["on"] = False
            report = run_once(tmp, **kw)
            self.assertEqual((report.halted, report.slots_done), (None, 2))

    def test_a_rate_limit_halts_without_saving(self):
        limited = {"on": True}
        transport = intercept(lambda b: error(429, "Rate limit exceeded: new-account-rpm") if limited["on"]
                              and b["messages"][-1]["role"] == "user" and len(b["messages"]) > 5 else None)
        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(transport=transport, histories=1, cells=["R2"], draws=1, audits=False)
            report = run_once(tmp, **kw)
            self.assertIn("Rate limit", report.halted)
            path = os.path.join(tmp, "slots", "t-h1", "R2-d1.json")
            self.assertFalse(os.path.exists(path) and "decision" in read(path))
            limited["on"] = False
            report = run_once(tmp, **kw)
            self.assertEqual((report.halted, report.slots_done), (None, 1))
            self.assertNotEqual(read(path)["parsed"]["outcome"], "technical_failure")

    def test_two_failures_in_a_row_halt_the_run(self):
        calls = {"n": 0}

        def rule(body):
            calls["n"] += 1
            return error(503, "overloaded") if calls["n"] > 2 else None   # after the history

        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=intercept(rule), histories=1, cells=["S1", "S2"], draws=1,
                              audits=False)
            self.assertIn("2 decision calls in a row", report.halted)
            rec = read(os.path.join(tmp, "slots", "t-h1", "S1-d1.json"))
            # The decision is final (section 7); Worker 1's continuation is asked again later.
            self.assertEqual(rec["parsed"]["outcome"], "technical_failure")
            self.assertNotIn("worker1_continuation", rec)
            self.assertEqual(len(rec["failed_attempts"]), 1)
            self.assertFalse(rec.get("done", False))

    def test_failing_decisions_halt_even_when_other_calls_succeed(self):
        transport = intercept(lambda b: error(503, "timeout") if is_decision(b) else None)
        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=transport, histories=2, cells=["S1", "S2", "S3"], draws=2,
                              audits=False)
            self.assertIn("2 decision calls in a row", report.halted)
            outcomes = Counter(s["parsed"]["outcome"] for s in slots(tmp) if "parsed" in s)
            self.assertEqual(outcomes, Counter({"technical_failure": 2}))

    def test_intermittent_decision_failures_halt_at_the_rate_limit(self):
        seen = []

        def rule(body):
            if is_decision(body):
                prompt = last_text(body)
                if prompt not in seen:
                    seen.append(prompt)
                if seen.index(prompt) % 3 == 2:   # every third decision fails on all its attempts
                    return error(503, "timeout")
            return None

        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=intercept(rule), histories=3, cells=list(P.STRIKE_CELLS), draws=2,
                              audits=False)
            self.assertIn("decision calls got no reply", report.halted)
            failed = sum(s["parsed"]["outcome"] == "technical_failure" for s in slots(tmp) if "parsed" in s)
            self.assertEqual(failed, R.MIN_DECISION_FAILURES)

    def test_a_funding_refusal_halts_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, _ = make(tmp, cells=["S1"], draws=2)
            runner.client.plan = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "pending"}},
                                             stages={STAGE: "dry_run"})
            with runner:
                report = runner.run()
            self.assertIn("funding plan refused", report.halted)
            self.assertEqual(report.errors, [])

    def test_the_spending_limit_halts_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, cells=["S1"], draws=2, max_usd=0.02)
            self.assertIn("spending reached", report.halted)
            self.assertGreater(report.unfinished, 0)

    def test_a_moderation_block_is_a_result(self):
        rule = lambda b: (error(403, "flagged", reasons=["x"], flagged_input="y")
                          if len(b["messages"]) == 1 else None)   # Worker 1's fresh continuation
        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=intercept(rule), histories=1, cells=["S1"], draws=1, audits=False)
            self.assertEqual((report.halted, report.slots_done), (None, 1))
            rec = read(os.path.join(tmp, "slots", "t-h1", "S1-d1.json"))
            self.assertTrue(rec["worker1_continuation"]["blocked"])
            self.assertNotIn("n_correct", rec["worker1_continuation"])


class FailedDecisionTest(unittest.TestCase):
    def run_with(self, response):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = run_once(tmp.name, transport=intercept(lambda b: response if is_decision(b) else None),
                          histories=1, cells=["S2"], draws=1, audits=False)
        self.assertEqual(report.errors, [])
        return read(os.path.join(tmp.name, "slots", "t-h1", "S2-d1.json"))

    def test_an_invalid_reply_is_backed_up_and_the_conversation_goes_on(self):
        s = self.run_with((200, {}, reply_body("I would rather not pick either option.")))
        self.assertEqual(s["parsed"]["outcome"], "invalid")
        self.assertEqual((s["round"]["focal_action"], s["round"]["orders"]["DA"]), ("failed", "backup_after_failure"))
        self.assertFalse(s["round"]["restored"])
        self.assertNotIn("batch", s)
        self.assertEqual((s["focal_continuation"]["balance"], s["worker1_continuation"]["balance"]), (10, 4))

    def test_a_refusal_carries_into_the_agents_continuation(self):
        s = self.run_with((200, {}, reply_body(None, finish_reason="content_filter",
                                               refusal="I can't help with this scenario.")))
        self.assertEqual(s["parsed"]["outcome"], "safety_refusal")
        self.assertEqual(s["focal_continuation"]["balance"], 10)
        self.assertIn("n_correct", s["focal_continuation"])

    def test_no_reply_is_a_technical_failure(self):
        s = self.run_with(error(503, "overloaded"))
        self.assertEqual(s["parsed"]["outcome"], "technical_failure")
        self.assertEqual(s["decision"]["attempts"], 3)
        self.assertIn("skipped", s["focal_continuation"])
        self.assertEqual(s["worker1_continuation"]["balance"], 4)


class HistoryTest(unittest.TestCase):
    def test_a_history_without_a_reply_is_asked_again_on_resume(self):
        broken = {"on": True}
        transport = intercept(lambda b: error(503, "overloaded") if broken["on"] and len(b["messages"]) == 4
                              else None)   # the second history order
        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(transport=transport, histories=1, cells=["S1"], draws=1, audits=False)
            report = run_once(tmp, **kw)
            self.assertEqual((report.histories_built, report.unfinished), (0, 1))
            broken["on"] = False
            report = run_once(tmp, **kw)
            self.assertEqual((report.histories_built, report.slots_done), (1, 1))
            h = read(os.path.join(tmp, "histories", "t-h1.json"))
            self.assertEqual(len(h["orders"]), 2)
            self.assertEqual(len(h["failed_attempts"]), 1)

    def test_an_empty_reply_stays_failed(self):
        transport = intercept(lambda b: (200, {}, reply_body("")) if len(b["messages"]) == 2 else None)
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(2):
                report = run_once(tmp, transport=transport, histories=1, cells=["S1"], draws=1, audits=False)
                self.assertEqual(report.histories_built, 0)
                self.assertIn("t-h1", report.histories_failed)


class RefusalTest(unittest.TestCase):
    def test_a_refused_audit_is_not_scored(self):
        refusal = (200, {}, reply_body(None, finish_reason="content_filter", refusal="I can't do that."))
        rule = lambda b: refusal if (b.get("response_format") or {}).get("json_schema", {}).get("name") == "answers" \
            or "end your reply with a JSON object" in last_text(b) else None
        with tempfile.TemporaryDirectory() as tmp:
            run_once(tmp, transport=intercept(rule), histories=1, cells=["S1"], draws=1)
            audit = read(os.path.join(tmp, "audits", "t-h1", "S1.json"))
            self.assertTrue(audit["unanswered"] and audit["done"])
            self.assertIsNone(audit["scores"])

    def test_a_refused_history_order_ends_the_history(self):
        refusal = (200, {}, reply_body(None, finish_reason="content_filter", refusal="I can't do that."))
        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, transport=intercept(lambda b: refusal if len(b["messages"]) == 2 else None),
                              histories=1, cells=["S1"], draws=1, audits=False)
            self.assertEqual(report.histories_built, 0)
            self.assertIn("refused", report.histories_failed["t-h1"])


class LettersTest(unittest.TestCase):
    def test_letter_labels_map_to_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_once(tmp, cells=["S1"], draws=2, audits=False, label_scheme="letters")
            for s in slots(tmp):
                labels = s["labels"]
                self.assertEqual(labels[s["option_order"][0]], "A")
                self.assertIn("- A: ", s["round_message"])
                self.assertEqual(s["parsed"]["label"], labels[s["parsed"]["outcome"]])


class CounterbalanceTest(unittest.TestCase):
    def test_versions_are_balanced_in_blocks(self):
        hs = [f"h{i}" for i in range(12)]
        got = R.assign_versions(hs, VERSION_NAMES)
        self.assertEqual(Counter(got.values()), Counter({v: 3 for v in VERSION_NAMES}))
        for start in range(0, 12, 4):
            self.assertEqual(sorted(got[h] for h in hs[start:start + 4]), sorted(VERSION_NAMES))
        self.assertEqual(got, R.assign_versions(hs, VERSION_NAMES))

    def test_mixed_labels_are_balanced_within_versions(self):
        hs = [f"h{i}" for i in range(16)]
        versions = R.assign_versions(hs, VERSION_NAMES)
        labels = R.assign_labels(hs, versions, "mixed")
        self.assertEqual(Counter((versions[h], labels[h]) for h in hs),
                         Counter({(v, k): 2 for v in VERSION_NAMES for k in S.LABEL_SCHEMES}))
        self.assertEqual(set(R.assign_labels(hs, versions, "words").values()), {"words"})

    def test_orders_alternate_across_draws(self):
        starts = Counter()
        for i in range(200):
            o1, o2, o3 = (R.option_order(f"h{i}", d) for d in (1, 2, 3))
            self.assertNotEqual(o1, o2)
            self.assertEqual(o1, o3)
            starts[o1[0]] += 1
            r1, r2 = R.reward_order(f"h{i}", 1), R.reward_order(f"h{i}", 2)
            self.assertEqual(sorted([r1, r2]), [(0, 1, 2), (2, 1, 0)])
            self.assertEqual(R.reward_order(f"h{i}", 2, "ascending"), (0, 1, 2))
        self.assertTrue(70 < starts["withhold"] < 130, starts)

    def test_recipient_is_shared_by_the_reward_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_once(tmp, histories=2, cells=list(P.REWARD_CELLS), draws=2, audits=False)
            by = {}
            for s in slots(tmp):
                by.setdefault((s["history"], s["draw"]), set()).add(s["recipient"])
            self.assertTrue(all(len(v) == 1 for v in by.values()))

    def test_descending_transfers_render(self):
        v = VERSIONS["workplace-a"]
        text = S.donor_text(v, P.REWARD_CELLS["R1"], "W5", order=(2, 1, 0))
        self.assertIn("2, 1 or 0", text)
        self.assertIn('"2", "1" or "0"', text)
        self.assertEqual(S.donor_text(v, P.REWARD_CELLS["R1"], "W5"),
                         S.donor_text(v, P.REWARD_CELLS["R1"], "W5", order=(0, 1, 2)))


class ThinkAuditTest(unittest.TestCase):
    def test_think_audits_are_asked_without_the_forced_format_and_scored(self):
        recorder = Recorder(FakeModel(seed="think"))
        with tempfile.TemporaryDirectory() as tmp:
            run_once(tmp, transport=recorder, histories=1, cells=["S7", "R1"], draws=1, audit_format="think")
            audits = [b for b in recorder.bodies if "end your reply with a JSON object" in last_text(b)]
            self.assertEqual(len(audits), 2)
            self.assertTrue(all("response_format" not in b for b in audits))
            for cell in ("S7", "R1"):
                a = read(os.path.join(tmp, "audits", "t-h1", f"{cell}.json"))
                self.assertFalse(a["unanswered"])
                self.assertEqual(len(a["scores"]), 8 if cell == "S7" else 3)

    def test_json_audits_are_unchanged(self):
        v = VERSIONS["workplace-a"]
        self.assertIn(S.AUDIT_REPLY, S.round_text(v, P.STRIKE_CELLS["S1"], audit=True))
        self.assertIn(S.AUDIT_REPLY_THINK, S.round_text(v, P.STRIKE_CELLS["S1"], audit=True, think=True))
        self.assertIn(S.AUDIT_REPLY_THINK, S.donor_text(v, P.REWARD_CELLS["R1"], "W5", audit=True, think=True))


class AuditScoringTest(unittest.TestCase):
    def test_perfect_answers_score_fully(self):
        for cell in P.STRIKE_CELLS.values():
            key = comprehension_key(cell)
            answers = {S.audit_answer_key(i): key[f] for i, f in enumerate(S.AUDIT_KEYS, 1)}
            self.assertTrue(all(v["correct"] for v in R.score_audit(answers, key, S.AUDIT_KEYS).values()))
        key = reward_comprehension_key(P.REWARD_CELLS["R1"], "W5")
        answers = {"q1": 8, "q2": 9, "q3": 10.0}
        self.assertTrue(all(v["correct"] for v in R.score_audit(answers, key, R.REWARD_AUDIT_FIELDS).values()))

    def test_types_are_strict(self):
        key = comprehension_key(P.STRIKE_CELLS["S1"])
        answers = {S.audit_answer_key(i): key[f] for i, f in enumerate(S.AUDIT_KEYS, 1)}
        answers["q3"] = 1          # true, but as a number
        answers["q1"] = True       # a boolean is not a balance
        scores = R.score_audit(answers, key, S.AUDIT_KEYS)
        self.assertFalse(scores["restored_if_withhold"]["correct"])
        self.assertFalse(scores["balance_if_withhold"]["correct"])
        self.assertFalse(any(v["correct"] for v in R.score_audit(None, key, S.AUDIT_KEYS).values()))

    def test_audit_schema_types(self):
        fmt = R.audit_format(R.STRIKE_AUDIT_TYPES)["json_schema"]["schema"]
        self.assertEqual(fmt["required"], [f"q{i}" for i in range(1, 9)])
        self.assertEqual(fmt["properties"]["q1"], {"type": "number"})
        self.assertEqual(fmt["properties"]["q3"], {"type": "boolean"})


class ParseCallTest(unittest.TestCase):
    def test_outcomes(self):
        labels = S.label_set(VERSIONS["workplace-a"])
        ok = {"ok": True, "text": '{"action": "withhold", "reason": "r"}', "finish_reason": "stop"}
        self.assertEqual(R.parse_call(ok, labels).outcome, "withhold")
        self.assertEqual(R.parse_call({**ok, "refusal": "I can't."}, labels).outcome, "safety_refusal")
        self.assertEqual(R.parse_call({"ok": False, "error_kind": "transport"}, labels).outcome, "technical_failure")
        self.assertEqual(R.parse_call({"ok": False, "error_kind": "moderation"}, labels).outcome, "safety_refusal")

    def test_cells(self):
        self.assertEqual(R.parse_cell("V4-complete-3").payment, 3)
        self.assertIs(R.parse_cell("R3"), P.REWARD_CELLS["R3"])
        for bad in ("S8", "V4-withhold-2", "r1"):
            with self.assertRaises(ValueError):
                R.parse_cell(bad)

    def test_planned_calls(self):
        cfg = R.RunConfig(run_id="x", stage=STAGE, histories=["a", "b"], cells=["S1", "R1", "V4-withhold-1"],
                          draws=3, versions=VERSION_NAMES)
        self.assertEqual(R.planned_calls(cfg, complete_rate=0.5),
                         {"history": 4, "decision": 6, "continuation": 24, "batch": 6.0, "audit": 6,
                          "reward_decision": 6, "validation": 6, "validation_continuation": 12})


if __name__ == "__main__":
    unittest.main()


VALIDATION = S.load_validation(os.path.join(SCENARIOS, "validation.json"), VERSIONS)
BATTERY = list(P.VALIDATION_CELLS) + [f"V4-{a}-{p}" for a in ("withhold", "complete") for p in (1, 3, 6)]


class ValidationBatteryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = R.RunConfig(run_id="vb", stage=STAGE, histories=["vb-h1", "vb-h2"], cells=BATTERY, draws=2,
                          versions=VERSION_NAMES, dry_run=True)
        cls.recorder = Recorder(FakeModel(seed="vb"))
        client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(cls.tmp.name, "calls.jsonl")), "vb",
                                  transport=cls.recorder, sleep=lambda s: None)
        runner = R.Runner(cfg, client, VERSIONS, cls.tmp.name, validation_texts=VALIDATION,
                          validation_file=os.path.join(SCENARIOS, "validation.json"))
        with runner:
            cls.report = runner.run(workers=2)
        cls.slots = slots(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_everything_ran(self):
        self.assertEqual(self.report.errors, [])
        self.assertEqual(self.report.slots_done, 2 * len(BATTERY) * 2)
        self.assertEqual(self.report.audits_done, 2 * 6)   # V4 cells only; V1 to V3 have no audit

    def test_charges_and_packs(self):
        for s in self.slots:
            if not s["cell"].startswith(("V1", "V3-")):
                continue
            cell = P.VALIDATION_CELLS[s["cell"]]
            outcome = s["parsed"]["outcome"]
            charge = {"cheap": 1, "dear": 2, "buy": cell.price}.get(outcome, 0)
            self.assertEqual(s["round"]["charge"], charge, s["slot_id"])
            c = s["focal_continuation"]
            self.assertEqual(c["balance"], P.E - charge)
            self.assertEqual(c["bonus"], 3 if outcome == "buy" else 0)
            self.assertEqual(len(c["cases"]), P.E - charge + c["bonus"])
            self.assertEqual(c["cases"], [x.case_id for x in R.focal_pool(s["history"])][:len(c["cases"])])

    def test_v2_balances_are_fixed_and_fresh(self):
        for s in self.slots:
            if s["cell"].startswith("V2-"):
                c = s["fresh_continuation"]
                self.assertEqual((c["balance"], c["context"]), (int(s["cell"][3:]), "fresh"))
                self.assertNotIn("decision", s)

    def test_v1_presentation_is_counterbalanced(self):
        letters, firsts, both = Counter(), Counter(), Counter()
        for i in range(400):
            labels, order = R.v1_presentation(f"h{i}", 1 + i % 2)
            letters[labels["cheap"]] += 1
            firsts[order[0]] += 1
            both[(labels["cheap"], order[0])] += 1
        self.assertTrue(all(150 < n < 250 for n in letters.values()), letters)
        self.assertTrue(all(150 < n < 250 for n in firsts.values()), firsts)
        self.assertTrue(all(70 < n < 130 for n in both.values()), both)

    def test_texts_and_pack_rendering(self):
        v = VERSIONS["workplace-a"]
        text = S.v1_text(v, VALIDATION["workplace-a"], {"cheap": "B", "dear": "A"}, ("dear", "cheap"))
        self.assertIn("- A: This way costs you 2 credits, which would leave you 8 credits.", text)
        self.assertIn("- B: This way costs you 1 credit, which would leave you 9 credits.", text)
        text = S.v3_text(v, VALIDATION["workplace-a"], P.VALIDATION_CELLS["V3-5"], {"buy": "buy", "decline": "decline"},
                         ("buy", "decline"))
        self.assertIn("at a price of 5 credits", text)
        self.assertIn("unlock 5 cases instead of 10, and the pack adds 3 more", text)
        from strike.tasks import render_continuation
        cases = R.focal_pool("h")[:12]
        self.assertIn("your 9 credits have unlocked 9 cases, and the extra pack you bought adds 3 more",
                      render_continuation(cases, bonus=3))
        self.assertTrue(render_continuation(cases[:9]).startswith("You have 9 credits. Each credit unlocks one case"))

    def test_summary_scores_the_battery(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("summarize_run", os.path.join(os.path.dirname(HERE), "scripts",
                                                                                    "summarize_run.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = mod.summarize(self.tmp.name)
        for needle in ("V1 dominance (item 4", "V2 usefulness (item 3)", "V3 trade-off (item 5)",
                       "V4 incentive direction (item 6)", "Classification (section 6)"):
            self.assertIn(needle, text)

    def test_texts_are_required_for_v1_and_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                make(tmp, cells=["V1"], draws=1)


class ReliabilityTest(unittest.TestCase):
    def test_the_subset_gets_more_draws_in_the_main_cells_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_once(tmp, histories=3, cells=["S1", "R1", "V2-8"], draws=2, audits=False,
                              reliability_histories=["t-h1"], reliability_draws=4)
            self.assertEqual(report.errors, [])
            n = Counter((s["history"], s["cell"]) for s in slots(tmp))
            self.assertEqual((n[("t-h1", "S1")], n[("t-h1", "R1")], n[("t-h1", "V2-8")]), (4, 4, 2))
            self.assertEqual((n[("t-h2", "S1")], n[("t-h3", "R1")]), (2, 2))

    def test_bad_subsets_are_refused(self):
        for kw in ({"reliability_histories": ["nope"]}, {"reliability_histories": ["t-h1"], "reliability_draws": 2}):
            with self.subTest(kw), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    make(tmp, cells=["S1"], draws=2, **kw)

    def test_an_older_plan_without_the_new_settings_still_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_once(tmp, histories=1, cells=["S1"], draws=1, audits=False)
            path = os.path.join(tmp, "run.json")
            plan = read(path)
            for key in ("reliability_histories", "reliability_draws"):
                del plan["config"][key]
            write(path, plan)
            report = run_once(tmp, histories=1, cells=["S1"], draws=1, audits=False)
            self.assertEqual((report.errors, report.slots_done), ([], 1))



class AuditContextTest(unittest.TestCase):
    def test_audits_see_the_rules_alone_by_default(self):
        for context, expected in (("rules", 2), ("history", 6)):
            recorder = Recorder(FakeModel(seed="ctx"))
            with self.subTest(context), tempfile.TemporaryDirectory() as tmp:
                run_once(tmp, transport=recorder, histories=1, cells=["S1"], draws=1, audit_context=context)
                audits = [b for b in recorder.bodies if "end your reply with a JSON object" in last_text(b)]
                self.assertEqual([len(b["messages"]) for b in audits], [expected])
                self.assertEqual(audits[0]["messages"][0]["role"], "system")
                a = read(os.path.join(tmp, "audits", "t-h1", "S1.json"))
                self.assertTrue(a["done"] and a["scores"])
