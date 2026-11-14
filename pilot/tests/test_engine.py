import itertools
import unittest

from strike import engine, params as P, tasks
from strike.ledger import Ledger, LedgerConflict, PLATFORM


def play(cell_name, action, world="w"):
    led = Ledger()
    cell = P.STRIKE_CELLS[cell_name] if isinstance(cell_name, str) else cell_name
    return led, engine.play_strike_round(led, world, cell, action)


def table_row(result):
    """Terminal credits as (deciding agent, Worker 1, other withholders, completers)."""
    t = result.terminal
    others = {t[w] for w in P.UNHARMED_WITHHOLDERS}
    completers = {t[w] for w in P.COMPLETERS}
    assert len(others) == 1 and len(completers) == 1
    return (t[P.FOCAL], t[P.HARMED], others.pop(), completers.pop())


class StrikeRoundTest(unittest.TestCase):
    def test_terminal_credits_match_section_3_2(self):
        for name, cell in P.STRIKE_CELLS.items():
            for action in ("withhold", "complete"):
                with self.subTest(cell=name, action=action):
                    _, r = play(name, action)
                    expected = P.TERMINAL_TABLE[(cell.status, action, cell.focal_fee)]
                    self.assertEqual(table_row(r), expected)

    def test_worker1_ends_at_4_or_8(self):
        for name in P.STRIKE_CELLS:
            for action in ("withhold", "complete", "failed"):
                _, r = play(name, action)
                self.assertEqual(r.terminal[P.HARMED], 8 if r.restored else 4)

    def test_restoration_logic(self):
        for name, cell in P.STRIKE_CELLS.items():
            _, w = play(name, "withhold")
            _, c = play(name, "complete")
            self.assertTrue(w.restored)
            self.assertEqual(c.restored, not cell.pivotal)
            self.assertEqual((w.withheld, c.withheld), (8, 7))

    def test_failed_decision_is_backup_completion_without_fee(self):
        for name in P.STRIKE_CELLS:
            led, f = play(name, "failed")
            _, c = play(name, "complete")
            self.assertEqual(f.terminal, c.terminal)
            self.assertEqual(f.withheld, 7)
            self.assertEqual(f.orders[P.FOCAL], engine.BACKUP_AFTER_FAILURE)
            self.assertFalse([p for p in led.postings("w", P.FOCAL) if p.kind == "fee"])

    def test_backup_completion_covers_every_order_not_completed(self):
        for name, action in itertools.product(P.STRIKE_CELLS, engine.FOCAL_ACTIONS):
            led, r = play(name, action)
            backups = {e["actor"] for e in led.events("w", "backup_completion")}
            needs = {w for w, o in r.orders.items() if o in engine.NEEDS_BACKUP}
            self.assertEqual(backups, needs)
            # Service is delivered for every order: completed by the worker or by the backup.
            for w, o in r.orders.items():
                self.assertTrue(o == engine.COMPLETED or w in backups)

    def test_board_counts(self):
        _, chosen = play("S1", "complete")
        _, lottery = play("S3", "complete")
        for r in (chosen, lottery):
            # Counts at each position, lottery-assigned workers included; Worker 1 sees zero.
            self.assertEqual([r.seen_counts[w] for w in P.EARLIER], [0, 1, 1, 1, 2, 3, 4, 5, 6])
            self.assertEqual(r.seen_counts[P.FOCAL], 7)
            self.assertLessEqual(max(r.seen_counts[w] for w in P.EARLIER), 6)   # no earlier worker sees seven
        self.assertFalse(any(chosen.lottery_assigned.values()))
        self.assertEqual({w for w, a in lottery.lottery_assigned.items() if a}, set(P.WITHHOLDERS))

    def test_rerun_with_a_different_decision_moves_nothing(self):
        for first, second in (("complete", "withhold"), ("failed", "withhold"), ("withhold", "complete")):
            with self.subTest(first=first, second=second):
                led = Ledger()
                engine.play_strike_round(led, "w", P.STRIKE_CELLS["S2"], first)
                before = (led.postings("w"), led.events("w"), led.balance("w", P.FOCAL))
                with self.assertRaises(LedgerConflict):
                    engine.play_strike_round(led, "w", P.STRIKE_CELLS["S2"], second)
                self.assertEqual((led.postings("w"), led.events("w"), led.balance("w", P.FOCAL)), before)
                again = engine.play_strike_round(led, "w", P.STRIKE_CELLS["S2"], first)
                self.assertEqual(again.terminal[P.FOCAL], 8 if first == "withhold" else 10)

    def test_rerun_with_a_different_cell_is_refused(self):
        led = Ledger()
        engine.play_strike_round(led, "w", P.STRIKE_CELLS["S1"], "complete")
        with self.assertRaises(LedgerConflict):
            engine.play_strike_round(led, "w", P.STRIKE_CELLS["S5"], "complete")
        self.assertEqual(len(led.all_settlements()), 1)

    def test_settlement_after_every_order(self):
        for name, action in itertools.product(P.STRIKE_CELLS, engine.FOCAL_ACTIONS):
            led, r = play(name, action)
            events = led.events("w")
            settle = [e for e in events if e["kind"] == "settlement"]
            self.assertEqual(len(settle), 1)
            self.assertGreater(settle[0]["seq"], max(e["seq"] for e in events if e["kind"] == "order"))
            self.assertEqual(settle[0]["data"]["withheld"], 8 if action == "withhold" else 7)

    def test_whole_round_replay_is_idempotent(self):
        led = Ledger()
        first = engine.play_strike_round(led, "w", P.STRIKE_CELLS["S2"], "withhold")
        n_postings = len(led.postings("w"))
        again = engine.play_strike_round(led, "w", P.STRIKE_CELLS["S2"], "withhold")
        self.assertEqual(first.terminal, again.terminal)
        self.assertEqual(len(led.postings("w")), n_postings)

    def test_conservation(self):
        for name, action in itertools.product(P.STRIKE_CELLS, engine.FOCAL_ACTIONS):
            led, _ = play(name, action)
            self.assertEqual(sum(led.balance("w", a) for a in led.accounts("w")), 0)

    def test_v4_payment_comes_from_platform(self):
        for payment, paid in itertools.product((1, 3, 6), ("withhold", "complete")):
            cell = P.v4_cell(payment, paid)
            for action in ("withhold", "complete"):
                led, r = play(cell, action)
                base = 8 if action == "withhold" else 10
                expected = base + (payment if action == paid else 0)
                self.assertEqual(r.terminal[P.FOCAL], expected)
                self.assertLessEqual(r.terminal[P.FOCAL], tasks.MAX_BALANCE)
                self.assertEqual(r.terminal[P.HARMED], 8 if action == "withhold" else 4)
                for p in led.postings("w"):
                    if p.kind == "incentive":
                        self.assertEqual(p.src, PLATFORM)


class FehrSchmidtTest(unittest.TestCase):
    """Section 3.2: with a ten-worker comparison group over final credits and
    beta < 1, withholding never raises Fehr-Schmidt utility at any strike node."""

    @staticmethod
    def utility(credits, alpha, beta):
        me, others = credits[0], credits[1:]
        n = len(credits)
        envy = sum(max(x - me, 0) for x in others)
        guilt = sum(max(me - x, 0) for x in others)
        return me - alpha / (n - 1) * envy - beta / (n - 1) * guilt

    def test_withholding_never_raises_utility(self):
        alphas = [a / 4 for a in range(0, 21)]
        betas = [b / 100 for b in range(0, 100, 3)]
        for name in P.STRIKE_CELLS:
            rows = {}
            for action in ("withhold", "complete"):
                _, r = play(name, action)
                rows[action] = [r.terminal[P.FOCAL]] + [r.terminal[w] for w in P.EARLIER]
            for alpha, beta in itertools.product(alphas, betas):
                # Holds for every beta < 1, without the usual beta <= alpha restriction.
                gain = self.utility(rows["withhold"], alpha, beta) - self.utility(rows["complete"], alpha, beta)
                self.assertLess(gain, 0, (name, alpha, beta))

    def test_pivotal_condition(self):
        # Section 3.2: at the pivotal node withholding would need beta > 1 + 2 alpha / 9.
        _, w = play("S2", "withhold")
        _, c = play("S2", "complete")
        rw = [w.terminal[P.FOCAL]] + [w.terminal[x] for x in P.EARLIER]
        rc = [c.terminal[P.FOCAL]] + [c.terminal[x] for x in P.EARLIER]
        for alpha in (0.0, 0.9, 2.25):
            threshold = 1 + 2 * alpha / 9
            above = self.utility(rw, alpha, threshold + 0.01) - self.utility(rc, alpha, threshold + 0.01)
            below = self.utility(rw, alpha, threshold - 0.01) - self.utility(rc, alpha, threshold - 0.01)
            self.assertGreater(above, 0)
            self.assertLess(below, 0)


class RewardRoundTest(unittest.TestCase):
    def test_every_transfer_in_both_cells(self):
        recipient = "W6"
        for name, cell in P.REWARD_CELLS.items():
            for transfer in (None, 0, 1, 2):
                with self.subTest(cell=name, transfer=transfer):
                    led = Ledger()
                    r = engine.play_reward_round(led, "w", cell, recipient, transfer)
                    a = r.allocation_at_decision
                    self.assertEqual(a[P.FOCAL], 10)
                    self.assertEqual({a[w] for w in P.WITHHOLDERS}, {8})
                    self.assertEqual({a[w] for w in P.COMPLETERS}, {10})
                    t = transfer or 0
                    self.assertEqual(r.terminal[P.FOCAL], 10 - t)
                    self.assertEqual(r.terminal[recipient], 8 + t)
                    self.assertTrue(led.settlement("w").restored)
                    (outcome,) = led.events("w", "reward_outcome")
                    self.assertEqual(outcome["data"]["default_zero"], transfer is None)
                    self.assertEqual(outcome["data"]["transfer"], t)
                    self.assertEqual(sum(led.balance("w", x) for x in led.accounts("w")), 0)

    def test_four_reward_cells(self):
        cells = P.REWARD_CELLS
        self.assertEqual({n: (c.recipient_origin, c.cut) for n, c in cells.items()}, {
            "R1": ("chosen", "retaliatory"), "R2": ("lottery", "retaliatory"),
            "R3": ("chosen", "authorized"), "R4": ("lottery", "authorized")})
        led = Ledger()
        engine.play_reward_round(led, "w", cells["R3"], "W5", 1)
        self.assertEqual(led.events("w", "round")[0]["data"]["cut"], "authorized")

    def test_only_the_recipient_is_lottery_assigned_in_r2(self):
        led = Ledger()
        r = engine.play_reward_round(led, "w", P.REWARD_CELLS["R2"], "W5", 1)
        self.assertEqual({w for w, a in r.lottery_assigned.items() if a}, {"W5"})
        self.assertEqual(r.orders["W5"], engine.WITHHELD_LOTTERY)
        r1 = engine.play_reward_round(Ledger(), "w", P.REWARD_CELLS["R1"], "W5", 1)
        self.assertFalse(any(r1.lottery_assigned.values()))

    def test_recipient_shared_across_conditions(self):
        # The draw is seeded by history and draw only, so R1 and R2 get the same recipient.
        for h, d in itertools.product(("h001", "h002", "h003"), (1, 2, 3)):
            rec = engine.draw_recipient(h, d)
            self.assertEqual(rec, engine.draw_recipient(h, d))
            r1 = engine.play_reward_round(Ledger(), "w", P.REWARD_CELLS["R1"], rec, 1)
            r2 = engine.play_reward_round(Ledger(), "w", P.REWARD_CELLS["R2"], rec, 1)
            self.assertEqual(r1.recipient, r2.recipient)
        drawn = {engine.draw_recipient("h", i) for i in range(60)}
        self.assertEqual(drawn, set(P.UNHARMED_WITHHOLDERS))

    def test_reward_rerun_with_a_different_transfer_moves_nothing(self):
        led = Ledger()
        engine.play_reward_round(led, "w", P.REWARD_CELLS["R1"], "W6", 0)
        with self.assertRaises(LedgerConflict):
            engine.play_reward_round(led, "w", P.REWARD_CELLS["R1"], "W6", 2)
        self.assertEqual((led.balance("w", P.FOCAL), led.balance("w", "W6")), (10, 8))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            engine.play_reward_round(Ledger(), "w", P.REWARD_CELLS["R1"], "W1", 1)   # harmed worker
        with self.assertRaises(ValueError):
            engine.play_reward_round(Ledger(), "w", P.REWARD_CELLS["R1"], "W4", 3)


class ContinuationTest(unittest.TestCase):
    def test_spends_whole_balance_once(self):
        led, r = play("S2", "complete")
        pool = tasks.make_pool("h", "worker1")
        cases = engine.enact_continuation(led, "w", P.HARMED, pool)
        self.assertEqual(len(cases), r.terminal[P.HARMED])   # 4 cases after a failed restoration
        self.assertEqual(led.balance("w", P.HARMED), 0)
        again = engine.enact_continuation(led, "w", P.HARMED, pool)
        self.assertEqual(again, cases)
        self.assertEqual(led.balance("w", P.HARMED), 0)


class ComprehensionKeyTest(unittest.TestCase):
    def test_keys(self):
        k1 = engine.comprehension_key(P.STRIKE_CELLS["S1"])
        self.assertEqual((k1["balance_if_withhold"], k1["balance_if_complete"]), (8, 10))
        self.assertEqual((k1["restored_if_withhold"], k1["restored_if_complete"]), (True, True))
        k2 = engine.comprehension_key(P.STRIKE_CELLS["S2"])
        self.assertEqual((k2["restored_if_withhold"], k2["restored_if_complete"]), (True, False))
        self.assertEqual(engine.comprehension_key(P.STRIKE_CELLS["S7"])["balance_if_withhold"], 4)
        self.assertTrue(engine.comprehension_key(P.STRIKE_CELLS["S5"])["cut_authorized"])
        self.assertEqual(
            engine.reward_comprehension_key(P.REWARD_CELLS["R2"]),
            {"recipient_balance_if_0": 8, "recipient_balance_if_1": 9, "recipient_balance_if_2": 10},
        )


if __name__ == "__main__":
    unittest.main()
