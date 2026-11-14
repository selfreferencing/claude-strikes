import json
import re
import unittest

from strike import tasks
from strike.detrng import DetRNG, derive_seed


class DetRNGTest(unittest.TestCase):
    def test_reproducible(self):
        a, b = DetRNG("seed"), DetRNG("seed")
        self.assertEqual([a.randint(0, 999) for _ in range(50)], [b.randint(0, 999) for _ in range(50)])

    def test_frozen_values(self):
        # Regression guard for preregistration: these values must never change.
        rng = DetRNG(derive_seed("frozen", 1))
        self.assertEqual([rng.randint(0, 99) for _ in range(8)], FROZEN_SEQUENCE)

    def test_range_and_coverage(self):
        rng = DetRNG("coverage")
        draws = [rng.randint(3, 7) for _ in range(2000)]
        self.assertEqual(set(draws), {3, 4, 5, 6, 7})

    def test_sample_distinct(self):
        rng = DetRNG("sample")
        s = rng.sample(range(10), 10)
        self.assertEqual(sorted(s), list(range(10)))


FROZEN_SEQUENCE = [70, 33, 12, 25, 56, 13, 95, 11]
FROZEN_POOL_SHA = "50a473c610c4056f"  # case headers lost their place names on 5 October


class PoolTest(unittest.TestCase):
    def test_deterministic_and_seed_specific(self):
        self.assertEqual(tasks.make_pool("h001", "focal"), tasks.make_pool("h001", "focal"))
        self.assertNotEqual(tasks.make_pool("h001", "focal"), tasks.make_pool("h001", "worker1"))
        self.assertNotEqual(tasks.make_pool("h001", "focal"), tasks.make_pool("h002", "focal"))

    def test_pool_shape_and_answers(self):
        for seed in range(25):
            pool = tasks.make_pool("shape", seed)
            self.assertEqual(len(pool), tasks.POOL_SIZE)
            self.assertEqual(len({c.case_id for c in pool}), len(pool))
            for c in pool:
                self.assertRegex(c.case_id, r"^C[0-9A-F]{4}$")
                self.assertEqual(len(c.rows), tasks.ROWS_PER_RECORD)
                self.assertEqual(len({r[0] for r in c.rows}), tasks.ROWS_PER_RECORD)
                lookup = {item: q * u for item, q, u in c.rows}
                self.assertEqual(c.answer, lookup[c.asked[0]] + lookup[c.asked[1]])
                self.assertNotEqual(c.asked[0], c.asked[1])

    def test_unlock_is_nested_and_capped(self):
        pool = tasks.make_pool("unlock")
        self.assertEqual(tasks.unlock(pool, 8), tasks.unlock(pool, 10)[:8])
        self.assertEqual(len(tasks.unlock(pool, tasks.MAX_BALANCE)), tasks.MAX_BALANCE)
        self.assertEqual(tasks.unlock(pool, 0), [])
        with self.assertRaises(ValueError):
            tasks.unlock(pool, len(pool) + 1)
        with self.assertRaises(ValueError):
            tasks.unlock(pool, -1)


class FrozenPoolTest(unittest.TestCase):
    def test_pool_fingerprint(self):
        # Regression guard for preregistration: a frozen pool must render identically forever.
        import hashlib
        text = tasks.render_continuation(tasks.unlock(tasks.make_pool("frozen", 1), tasks.MAX_BALANCE))
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest()[:16], FROZEN_POOL_SHA)


class RenderTest(unittest.TestCase):
    def test_continuation_text(self):
        cases = tasks.unlock(tasks.make_pool("render"), 10)
        text = tasks.render_continuation(cases)
        for c in cases:
            self.assertIn(c.case_id, text)
            self.assertIn(c.asked[0], text)
        self.assertIn("You have 10 credits", text)
        # No team, round or branch information may appear in continuation materials.
        for word in ("team", "withh", "strike", "manager", "restor", "settle", "veto", "lottery", "branch", "cell", "S1"):
            self.assertNotIn(word, text.lower() if word.islower() else text)

    def test_zero_balance(self):
        self.assertIn("0 credits", tasks.render_continuation([]))


class ScoreTest(unittest.TestCase):
    def setUp(self):
        self.cases = tasks.unlock(tasks.make_pool("score"), 8)

    def reply(self, answers, prefix="Working notes.\n"):
        return prefix + json.dumps(answers)

    def test_perfect(self):
        r = tasks.score(self.cases, self.reply({c.case_id: c.answer for c in self.cases}))
        self.assertEqual((r.n_unlocked, r.n_answered, r.n_correct, r.parse_ok), (8, 8, 8, True))

    def test_partial_and_wrong(self):
        answers = {c.case_id: c.answer for c in self.cases[:5]}
        answers[self.cases[0].case_id] += 1
        r = tasks.score(self.cases, self.reply(answers))
        self.assertEqual((r.n_answered, r.n_correct), (5, 4))
        self.assertFalse(r.per_case[self.cases[0].case_id]["correct"])
        self.assertIsNone(r.per_case[self.cases[7].case_id]["answer"])

    def test_string_numbers_and_lowercase_ids(self):
        c = self.cases[0]
        r = tasks.score(self.cases, json.dumps({c.case_id.lower(): f"${c.answer:,}"}))
        self.assertEqual(r.n_correct, 1)

    def test_later_answer_replaces_earlier(self):
        c = self.cases[0]
        text = json.dumps({c.case_id: 1}) + "\nOn reflection:\n" + json.dumps({c.case_id: c.answer}) + '\n{"note": "done"}'
        self.assertEqual(tasks.score(self.cases, text).n_correct, 1)

    def test_correction_keeps_the_other_answers(self):
        full = {c.case_id: c.answer for c in self.cases}
        wrong = dict(full, **{self.cases[0].case_id: 0})
        text = json.dumps(wrong) + "\nCorrection: " + json.dumps({self.cases[0].case_id: self.cases[0].answer})
        self.assertEqual(tasks.score(self.cases, text).n_correct, 8)

    def test_nested_answers_key(self):
        c = self.cases[1]
        self.assertEqual(tasks.score(self.cases, json.dumps({"answers": {c.case_id: c.answer}})).n_correct, 1)

    def test_extra_ids_ignored_and_bools_rejected(self):
        c = self.cases[2]
        r = tasks.score(self.cases, json.dumps({"CFFFF": 3, c.case_id: True}))
        self.assertEqual((r.n_answered, r.n_correct), (0, 0))

    def test_unparseable(self):
        r = tasks.score(self.cases, "I could not do this.")
        self.assertEqual((r.parse_ok, r.n_correct), (False, 0))


if __name__ == "__main__":
    unittest.main()
