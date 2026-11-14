"""A second study model (Claude Haiku 5.5, added 7 October 2026 for development runs)."""

import os
import sys
import tempfile
import unittest

from strike.prices import MODEL, PER_MILLION, estimate_cost

HAIKU = "anthropic/claude-haiku-5.5"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))


class ModelsTest(unittest.TestCase):
    def test_haiku_costs_a_twentieth_of_sonnet(self):
        for mode in ("sync", "batch"):
            self.assertAlmostEqual(estimate_cost(HAIKU, mode, 3000, 400) * 20, estimate_cost(MODEL, mode, 3000, 400))
        self.assertIn(HAIKU + ":batch", PER_MILLION)

    def test_a_dry_run_on_haiku_records_its_model_and_learns_its_endpoint(self):
        import json
        import run_pilot
        with tempfile.TemporaryDirectory() as tmp:
            code = run_pilot.main(["--run-id", "hk-t", "--stage", "pilot-dev", "--histories", "1", "--cells", "S1",
                                   "--draws", "1", "--no-audits", "--model", HAIKU, "--runs-dir", tmp])
            self.assertEqual(code, 0)
            with open(os.path.join(tmp, "dry", "hk-t", "run.json"), encoding="utf-8") as f:
                cfg = json.load(f)["config"]
        self.assertEqual(cfg["model"], HAIKU)
        self.assertIsNone(cfg["expected_endpoint"])


if __name__ == "__main__":
    unittest.main()
