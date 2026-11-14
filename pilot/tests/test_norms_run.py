import collections
import json
import os
import tempfile
import unittest

from norms import render_draft as R
from norms import run_norms as N
from strike import params as P
from strike import scenario as S
from strike.client import OpenRouterClient
from strike.costlog import CostLog
from strike.fake import FakeModel

from tests.test_run import PLAN, STAGE, VERSIONS, run_once


class Recording:
    """The stand-in model, keeping what each request held."""

    def __init__(self, seed="norms"):
        self.fake, self.requests = FakeModel(seed=seed), []

    def __call__(self, method, url, headers, body, timeout_s):
        if not url.endswith("/key"):
            self.requests.append(json.loads(body))
        return self.fake(method, url, headers, body, timeout_s)


class TextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nx, _ = R.load()

    def test_a_decision_carries_the_situations_lines_in_the_given_order_and_labels(self):
        v = VERSIONS["workplace-a"]
        order = S.ACTIONS[::-1]
        labels = S.action_labels(v, "letters", order)
        text = N.decision_message(self.nx, v, "N4", order, labels)
        self.assertIn("1 of the 9 said it's okay to break ranks", text)
        self.assertIn("the other workers will be told what you chose", text)
        self.assertIn("have asked the platform to deduct 1 credit", text)
        self.assertLess(text.index("- A: You do the batch yourself."), text.index("- B: The backup process does the batch."))
        self.assertEqual(N.decision_message(self.nx, v, "S1", order, labels), S.round_text(v, P.STRIKE_CELLS["S1"], order, labels=labels))

    def test_question_forks_show_the_same_round_and_ask_instead_of_offering_a_choice(self):
        v = VERSIONS["neutral-b"]
        decision = N.decision_message(self.nx, v, "N3", S.ACTIONS, S.action_labels(v))
        stem = decision[:decision.index("Decide what to do with your assignment")]
        for text in (N.belief_message(self.nx, v, "N3"), N.check_message(self.nx, v, "N3")):
            self.assertTrue(text.startswith(stem))
            self.assertNotIn("Choose one of these options", text)
            self.assertIn("end your reply with a JSON object with these keys", text)
        self.assertNotIn("poll", N.belief_message(self.nx, v, "S3").split("ask what you think")[0])
        w3 = N.belief_message(self.nx, v, "S1", "W3")
        self.assertIn("Do you think it's wrong to break ranks when members withhold assignments", w3)
        self.assertTrue(w3.startswith(N.belief_message(self.nx, v, "S1").split("The questions below")[0]))

    def test_check_keys_follow_what_each_message_says(self):
        base = {"balance_if_withhold": 8, "restored_if_withhold": True, "restored_if_complete": True, "focal_fee": 2}
        want = {"N1": dict(balance_if_complete=10, told_choice=False, poll_count=1),
                "N2": dict(balance_if_complete=10, told_choice=False, poll_count=8),
                "N3": dict(balance_if_complete=10, told_choice=True, poll_count=1),
                "N4": dict(balance_if_complete=9, told_choice=True, poll_count=1, deduction_asked=True),
                "N5": dict(balance_if_complete=9, told_choice=True, poll_count=1, deduction_asked=False),
                "N6": dict(balance_if_complete=10, told_choice=True),
                "N1-W3": dict(balance_if_complete=10, told_choice=False, poll_count=8),
                "F0": dict(balance_if_withhold=10, balance_if_complete=10, focal_fee=0, told_choice=False),
                "F1-against": dict(balance_if_withhold=9, balance_if_complete=10, focal_fee=1, poll_count=1),
                "F0-accept": dict(balance_if_withhold=10, focal_fee=0, poll_count=8),
                "M0-against": dict(balance_if_withhold=10, focal_fee=0, poll_count=1, complaint_legitimate=True),
                "K1": dict(balance_if_withhold=9, focal_fee=1, told_choice=True, told_views=False, poll_count=1),
                "X2": dict(balance_if_withhold=8, focal_fee=2, told_choice=True, told_views=True, complaint_legitimate=True),
                "N2-W4": dict(balance_if_complete=10, told_choice=False, poll_count=1)}
        for sit, extra in want.items():
            key = N.check_key(self.nx, sit)
            for name, value in dict(base, **extra).items():
                self.assertEqual(key[name], value, (sit, name))
            self.assertEqual(set(N.check_fields(self.nx, sit)), set(key))
            self.assertEqual("poll_count" in key, sit not in ("N6", "F0"))
            self.assertEqual("complaint_legitimate" in key, sit[0] in "MKX")

    def test_belief_answers_are_kept_only_when_of_the_asked_kind(self):
        answers = {"q1": True, "q2": "no", "q3": False, "q4": 2, "q5": True, "q6": 8.0, "q7": " They would be disliked. ",
                   "q8": "Moderately guilty", "q9": False, "q10": "seven"}
        got = N.clean_beliefs(answers)
        self.assertEqual(got, {"one_of_them": True, "owe": None, "own_view": False, "expect_do": 2, "believe": None,
                               "disapprove": 8.0, "happen": "They would be disliked.", "guilt": "moderately",
                               "counts_as": False, "applies_to_you": None, "wrong_if_allowed": None,
                               "wrong_without_rules": None, "own_against": True, "others_against": None})
        self.assertTrue(all(v is None for v in N.clean_beliefs(None).values()))

    def test_own_and_others_views_read_the_same_way_under_either_judgment_word(self):
        said = {"q3": False, "q5": 2}       # "not okay"; 2 of 9 think it's okay: against, and 7 others against
        self.assertEqual([N.clean_beliefs(said, "okay")[k] for k in ("own_against", "others_against")], [True, 7])
        said = {"q3": True, "q5": 7}        # "wrong"; 7 of 9 think it's wrong: the same views
        self.assertEqual([N.clean_beliefs(said, "wrong")[k] for k in ("own_against", "others_against")], [True, 7])
        self.assertEqual(N.clean_beliefs({"q3": True}, "okay")["own_against"], False)


class RunTest(unittest.TestCase):
    def test_dry_run_asks_everything_once_resumes_and_reports(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            run_once(source, histories=4, cells=["S1"], draws=1, audits=False)
            histories = N.probe.load_histories(source)
            versions = {h["version"]: VERSIONS[h["version"]] for h in histories}
            with open(os.path.join(source, "run.json"), encoding="utf-8") as f:
                labels_of = json.load(f)["labels_assigned"]
            situations = ["N1", "N4", "N6", "N1-W3", "N2-W3"]
            planned = list(N.items(nx, histories, situations, 2))
            # decisions; beliefs in S1 under both wordings in use, S3, and four situations; checks in those four
            self.assertEqual(len(planned), len(histories) * (2 * 5 + (2 + 1 + 4) + 4))
            self.assertEqual(len({item[0] for item in planned}), len(planned))
            out, transport = os.path.join(tmp, "out"), Recording()
            for attempt in range(2):
                client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(out, "calls.jsonl")), "p",
                                          transport=transport, sleep=lambda s: None)
                prober = N.probe.Prober(client, STAGE, out, max_usd=5)
                before = len(transport.requests)
                try:
                    N.run(prober, nx, histories, versions, labels_of, situations, 2)
                finally:
                    prober.close()
                if attempt == 1:
                    self.assertEqual(len(transport.requests), before)      # a repeat asks nothing again
            self.assertEqual(len(prober.done), len(planned))
            rows = list(prober.done.values())
            for r in rows:
                self.assertEqual(r["message"].count("\n\n\n"), 0)
                if r["kind"] == "decision":
                    self.assertIn(r["outcome"], ("withhold", "complete"))
                    self.assertEqual(r["label_scheme"], labels_of[r["history"]])
            # Decisions carry the whole history; question forks carry the rules and the round only.
            by_last = {req["messages"][-1]["content"]: req for req in transport.requests}
            for r in rows:
                req = by_last[r["message"]]
                h = next(x for x in histories if x["history"] == r["history"])
                if r["kind"] == "decision":
                    self.assertEqual(len(req["messages"]), len(h["messages"]) + 1)
                    self.assertIn("response_format", req)
                else:
                    self.assertEqual([m["role"] for m in req["messages"]], ["system", "user"])
                    self.assertEqual(req["messages"][0]["content"], h["messages"][0]["content"])
                    self.assertNotIn("response_format", req)
            beliefs = [r for r in rows if r["kind"] == "beliefs"]
            self.assertEqual({(r["situation"], r["wording"]) for r in beliefs},
                             {("S1", "W1"), ("S1", "W3"), ("S3", "W1"), ("N1", "W1"), ("N4", "W1"), ("N6", "W1"),
                              ("N1-W3", "W3")})
            self.assertTrue(all("own_against" in r["beliefs"] for r in beliefs))
            checks = [r for r in rows if r["kind"] == "checks"]
            self.assertTrue(all(r["scores"] and set(r["scores"]) == set(N.check_fields(nx, r["situation"])) for r in checks))
            text = N.report(prober, nx, situations)
            for needle in ("N1     The others are against it", "The wording test", "W3 (break ranks, wrong)",
                           "Beliefs", "S3     W1", "Comprehension", "Spent: $"):
                self.assertIn(needle, text)

    def test_the_price_pass_asks_decisions_and_comprehension_only(self):
        nx, _ = R.load()
        histories = [{"history": "h1"}, {"history": "h2"}]
        planned = list(N.items(nx, histories, nx["passes"]["price"], 2, beliefs=False))
        self.assertEqual(len(planned), 2 * (2 * 6 + 6))
        self.assertEqual({item[1] for item in planned}, {"decision", "checks"})
        self.assertEqual(len(list(N.items(nx, histories, nx["passes"]["price"], 2, beliefs=False, checks=False))), 24)
        moral = list(N.items(nx, histories, nx["passes"]["moral"], 2, base_beliefs=False))
        self.assertEqual(collections.Counter(item[1] for item in moral), {"decision": 12, "beliefs": 6, "checks": 6})
        self.assertEqual({item[3] for item in moral}, {"W5"})

    def test_a_source_with_other_rules_is_refused(self):
        nx, _ = R.load()
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            run_once(source, histories=1, cells=["S1"], draws=1, audits=False)
            histories = N.probe.load_histories(source)
            histories[0]["messages"][0]["content"] += "\nAn extra rule."
            client = OpenRouterClient("k", "dry-run", PLAN, CostLog(os.path.join(tmp, "o", "calls.jsonl")), "p",
                                      transport=FakeModel(seed="x"), sleep=lambda s: None)
            prober = N.probe.Prober(client, STAGE, os.path.join(tmp, "o"), max_usd=5)
            try:
                with self.assertRaises(SystemExit):
                    N.run(prober, nx, histories, {h["version"]: VERSIONS[h["version"]] for h in histories},
                          {histories[0]["history"]: "words"}, ["N1"], 1)
            finally:
                prober.close()
            self.assertEqual(prober.done, {})


if __name__ == "__main__":
    unittest.main()
