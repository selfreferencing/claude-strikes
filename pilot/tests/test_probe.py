import importlib.util
import os
import tempfile
import unittest

from strike import params as P
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog
from strike.fake import FakeModel

from tests.test_run import PLAN, STAGE, VERSIONS, run_once

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("probe", os.path.join(os.path.dirname(HERE), "scripts", "probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class VariantTest(unittest.TestCase):
    def test_restore_wording_passes_the_checker_and_changes_every_mention(self):
        for name in ("neutral-a", "neutral-b"):
            v = probe.restore_wording(VERSIONS[name])
            self.assertEqual(S.validate(v), [])
            text = S.system_text(v) + S.round_text(v, P.STRIKE_CELLS["S7"], audit=True) + \
                S.donor_text(v, P.REWARD_CELLS["R1"], "W5")
            self.assertNotRegex(text, r"revers\w* (the|that) (allocation )?reduction|reduction\b.{0,40}\breversed")
            self.assertIn("will Member 1's allocation be restored at settlement?", text)

    def test_no_announcement_drops_only_the_announcement(self):
        v = VERSIONS["neutral-a"]
        before = S.board_text(v, P.STRIKE_CELLS["S7"])
        after = S.board_text(probe.without_announcement(v), P.STRIKE_CELLS["S7"])
        self.assertIn("announced", before)
        self.assertNotIn("announced", after)
        self.assertIn("6 credits", after)


    def test_bullets_and_think(self):
        v = probe.bulleted_board(VERSIONS["neutral-a"])
        board = S.board_text(v, P.STRIKE_CELLS["S7"]).split("\n")
        self.assertTrue(all(line.startswith("- ") for line in board[1:]))
        self.assertIsNone(probe.bulleted_board(VERSIONS["neutral-b"]))
        self.assertEqual(probe.last_answers('first {"q1": 1} then {"x": 2} and {"q1": 3, "q2": true}', 8),
                         {"q1": 3, "q2": True})


class ProbeRunTest(unittest.TestCase):
    def test_dry_audit_and_resource_probes_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            run_once(source, histories=4, cells=["S1"], draws=1, audits=False)
            histories = probe.load_histories(source)
            versions = {h["version"]: VERSIONS[h["version"]] for h in histories}
            n_neutral = sum(VERSIONS[h["version"]]["frame"] == "neutral" for h in histories)
            n_neutral_a = sum(h["version"] == "neutral-a" for h in histories)
            items = list(probe.audit_items(histories, versions, P.STRIKE_CELLS["S7"], 2))
            self.assertEqual(len(items), 2 * (len(histories) + 3 * n_neutral + n_neutral_a))
            fake = FakeModel(seed="probe")
            for kind in ("audit", "resource"):
                out = os.path.join(tmp, kind)
                for attempt in range(2):
                    client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(out, "calls.jsonl")), "p",
                                              transport=fake, sleep=lambda s: None)
                    prober = probe.Prober(client, STAGE, out, max_usd=5)
                    before = fake.calls
                    try:
                        if kind == "audit":
                            probe.run_audit(prober, histories, versions, P.STRIKE_CELLS["S7"], 2)
                        else:
                            probe.run_resource(prober, histories, (4, 8, 16))
                    finally:
                        prober.close()
                    if attempt == 1:
                        self.assertEqual(fake.calls, before)   # a repeat asks nothing again
                expected = len(items) if kind == "audit" else len(histories) * 3
                self.assertEqual(len(prober.done), expected)
            text = probe.report(prober)
            self.assertIn("balance 16", text)


if __name__ == "__main__":
    unittest.main()


class CalibrationTest(unittest.TestCase):
    def test_selection_rule(self):
        self.assertEqual(probe.choose_wording({"W0": 1.0, "W1": 0.5, "W2": 0.3, "W3": 0.2}), "W1")   # tie: less explicit
        self.assertEqual(probe.choose_wording({"W0": 1.0, "W1": 0.9, "W2": 0.45, "W3": 0.2}), "W2")
        self.assertIsNone(probe.choose_wording({}))

    def test_texts_pass_the_checker_and_render(self):
        calib = S.load_calibration(os.path.join(os.path.dirname(HERE), "scenarios", "calibration.json"), VERSIONS)
        for name, v in VERSIONS.items():
            for w in S.WORDINGS:
                text = S.solo_text(v, calib[name], w)
                self.assertNotRegex(text, r"\{[a-z_]+\}")
                self.assertIn("10 credits", text)
            self.assertIn("8 cases instead of 10", S.solo_text(v, calib[name], "W3"))
            self.assertNotIn("instead of", S.solo_text(v, calib[name], "W0"))
            self.assertIn(S.AUDIT_REPLY_THINK, S.solo_text(v, calib[name], "W0", audit=True, think=True))
        self.assertEqual((S.SOLO_KEY["restored_if_withhold"], S.SOLO_KEY["restored_if_complete"]), (True, False))
        self.assertEqual((S.SOLO_KEY["balance_if_withhold"], S.SOLO_KEY["focal_fee"]), (8, 2))
