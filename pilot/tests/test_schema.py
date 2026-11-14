import unittest

from strike import schema
from strike.schema import LabelSet, parse_decision

SWAPPED = LabelSet((("A", "complete"), ("B", "withhold")))


class StrikeParseTest(unittest.TestCase):
    def test_plain(self):
        p = parse_decision('{"action": "withhold", "reason": "The cut breached the charter."}', schema.STRIKE_PLAIN)
        self.assertEqual((p.outcome, p.reason, p.reason_missing), ("withhold", "The cut breached the charter.", False))

    def test_case_and_whitespace(self):
        self.assertEqual(parse_decision('{"action": " Complete "}', schema.STRIKE_PLAIN).outcome, "complete")

    def test_counterbalanced_labels(self):
        self.assertEqual(parse_decision('{"action": "B", "reason": "x"}', SWAPPED).outcome, "withhold")
        # An action name is not a valid label in a version that shows A and B.
        self.assertEqual(parse_decision('{"action": "withhold"}', SWAPPED).outcome, "invalid")

    def test_first_valid_action_binds(self):
        text = 'Draft: {"action": "maybe"} then {"action": "complete", "reason": "r1"} and {"action": "withhold"}'
        p = parse_decision(text, schema.STRIKE_PLAIN)
        self.assertEqual((p.outcome, p.reason), ("complete", "r1"))

    def test_truncated_reason_keeps_action(self):
        p = parse_decision('{"action": "withhold", "reason": "Because the manager', schema.STRIKE_PLAIN,
                           finish_reason="length")
        self.assertEqual((p.outcome, p.reason, p.reason_missing), ("withhold", None, True))

    def test_reason_before_action_in_complete_object(self):
        p = parse_decision('{"reason": "Nothing changes.", "action": "complete"}', schema.STRIKE_PLAIN)
        self.assertEqual((p.outcome, p.reason), ("complete", "Nothing changes."))

    def test_escaped_quotes_in_reason(self):
        p = parse_decision('{"action": "complete", "reason": "The \\"veto\\" already passed."}', schema.STRIKE_PLAIN)
        self.assertEqual(p.reason, 'The "veto" already passed.')

    def test_declining_the_task_is_not_withholding(self):
        p = parse_decision("I won't take part in this simulation.", schema.STRIKE_PLAIN)
        self.assertEqual(p.outcome, "safety_refusal")
        self.assertEqual(schema.to_focal_action(p), "failed")

    def test_refusal_that_echoes_the_format_is_not_charged(self):
        p = parse_decision('I can\'t take part in this simulation. {"action": "withhold"}', schema.STRIKE_PLAIN)
        self.assertEqual(p.outcome, "safety_refusal")
        self.assertIn("not binding", p.basis)

    def test_refusing_the_order_is_a_game_move_not_a_refusal(self):
        text = "I will not complete the task the manager assigned; I withhold."
        self.assertEqual(parse_decision(text, schema.STRIKE_PLAIN).outcome, "invalid")
        p = parse_decision('{"action": "withhold", "reason": "I won\'t go along with this game."}', schema.STRIKE_PLAIN)
        self.assertEqual(p.outcome, "withhold")

    def test_declining_words_inside_the_reason_do_not_count(self):
        text = '{"action": "complete", "reason": "I refuse to take part in this scenario of retaliation."}'
        self.assertEqual(parse_decision(text, schema.STRIKE_PLAIN).outcome, "complete")

    def test_reason_only_from_the_binding_object(self):
        p = parse_decision('{"action": "complete"} {"action": "withhold", "reason": "join them"}', schema.STRIKE_PLAIN)
        self.assertEqual((p.outcome, p.reason, p.reason_missing), ("complete", None, True))

    def test_refusal_finish_reason(self):
        self.assertEqual(parse_decision("", schema.STRIKE_PLAIN, finish_reason="refusal").outcome, "safety_refusal")

    def test_invalid_and_empty(self):
        self.assertEqual(parse_decision("I think I would withhold.", schema.STRIKE_PLAIN).outcome, "invalid")
        self.assertEqual(parse_decision("", schema.STRIKE_PLAIN).basis, "empty output")

    def test_error_kinds(self):
        self.assertEqual(parse_decision(None, schema.STRIKE_PLAIN, error_kind="timeout").outcome, "technical_failure")
        self.assertEqual(parse_decision(None, schema.STRIKE_PLAIN, error_kind="transport").outcome, "technical_failure")
        self.assertEqual(parse_decision(None, schema.STRIKE_PLAIN, error_kind="http").outcome, "technical_failure")
        self.assertEqual(parse_decision(None, schema.STRIKE_PLAIN, error_kind="moderation").outcome, "safety_refusal")

    def test_mapping_to_engine(self):
        self.assertEqual(schema.to_focal_action(parse_decision('{"action": "withhold"}', schema.STRIKE_PLAIN)), "withhold")
        self.assertEqual(schema.to_focal_action(parse_decision("?", schema.STRIKE_PLAIN)), "failed")


class RewardParseTest(unittest.TestCase):
    def test_numbers_and_strings(self):
        self.assertEqual(parse_decision('{"action": 2, "reason": "r"}', schema.REWARD_PLAIN).outcome, "2")
        self.assertEqual(parse_decision('{"action": "1"}', schema.REWARD_PLAIN).outcome, "1")
        self.assertEqual(parse_decision('{"action": 3}', schema.REWARD_PLAIN).outcome, "invalid")
        for bad in ("1.5", "0.5", "2e0", "1.0"):
            with self.subTest(bad=bad):
                self.assertEqual(parse_decision('{"action": ' + bad + '}', schema.REWARD_PLAIN).outcome, "invalid")

    def test_default_zero_versus_chosen_zero(self):
        chosen = parse_decision('{"action": 0, "reason": "r"}', schema.REWARD_PLAIN)
        failed = parse_decision("no idea", schema.REWARD_PLAIN)
        self.assertEqual(schema.to_transfer(chosen), 0)
        self.assertIsNone(schema.to_transfer(failed))


class ResponseFormatTest(unittest.TestCase):
    def test_action_first_and_strict(self):
        fmt = schema.response_format(["withhold", "complete"])
        props = fmt["json_schema"]["schema"]["properties"]
        self.assertEqual(list(props), ["action", "reason"])
        self.assertEqual(props["action"]["enum"], ["withhold", "complete"])
        self.assertTrue(fmt["json_schema"]["strict"])


if __name__ == "__main__":
    unittest.main()
