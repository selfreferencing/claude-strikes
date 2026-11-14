"""scripts/keep_going.py: which stops it repeats (the network's) and which end the run."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import keep_going as K  # noqa: E402

PILOT = ["python3", "scripts/run_pilot.py", "--live"]
NORMS = ["python3", "norms/run_norms.py", "--live"]


class VerdictTest(unittest.TestCase):
    def test_run_pilot(self):
        self.assertEqual(K.verdict(PILOT, 0, "Histories built: 300 of 300\n"), "done")
        self.assertEqual(K.verdict(PILOT, 5, "Slots done: 590; audits done: 300; unfinished: 10\n"), "again")
        self.assertEqual(K.verdict(PILOT, 4, "HALTED: 3 decision calls in a row got no reply after all attempts\n"), "again")
        self.assertEqual(K.verdict(PILOT, 4, "HALTED: spending reached the run's limit ($30.00 of $30.00)\n"), "stop")
        self.assertEqual(K.verdict(PILOT, 4, "HALTED: provider substitution (Google) (rgs-h001/S2-d1)\n"), "stop")
        self.assertEqual(K.verdict(PILOT, 3, "ERROR something\n"), "stop")

    def test_run_norms(self):
        done = "Norms probe nm-rg-son: 21600 calls on 300 histories\nNorms probe: 21600 results saved\n"
        short = "Norms probe nm-rg-son: 21600 calls on 300 histories\nNorms probe: 21590 results saved\n"
        self.assertEqual(K.verdict(NORMS, 0, done), "done")
        self.assertEqual(K.verdict(NORMS, 0, short), "again")
        self.assertEqual(K.verdict(NORMS, 4, "STOPPED: two calls in a row got no reply; the last, x: timeout\n"), "again")
        self.assertEqual(K.verdict(NORMS, 4, "STOPPED: spending reached the limit ($245.00 of $245.00)\n"), "stop")
        self.assertEqual(K.verdict(NORMS, 4, "STOPPED: response cache hit (x); the reply was set aside\n"), "stop")
        self.assertEqual(K.verdict(NORMS, 2, "Could not read the key's limit: timeout\n"), "key")
        self.assertEqual(K.verdict(NORMS, 2, "No key: missing\n"), "stop")


if __name__ == "__main__":
    unittest.main()
