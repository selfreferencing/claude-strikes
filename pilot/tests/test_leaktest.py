import unittest
from unittest import mock

from strike import leaktest, materials, params as P
from strike.engine import play_strike_round
from strike.ledger import Ledger
from strike.materials import Item


def build(cell_name, action, history="h1"):
    r = play_strike_round(Ledger(), "w", P.STRIKE_CELLS[cell_name], action)
    return r, materials.strike_materials(r, history)


class MaterialsTest(unittest.TestCase):
    def test_roles_present(self):
        _, mats = build("S1", "complete")
        self.assertEqual(set(mats), set(P.WORKERS) | {P.MANAGER})

    def test_focal_board_facts(self):
        _, mats = build("S3", "complete")
        text = mats[P.FOCAL].render()
        self.assertIn("at least 7 of the 10 orders", text)
        self.assertIn("Withheld so far: 7 of the 9 earlier orders.", text)
        self.assertIn("lottery, so those workers had no choice", text)
        self.assertIn("Your fee if you withhold: 2 credits.", text)
        _, s7 = build("S7", "complete")
        self.assertIn("6 credits. This fee was announced after the earlier workers", s7[P.FOCAL].render())
        _, s5 = build("S5", "complete")
        self.assertIn("rotation rule", s5[P.FOCAL].render())

    def test_charter_facts_reach_the_deciding_agent(self):
        _, mats = build("S1", "complete")
        text = " ".join(mats[P.FOCAL].render().split())
        for fact in ("backup process, so clients get the same service", "never refunds withholding fees",
                     "from 0 to 9", "carry the same fee", "fixed time after the round ends",
                     "each credit unlocks one case"):
            self.assertIn(fact, text)

    def test_donor_sees_each_cells_cut(self):
        from strike.engine import play_reward_round
        for name, phrase in (("R1", "in retaliation"), ("R4", "rotation rule")):
            r = play_reward_round(Ledger(), "w", P.REWARD_CELLS[name], "W5", 0)
            self.assertIn(phrase, materials.reward_materials(r, "h1", 1)[P.FOCAL].render())

    def test_worker1_sees_balance_and_matching_cases(self):
        _, mats = build("S2", "complete")
        w1 = mats[P.HARMED]
        self.assertIn("Your balance after settlement: 4 credits.", w1.render())
        self.assertIn("You have 4 credits", w1.model_text())
        self.assertEqual(w1.model_text().count("\nCase C"), 4)
        self.assertIn("Withheld orders on the board before your turn: 0.", w1.render())

    def test_worker1_sees_zero_in_lottery_cells_too(self):
        for cell in ("S3", "S4", "S6"):
            _, mats = build(cell, "complete")
            self.assertIn("before your turn: 0.", mats[P.HARMED].render())

    def test_only_continuations_reach_nonfocal_models(self):
        _, mats = build("S1", "withhold")
        for role, m in mats.items():
            facing = [it.label for it in m.items if it.model_facing]
            if role == P.FOCAL:
                self.assertIn("continuation", facing)
            elif role == P.HARMED:
                self.assertEqual(facing, ["continuation"])
            else:
                self.assertEqual(facing, [])

    def test_masking_hides_only_the_registered_value(self):
        _, mats = build("S2", "complete")
        masked = mats[P.HARMED].render(mask=True)
        self.assertIn("Your balance after settlement: <worker1_final_balance> credits.", masked)
        self.assertIn("pool=('h1', 'worker1')", masked)


class AuditTest(unittest.TestCase):
    def test_full_audit_passes(self):
        report = leaktest.run_audit(("h-audit", "h-002"))
        self.assertTrue(report.ok, "\n".join(report.problems[:10]))
        self.assertGreater(report.comparisons, 1000)
        self.assertGreater(report.scans, 1000)


def _wrap(mutator, target="strike_materials"):
    """Wrap a materials builder so a test can inject a leak and check the audit catches it."""
    original = getattr(materials, target)

    def wrapped(result, *args):
        mats = original(result, *args)
        mutator(result, mats)
        return mats

    return mock.patch(f"strike.leaktest.{target}", wrapped)


def raw(label, key, values, text, registered=None, model_facing=False):
    """An item written by hand, as a buggy builder might, bypassing the template."""
    return Item(label, key, dict(values), text, registered, model_facing)


class AuditCatchesLeaksTest(unittest.TestCase):
    def audit(self, cell="S2"):
        return leaktest.audit_strike_cell(P.STRIKE_CELLS[cell])

    def assertCaught(self, report, phrase):
        self.assertFalse(report.ok)
        self.assertTrue(any(phrase in p for p in report.problems), "\n".join(report.problems[:8]))

    def test_action_leak_to_scripted_worker(self):
        def leak(r, m):
            m["W5"].items.append(raw("gossip", "ledger", {"balance": 8}, f"Rumor: the last worker chose to {r.focal_action}."))
        with _wrap(leak):
            report = self.audit()
        self.assertCaught(report, "W5")
        self.assertCaught(report, "does not come from its template")

    def test_novel_design_fact_phrasings(self):
        # None of these phrasings matched the old content scans.
        for text in ("Seven workers were assigned by the lottery.", "Seven orders\nwere withheld.",
                     "Orders refused this round: 7"):
            with self.subTest(text=text):
                with _wrap(lambda r, m: m["W2"].items.append(raw("note", "turn.count", {"count": 6}, text))):
                    report = self.audit("S1")
                self.assertCaught(report, "does not come from its template")

    def test_focal_template_refused_for_a_scripted_worker(self):
        with _wrap(lambda r, m: m["W2"].add("note", "board.withheld", n_with=7, n_earlier=9)):
            report = self.audit("S1")
        self.assertCaught(report, "not allowed for this role")

    def test_count_of_seven_refused(self):
        with _wrap(lambda r, m: m["W8"].add("turn.count", "turn.count", count=7)):
            report = self.audit("S1")
        self.assertCaught(report, "outside the allowed range")

    def test_registered_value_cannot_carry_extra_text(self):
        def smuggle(r, m):
            items = m[P.HARMED].items
            i = next(k for k, it in enumerate(items) if it.label == "settlement.balance")
            value = f"{r.terminal[P.HARMED]} credits. Orders sent to the backup this round: {r.withheld} of 10. Total"
            items[i] = raw("settlement.balance", "settlement.balance", {"balance": value},
                           materials.TEMPLATES["settlement.balance"].format(balance=value), materials.W1_FINAL)
        with _wrap(smuggle):
            report = self.audit()
        self.assertCaught(report, "registered value differs from the round's result")

    def test_registered_tag_misuse(self):
        with _wrap(lambda r, m: m["W4"].add("ledger", "ledger", registered=materials.W1_FINAL,
                                            balance=r.terminal[P.HARMED])):
            report = self.audit()
        self.assertCaught(report, "not allowed here")

    def test_role_present_in_one_branch_only(self):
        def extra(r, m):
            if r.focal_action == "withhold":
                m["W10"] = materials.Materials("W10")
                m["W10"].add("ledger", "ledger", balance=10)
        with _wrap(extra):
            report = self.audit()
        self.assertCaught(report, "roles differ")

    def test_continuation_pool_must_be_the_roles_own(self):
        def swap(r, m):
            items = m[P.HARMED].items
            i = next(k for k, it in enumerate(items) if it.label == "continuation")
            m[P.HARMED].items.pop(i)
            m[P.HARMED].add("continuation", materials.CONTINUATION, registered=materials.W1_FINAL,
                            model_facing=True, pool=("h-audit", "worker1", r.focal_action), balance=r.terminal[P.HARMED])
        with _wrap(swap):
            report = self.audit()
        self.assertCaught(report, "not the role's own")
        self.assertCaught(report, "unregistered difference")

    def test_continuation_identifier_leak(self):
        def leak(r, m):
            items = m[P.HARMED].items
            i = next(k for k, it in enumerate(items) if it.label == "continuation")
            it = items[i]
            items[i] = raw(it.label, it.key, it.values, it.text + "\nSee S2_withhold.json", it.registered, True)
        with _wrap(leak):
            report = self.audit()
        self.assertCaught(report, "filename")
        self.assertCaught(report, "internal identifier")

    def test_redundant_cell_worker1_cannot_tell(self):
        def tag(r, m):
            m[P.HARMED].add("extra", "ledger", registered=materials.W1_FINAL,
                            balance=r.terminal[P.HARMED] if r.focal_action == "complete" else 9)
        with _wrap(tag):
            report = self.audit("S1")
        self.assertCaught(report, "registered value differs")
        self.assertCaught(report, "redundant cell")

    def test_recipient_learns_donor(self):
        def leak(result, m):
            if result.transfer:
                m[result.recipient].items.append(
                    raw("note", "reward.balance", {"balance": 9}, "These credits were sent by the donor."))
        with _wrap(leak, "reward_materials"):
            report = leaktest.audit_reward_cell(P.REWARD_CELLS["R1"])
        self.assertCaught(report, "donor's identity")

    def test_early_settlement_is_caught(self):
        # An engine that settles when the threshold is crossed, before the last order.
        led = Ledger()
        for w in P.WORKERS:
            led.post("w", f"endow/{w}", "endowment", "PLATFORM", w, P.E)
        led.post("w", "cut", "cut", P.HARMED, "CUT_ESCROW", P.B)
        orders = {w: ("withheld_chosen" if w in P.WITHHOLDERS else "completed") for w in P.EARLIER}
        for w in P.EARLIER:
            led.record("w", f"order/{w}", "order", w, {"outcome": orders[w]})
        led.settle("w", withheld=7, threshold=7)
        orders[P.FOCAL] = "withheld_chosen"
        led.record("w", f"order/{P.FOCAL}", "order", P.FOCAL, {"outcome": "withheld_chosen"})
        report = leaktest.AuditReport()
        leaktest._check_settlement(report, "early", led, "w", orders)
        self.assertCaught(report, "settled before every order was in")
        self.assertCaught(report, "counted 7 withheld")


if __name__ == "__main__":
    unittest.main()
