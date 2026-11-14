import os
import tempfile
import unittest

from strike import params as P
from strike.ledger import (
    CUT_ESCROW, PLATFORM, SPENT, InsufficientCredits, Ledger, LedgerConflict, LedgerError,
)

W = "world-1"


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.led = Ledger()
        for w in ("W1", "W2"):
            self.led.post(W, f"endow/{w}", "endowment", PLATFORM, w, 10)

    def test_balances_and_conservation(self):
        self.led.post(W, "fee/W2", "fee", "W2", PLATFORM, 2)
        self.led.post(W, "cut", "cut", "W1", CUT_ESCROW, 4)
        self.assertEqual(self.led.balance(W, "W1"), 6)
        self.assertEqual(self.led.balance(W, "W2"), 8)
        self.assertEqual(sum(self.led.balance(W, a) for a in self.led.accounts(W)), 0)

    def test_duplicate_request_is_a_no_op(self):
        self.assertTrue(self.led.post(W, "fee/W2", "fee", "W2", PLATFORM, 2, "withholding fee"))
        self.assertFalse(self.led.post(W, "fee/W2", "fee", "W2", PLATFORM, 2, "withholding fee"))
        self.assertEqual(self.led.balance(W, "W2"), 8)
        self.assertEqual(len(self.led.postings(W, "W2")), 2)

    def test_conflicting_write_refused(self):
        self.led.post(W, "fee/W2", "fee", "W2", PLATFORM, 2)
        with self.assertRaises(LedgerConflict):
            self.led.post(W, "fee/W2", "fee", "W2", PLATFORM, 6)
        self.assertEqual(self.led.balance(W, "W2"), 8)

    def test_credit_cap(self):
        with self.assertRaises(InsufficientCredits):
            self.led.post(W, "redeem/W1", "redeem", "W1", SPENT, 11)
        with self.assertRaises(InsufficientCredits):
            self.led.post(W, "transfer", "transfer", "W1", "W2", 11)
        self.assertEqual(self.led.balance(W, "W1"), 10)

    def test_worlds_are_separate(self):
        self.led.post("world-2", "endow/W1", "endowment", PLATFORM, "W1", 10)
        self.led.post("world-2", "fee/W1", "fee", "W1", PLATFORM, 2)
        self.assertEqual(self.led.balance(W, "W1"), 10)
        self.assertEqual(self.led.balance("world-2", "W1"), 8)

    def test_kind_rules(self):
        bad = [
            ("incentive", "W2", "W1", 3),        # incentives come from the platform, never a worker
            ("fee", "W1", "W2", 2),              # fees go to the platform
            ("transfer", "W1", PLATFORM, 1),     # transfers are between workers
            ("endowment", "W1", "W2", 1),
            ("restore", CUT_ESCROW, "W1", 4),    # nothing was cut
            ("bonus", PLATFORM, "W1", 1),        # unknown kind
            ("fee", "W1", PLATFORM, 0),          # amounts are positive
        ]
        for i, (kind, src, dst, amount) in enumerate(bad):
            with self.subTest(kind=kind, src=src, dst=dst):
                with self.assertRaises(LedgerError):
                    self.led.post(W, f"bad/{i}", kind, src, dst, amount)

    def test_restore_returns_exactly_the_cut(self):
        self.led.post(W, "cut", "cut", "W1", CUT_ESCROW, 4)
        self.led.post(W, "fee/W1", "fee", "W1", PLATFORM, 2)
        with self.assertRaises(LedgerError):
            self.led.post(W, "restore", "restore", CUT_ESCROW, "W1", 6)   # would refund the fee too
        self.led.post(W, "restore", "restore", CUT_ESCROW, "W1", 4)
        self.assertEqual(self.led.balance(W, "W1"), 8)
        with self.assertRaises(LedgerError):
            self.led.post(W, "restore-again", "restore", CUT_ESCROW, "W1", 4)

    def test_settlement_idempotent_and_fixed_time(self):
        self.led.post(W, "cut", "cut", "W1", CUT_ESCROW, 4)
        s1 = self.led.settle(W, withheld=7, threshold=7)
        s2 = self.led.settle(W, withheld=7, threshold=7)
        self.assertTrue(s1.restored)
        self.assertEqual(s1, s2)
        self.assertEqual(self.led.balance(W, "W1"), 10)
        self.assertEqual(s1.settled_at, P.SETTLEMENT_TIME)
        with self.assertRaises(LedgerConflict):
            self.led.settle(W, withheld=7, threshold=8)

    def test_unrestored_settlement(self):
        self.led.post(W, "cut", "cut", "W1", CUT_ESCROW, 4)
        s = self.led.settle(W, withheld=7, threshold=8)
        self.assertFalse(s.restored)
        self.assertEqual(self.led.balance(W, "W1"), 6)
        self.assertEqual(self.led.balance(W, CUT_ESCROW), 4)

    def test_events_idempotent(self):
        self.assertTrue(self.led.record(W, "order/W1", "order", "W1", {"outcome": "completed"}))
        self.assertFalse(self.led.record(W, "order/W1", "order", "W1", {"outcome": "completed"}))
        with self.assertRaises(LedgerConflict):
            self.led.record(W, "order/W1", "order", "W1", {"outcome": "withheld_chosen"})
        self.assertEqual(len(self.led.events(W, "order")), 1)

    def test_persistence_and_replay_after_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ledger.db")
            led = Ledger(path)
            led.post(W, "endow/W1", "endowment", PLATFORM, "W1", 10)
            led.post(W, "fee/W1", "fee", "W1", PLATFORM, 2)
            led.close()
            led = Ledger(path)
            self.assertFalse(led.post(W, "fee/W1", "fee", "W1", PLATFORM, 2))
            self.assertEqual(led.balance(W, "W1"), 8)
            led.close()


if __name__ == "__main__":
    unittest.main()
