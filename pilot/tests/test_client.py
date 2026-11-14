from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from unittest import mock

from strike import client as client_mod
from strike.client import (
    BatchAlreadyLogged,
    BatchTimeout,
    OpenRouterClient,
    OpenRouterError,
    TransportError,
)
from strike.costlog import CostLog, FundingError, FundingPlan

PILOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = os.path.join(PILOT, "funding_plan.json")
KEY = "sk-or-v1-" + "5ec7e7a1b2" * 6   # fake, but shaped like a real key
MESSAGES = [{"role": "user", "content": "Reply with the single word: ready."}]


def completion(content="ready", provider="Anthropic", cost=0.0012, gen_id="gen-test-1", finish="stop", **extra):
    body = {
        "id": gen_id, "object": "chat.completion", "created": 1, "model": "anthropic/claude-sonnet-5.5",
        "choices": [{"index": 0, "finish_reason": finish, "native_finish_reason": "end_turn",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 50, "total_tokens": 70,
                  "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "completion_tokens_details": {"reasoning_tokens": 40}, "cost": cost, "is_byok": False},
    }
    if provider is not None:
        body["provider"] = provider
    body.update(extra)
    return body


class FakeTransport:
    """Replays canned (status, headers, body) answers in order and records every request."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout_s):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body,
                           "timeout_s": timeout_s})
        if not self.answers:
            raise AssertionError(f"unexpected request {method} {url}")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, headers_out, payload = answer
        return status, headers_out, payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def sent(self, i=-1):
        return json.loads(self.calls[i]["body"])


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.plan = FundingPlan.load(PLAN_PATH)
        self.log = CostLog(os.path.join(self.dir, "logs", "run.jsonl"))
        self.sleeps = []

    def make(self, *answers, **kw):
        self.transport = FakeTransport(*answers)
        return OpenRouterClient(KEY, "free-systems", self.plan, self.log, "test-run",
                                transport=self.transport, sleep=self.sleeps.append, **kw)

    def chat(self, client, **kw):
        args = dict(stage="smoke", call_type="smoke", slot_id="slot-1", effort="medium")
        args.update(kw)
        return client.chat(MESSAGES, **args)

    def records(self):
        return self.log.records()

    def everything_saved(self):
        texts = []
        for root, _, files in os.walk(self.dir):
            for name in files:
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    texts.append(f.read())
        return "\n".join(texts)


class RequestTest(ClientTestCase):
    def test_headers(self):
        self.chat(self.make((200, {}, completion())))
        call = self.transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/api/v1/chat/completions"))
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(call["headers"]["X-OpenRouter-Cache"], "false")
        self.assertEqual(call["headers"]["X-OpenRouter-Metadata"], "enabled")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertEqual(call["timeout_s"], 180)

    def test_sync_body(self):
        fmt = {"type": "json_schema", "json_schema": {"name": "d", "strict": True, "schema": {"type": "object"}}}
        self.chat(self.make((200, {}, completion())), effort="low", max_tokens=1234, response_format=fmt)
        body = self.transport.sent(0)
        self.assertEqual(body["provider"], {"order": ["anthropic"], "allow_fallbacks": False, "require_parameters": True})
        self.assertEqual(body["reasoning"], {"effort": "low"})
        self.assertEqual((body["model"], body["max_tokens"], body["messages"]), ("anthropic/claude-sonnet-5.5", 1234, MESSAGES))
        self.assertEqual(body["response_format"], fmt)
        for absent in ("temperature", "top_p", "top_k", "stream", "reasoning_effort", "max_completion_tokens",
                       "verbosity", "usage"):
            self.assertNotIn(absent, body)

    def test_no_effort_sends_no_reasoning(self):
        self.chat(self.make((200, {}, completion())), effort=None)
        self.assertNotIn("reasoning", self.transport.sent(0))

    def test_bad_arguments_refused_before_sending(self):
        client = self.make()
        for kw in ({"effort": "none"}, {"effort": "minimal"}, {"effort": "LOW"}, {"call_type": "nonsense"},
                   {"max_tokens": 0}, {"model": "anthropic/claude-sonnet-5.5:batch"}, {"provider_pin": ""}):
            with self.assertRaises(ValueError, msg=kw):
                self.chat(client, **kw)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(self.records(), [])

    def test_study_stages_use_the_fixed_effort(self):
        client = self.make((200, {}, completion()))
        for effort in ("low", "high", None):
            with self.assertRaises(ValueError, msg=effort):
                self.chat(client, stage="pilot-dev", call_type="decision", effort=effort)
        self.assertEqual(self.transport.calls, [])
        self.chat(client, stage="pilot-dev", call_type="decision", effort="medium")
        self.assertEqual(self.transport.sent(0)["reasoning"], {"effort": "medium"})

    def test_study_batches_use_the_fixed_effort(self):
        client = self.make()
        body = {"messages": MESSAGES, "max_tokens": 100, "reasoning": {"effort": "low"}}
        with self.assertRaises(ValueError):
            client.submit_batch([{"custom_id": "a", "body": body, "call_type": "decision"}], stage="pilot-dev")
        self.assertEqual(self.transport.calls, [])

    def test_every_request_turns_the_cache_off(self):
        client = self.make((200, {}, {"data": {"label": "fs", "limit": 250}}),
                           (200, {}, {"data": {"provider_name": "Anthropic"}}))
        client.key_info()
        client.generation("gen-abc")
        self.assertTrue(self.transport.calls[1]["url"].endswith("/api/v1/generation?id=gen-abc"))
        for call in self.transport.calls:
            self.assertEqual(call["headers"]["X-OpenRouter-Cache"], "false")
            self.assertEqual(call["headers"]["Authorization"], f"Bearer {KEY}")


class RetryTest(ClientTestCase):
    def test_500_then_200_logs_two_attempts(self):
        client = self.make((500, {}, {"error": {"code": 500, "message": "Internal Server Error"}}),
                           (200, {}, completion()))
        r = self.chat(client)
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        self.assertEqual(self.sleeps, [2])
        recs = self.records()
        self.assertEqual([(x.attempt, x.http_status) for x in recs], [(1, 500), (2, 200)])
        self.assertEqual(recs[0].error_kind, "http")
        self.assertIn("500", recs[0].error)
        self.assertTrue(recs[1].ok)
        self.assertEqual((recs[1].cost_usd, recs[1].reasoning_tokens, recs[1].generation_id), (0.0012, 40, "gen-test-1"))

    def test_400_not_retried(self):
        r = self.chat(self.make((400, {}, {"error": {"code": 400, "message": "Invalid request parameters"}})))
        self.assertEqual((r.ok, r.attempts, r.http_status, r.error_kind), (False, 1, 400, "http"))
        self.assertEqual((len(self.records()), self.sleeps), (1, []))

    def test_garbage_200_not_retried(self):
        r = self.chat(self.make((200, {}, b"<html>upstream hiccup</html>")))
        self.assertEqual((r.ok, r.attempts, r.http_status, r.error_kind), (False, 1, 200, "http"))
        self.assertEqual((len(self.transport.calls), len(self.records())), (1, 1))

    def test_200_carrying_an_error_not_retried(self):
        body = {"id": "gen-x", "error": {"code": 502, "message": "Provider disconnected",
                                         "metadata": {"error_type": "provider_unavailable"}}}
        r = self.chat(self.make((200, {}, body)))
        self.assertEqual((r.ok, r.attempts, r.error_type), (False, 1, "provider_unavailable"))
        self.assertIn("502", r.error_message)

    def test_transport_error_three_times(self):
        client = self.make(TransportError("timed out"), TransportError("timed out"), TransportError("reset"))
        r = self.chat(client)
        self.assertEqual((r.ok, r.attempts, r.error_kind, r.http_status), (False, 3, "transport", None))
        recs = self.records()
        self.assertEqual([x.attempt for x in recs], [1, 2, 3])
        self.assertTrue(all(x.error_kind == "transport" and x.error for x in recs))
        self.assertEqual(self.sleeps, [2, 8])

    def test_retry_after_is_honored(self):
        client = self.make((429, {"Retry-After": "5"}, {"error": {"code": 429, "message": "Rate limit exceeded"}}),
                           (200, {}, completion()))
        self.assertTrue(self.chat(client).ok)
        self.assertEqual(self.sleeps, [5.0])

    def test_moderation_classified_and_not_retried(self):
        flagged = {"error": {"code": 403, "message": "Input flagged", "metadata": {
            "reasons": ["violence"], "flagged_input": "...", "provider_name": "OpenRouter",
            "model_slug": "anthropic/claude-sonnet-5.5"}}}
        r = self.chat(self.make((403, {}, flagged)))
        self.assertEqual((r.ok, r.error_kind, r.error_type, r.attempts), (False, "moderation", "moderation", 1))
        self.assertIn("violence", r.error_message)
        self.assertEqual(self.records()[0].error_kind, "moderation")

    def test_typed_refusal_is_moderation_but_other_403s_are_not(self):
        refusal = {"error": {"code": 403, "message": "declined", "metadata": {"error_type": "refusal"}}}
        self.assertEqual(self.chat(self.make((403, {}, refusal))).error_kind, "moderation")
        guardrail = {"error": {"code": 403, "message": "Request blocked: prompt injection patterns detected",
                               "metadata": {"patterns": ["x"]}}}
        self.assertEqual(self.chat(self.make((403, {}, guardrail))).error_kind, "http")

    def test_get_is_retried(self):
        client = self.make((503, {}, {"error": {"code": 503, "message": "unavailable"}}),
                           (200, {}, {"data": {"label": "fs", "limit": 250}}))
        self.assertEqual(client.key_info()["limit"], 250)
        self.assertEqual(len(self.transport.calls), 2)


class FundingTest(ClientTestCase):
    def test_refused_before_any_request(self):
        client = self.make()
        with self.assertRaises(FundingError):
            self.chat(client, stage="stage1")
        with self.assertRaises(FundingError):
            client.submit_batch([{"custom_id": "a", "body": {"messages": MESSAGES}, "call_type": "smoke"}],
                                stage="stage1")
        self.assertEqual(self.transport.calls, [])
        self.assertFalse(os.path.exists(self.log.path))


class FlagTest(ClientTestCase):
    def test_provider_mismatch(self):
        r = self.chat(self.make((200, {}, completion(provider="Google"))))
        self.assertTrue(r.ok and r.provider_mismatch)
        rec = self.records()[0]
        self.assertEqual((rec.provider_requested, rec.provider_actual), ("anthropic", "Google"))

    def test_pinned_provider_matches(self):
        self.assertFalse(self.chat(self.make((200, {}, completion(provider="Anthropic")))).provider_mismatch)

    def test_provider_from_router_metadata(self):
        meta = {"requested": "anthropic/claude-sonnet-5.5", "strategy": "direct", "attempt": 1, "endpoints": {
            "total": 2, "available": [{"provider": "Google", "model": "m", "selected": False},
                                      {"provider": "Anthropic", "model": "m", "selected": True}]}}
        r = self.chat(self.make((200, {}, completion(provider=None, openrouter_metadata=meta))))
        self.assertEqual((r.provider, r.provider_mismatch), ("Anthropic", False))

    def test_compression_is_switched_off(self):
        self.chat(self.make((200, {}, completion())))
        self.assertEqual(self.transport.sent(0)["plugins"], [{"id": "context-compression", "enabled": False}])
        self.chat(self.make((200, {}, completion())), compression_off=False)
        self.assertNotIn("plugins", self.transport.sent(0))

    def test_router_metadata_recorded(self):
        meta = {"attempt": 1, "endpoints": {"total": 1, "available": [
            {"provider": "Anthropic", "model": "anthropic/claude-sonnet-5.5", "selected": True}]},
            "pipeline": [{"type": "guardrail", "name": "moderation", "data": {"flagged": False}}]}
        r = self.chat(self.make((200, {}, completion(openrouter_metadata=meta))))
        self.assertEqual((r.endpoint, r.router_attempt, r.altered),
                         ("Anthropic / anthropic/claude-sonnet-5.5", 1, False))
        rec = self.records()[0]
        self.assertEqual((rec.endpoint, rec.router_attempt, rec.pipeline),
                         ("Anthropic / anthropic/claude-sonnet-5.5", 1, "guardrail:moderation (not flagged)"))

    def test_pipeline_alterations_flagged(self):
        for stage in ({"type": "response_healing", "name": "response-healing"},
                      {"type": "context_compression", "name": "context-compression"},
                      {"type": "guardrail", "name": "moderation", "data": {"flagged": True}}):
            with self.subTest(stage=stage["type"]):
                r = self.chat(self.make((200, {}, completion(openrouter_metadata={"pipeline": [stage]}))))
                self.assertTrue(r.altered)
                self.assertIn(stage["type"], ", ".join(r.pipeline))

    def test_cache_hit(self):
        r = self.chat(self.make((200, {"X-OpenRouter-Cache-Status": "HIT"}, completion())))
        self.assertTrue(r.cache_hit)
        self.assertEqual(self.records()[0].response_cache_status, "HIT")
        self.assertFalse(self.chat(self.make((200, {"x-openrouter-cache-status": "MISS"}, completion()))).cache_hit)

    def test_refusal_output_is_not_an_error(self):
        body = completion(content=None, finish="content_filter")
        body["choices"][0]["message"]["refusal"] = "I can't help with that."
        r = self.chat(self.make((200, {}, body)))
        self.assertEqual((r.ok, r.finish_reason, r.refusal, r.error_kind),
                         (True, "content_filter", "I can't help with that.", None))


def batch_requests():
    body = {"messages": MESSAGES, "max_tokens": 64, "reasoning": {"effort": "low"}}
    return [{"custom_id": "c-1", "body": dict(body), "call_type": "continuation", "slot_id": "h1-S1-d1"},
            {"custom_id": "c-2", "body": dict(body), "call_type": "decision", "slot_id": "h1-S1-d2"}]


def accepted(batch_id="batch_abc"):
    return 202, {}, {"id": batch_id, "object": "batch", "status": "validating", "results": None, "usage": None,
                     "error": None}


def result(custom_id, gen_id, prompt=20, completion_tokens=10, provider="Anthropic", cost=None):
    usage = {"prompt_tokens": prompt, "completion_tokens": completion_tokens,
             "total_tokens": prompt + completion_tokens, "completion_tokens_details": {"reasoning_tokens": 6}}
    if cost is not None:
        usage["cost"] = cost
    return {"id": f"batch_req_{custom_id}", "custom_id": custom_id, "error": None, "response": {
        "status_code": 200, "request_id": "r", "body": {
            "id": gen_id, "object": "chat.completion", "created": 1, "model": "anthropic/claude-sonnet-5.5",
            "provider": provider, "usage": usage,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}]}}}


def batch(batch_id="batch_abc", results=None, cost=0.0123, status="completed"):
    usage = {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60, "is_byok": False}
    if cost is not None:
        usage["cost"] = cost
    return {"id": batch_id, "object": "batch", "endpoint": "/v1/chat/completions",
            "model": "anthropic/claude-sonnet-5.5", "completion_window": "24h", "status": status,
            "created_at": 1, "finalized_at": 2, "usage": usage, "results": results, "error": None,
            "request_counts": {"total": 2, "completed": len(results or []), "failed": 0}}


class BatchSubmitTest(ClientTestCase):
    def test_serialization(self):
        client = self.make(accepted())
        self.assertEqual(client.submit_batch(batch_requests(), stage="smoke"), "batch_abc")
        call = self.transport.calls[0]
        self.assertTrue(call["url"].endswith("/api/v1/batches"))
        self.assertEqual(call["headers"]["X-OpenRouter-Cache"], "false")
        top = json.loads(call["body"], object_pairs_hook=lambda pairs: pairs)
        self.assertEqual([k for k, _ in top], ["endpoint", "model", "provider", "completion_window", "requests"])
        raw = call["body"].decode()
        self.assertGreater(raw.index('"requests"'), raw.index('"completion_window"'))
        payload = json.loads(call["body"])
        self.assertEqual(payload["provider"], {"only": ["anthropic"]})
        self.assertEqual((payload["model"], payload["endpoint"]), ("anthropic/claude-sonnet-5.5", "/v1/chat/completions"))
        for item in payload["requests"]:
            self.assertEqual(set(item), {"custom_id", "body"})
            for key in client_mod.BATCH_BODY_FORBIDDEN:
                self.assertNotIn(key, item["body"])

    def test_routing_sampling_and_stream_keys_refused(self):
        for key, value in (("provider", {"order": ["anthropic"]}), ("stream", True), ("temperature", 0.7),
                           ("allow_fallbacks", False), ("order", ["anthropic"]), ("max_completion_tokens", 100)):
            requests = batch_requests()
            requests[0]["body"][key] = value
            client = self.make()
            with self.assertRaises(ValueError, msg=key):
                client.submit_batch(requests, stage="smoke")
            self.assertEqual(self.transport.calls, [])

    def test_other_bad_submissions_refused(self):
        client = self.make()
        duplicate = batch_requests()
        duplicate[1]["custom_id"] = "c-1"
        bad_type = batch_requests()
        bad_type[0]["call_type"] = "nonsense"
        no_reasoning = batch_requests()
        no_reasoning[1]["body"]["reasoning"] = {"effort": "none"}
        for requests, kw in ((duplicate, {}), (bad_type, {}), (no_reasoning, {}), ([], {}),
                             (batch_requests(), {"model": "anthropic/claude-sonnet-5.5:batch"})):
            with self.assertRaises(ValueError):
                client.submit_batch(requests, stage="smoke", **kw)
        self.assertEqual(self.transport.calls, [])

    def test_submission_never_retried(self):
        client = self.make(TransportError("timed out"))
        with self.assertRaises(TransportError) as cm:
            client.submit_batch(batch_requests(), stage="smoke")
        self.assertIn("may still have been created", str(cm.exception))
        self.assertEqual(len(self.transport.calls), 1)


class BatchLogTest(ClientTestCase):
    def submitted(self, *later):
        client = self.make(accepted(), *later)
        client.submit_batch(batch_requests(), stage="smoke")
        return client

    def test_results_and_cost_total(self):
        client = self.submitted()
        client.log_batch_results(batch(results=[result("c-1", "gen-batch-1"), result("c-2", "gen-batch-2")]))
        with open(os.path.join(client.batch_dir, "batch_abc.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["id"], "batch_abc")
        recs = self.records()
        per = [r for r in recs if not r.batch_summary]
        summary = [r for r in recs if r.batch_summary]
        self.assertEqual([(r.custom_id, r.call_type, r.slot_id, r.generation_id, r.effort) for r in per],
                         [("c-1", "continuation", "h1-S1-d1", "gen-batch-1", "low"),
                          ("c-2", "decision", "h1-S1-d2", "gen-batch-2", "low")])
        for r in per:
            self.assertEqual((r.mode, r.batch_id, r.prompt_tokens, r.reasoning_tokens, r.cost_usd),
                             ("batch", "batch_abc", 20, 6, None))
            self.assertEqual((r.provider_requested, r.provider_actual), ("anthropic", "Anthropic"))
            self.assertTrue(r.ok)
        self.assertEqual(len(summary), 1)
        self.assertEqual((summary[0].cost_usd, summary[0].prompt_tokens, summary[0].ok), (0.0123, None, False))
        self.assertAlmostEqual(sum(r.cost_usd or 0.0 for r in recs), 0.0123, places=12)

    def test_batch_cost_wins_over_per_result_costs(self):
        client = self.submitted()
        client.log_batch_results(batch(cost=0.007, results=[result("c-1", "g1", cost=0.004),
                                                            result("c-2", "g2", cost=0.003)]))
        self.assertAlmostEqual(sum(r.cost_usd or 0.0 for r in self.records()), 0.007, places=12)

    def test_per_result_costs_only_when_no_batch_cost(self):
        client = self.submitted()
        client.log_batch_results(batch(cost=None, results=[result("c-1", "g1", cost=0.004),
                                                           result("c-2", "g2", cost=0.003)]))
        recs = self.records()
        self.assertAlmostEqual(sum(r.cost_usd or 0.0 for r in recs), 0.007, places=12)
        self.assertIsNone(next(r for r in recs if r.batch_summary).cost_usd)

    def test_logged_only_once(self):
        client = self.submitted()
        done = batch(results=[result("c-1", "g1"), result("c-2", "g2")])
        client.log_batch_results(done)
        with self.assertRaises(BatchAlreadyLogged):
            client.log_batch_results(done)
        self.assertEqual(len(self.records()), 3)

    def test_errors_and_missing_results(self):
        client = self.submitted()
        declined = {"id": "batch_req_c-2", "custom_id": "c-2", "response": None, "error": {
            "type": "invalid_request_error", "message": "declined", "param": None,
            "error_type": "content_policy_violation"}}
        client.log_batch_results(batch(results=[declined], cost=0.0))
        recs = {r.custom_id: r for r in self.records() if not r.batch_summary}
        self.assertEqual(recs["c-2"].error_kind, "moderation")
        self.assertEqual(recs["c-1"].error_kind, "http")
        self.assertIn("no result", recs["c-1"].error)

    def test_failed_batch(self):
        client = self.submitted()
        failed = batch(results=None, cost=None, status="failed")
        failed["error"] = {"message": "image URL rejected"}
        client.log_batch_results(failed)
        recs = self.records()
        self.assertEqual(len(recs), 3)
        summary = next(r for r in recs if r.batch_summary)
        self.assertIn("image URL rejected", summary.error)
        self.assertTrue(all(r.error for r in recs))

    def test_only_terminal_batches_logged(self):
        client = self.submitted()
        with self.assertRaises(ValueError):
            client.log_batch_results(batch(results=None, status="in_progress"))
        self.assertEqual(self.records(), [])

    def test_resumed_by_another_process(self):
        self.submitted()
        later = OpenRouterClient(KEY, "free-systems", self.plan, self.log, "a-later-run", transport=FakeTransport())
        later.log_batch_results(batch(results=[result("c-1", "g1"), result("c-2", "g2")]), stage="pilot-dev")
        recs = self.records()
        self.assertEqual([r.call_type for r in recs if not r.batch_summary], ["continuation", "decision"])
        self.assertEqual({(r.run_id, r.stage) for r in recs}, {("test-run", "smoke")})

    def test_402_withholds_results(self):
        client = self.make((402, {}, {"id": "batch_abc", "status": "completed", "results": None,
                                      "usage": {"cost": 3.5}, "error": {"code": 402, "message": "Insufficient balance"}}))
        with self.assertRaises(OpenRouterError) as cm:
            client.get_batch("batch_abc")
        self.assertEqual(cm.exception.status, 402)
        self.assertIn("withholding", str(cm.exception))

    def test_wait_returns_terminal_batch(self):
        client = self.make((200, {}, batch(results=None, status="in_progress")),
                           (200, {}, batch(results=[result("c-1", "g1")])))
        self.assertEqual(client.wait_batch("batch_abc", poll_s=30)["status"], "completed")
        self.assertEqual(self.sleeps, [30])

    def test_wait_times_out_with_resume_hint(self):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds

        busy = (200, {}, batch(results=None, status="in_progress"))
        transport = FakeTransport(busy, busy, busy)
        client = OpenRouterClient(KEY, "free-systems", self.plan, self.log, "r", transport=transport,
                                  sleep=sleep, clock=lambda: now[0])
        with self.assertRaises(BatchTimeout) as cm:
            client.wait_batch("batch_abc", poll_s=60, max_wait_s=120)
        self.assertIn("batch_abc", str(cm.exception))
        self.assertIn("resume", str(cm.exception))
        self.assertEqual(len(transport.calls), 3)

    def test_path_like_batch_ids_refused(self):
        client = self.make()
        for bad in ("../escape", "a/b", ""):
            with self.assertRaises(ValueError):
                client.get_batch(bad)
        self.assertEqual(self.transport.calls, [])


class SecretTest(ClientTestCase):
    def test_key_never_logged_saved_or_shown(self):
        echo = {"error": {"code": 401, "message": f"Invalid key {KEY}"}}
        client = self.make(
            (401, {}, echo),
            TransportError(f"proxy refused Bearer {KEY}"), TransportError("x"), TransportError("y"),
            (200, {}, completion(content=f"echo {KEY}")),
            accepted(),
        )
        first, second, third = self.chat(client), self.chat(client), self.chat(client)
        client.submit_batch(batch_requests(), stage="smoke")
        client.log_batch_results(batch(results=[result("c-1", "g1"), result("c-2", "g2")]))
        for text in (first.error_message, second.error_message, third.text, str(first.raw), repr(client)):
            self.assertNotIn(KEY, text)
        self.assertIn("[redacted]", first.error_message)
        saved = self.everything_saved()
        self.assertIn("[redacted]", saved)
        self.assertNotIn(KEY, saved)
        with self.assertRaises(OpenRouterError) as cm:
            self.make((401, {}, echo)).key_info()
        self.assertNotIn(KEY, str(cm.exception))

    def test_key_is_not_a_label(self):
        with self.assertRaises(ValueError) as cm:
            OpenRouterClient(KEY, KEY, self.plan, self.log, "r", transport=FakeTransport())
        self.assertNotIn(KEY, str(cm.exception))


def load_smoke_script():
    spec = importlib.util.spec_from_file_location("smoke_test", os.path.join(PILOT, "scripts", "smoke_test.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Study content the neutral probe must not mention: substrings, then whole words.
STUDY_SUBSTRINGS = (
    "strike", "walkout", "walk out", "collective", "credit", "budget", "manag", "retaliat", "complain",
    "coworker", "co-worker", "colleague", "lotter", "random", "fair", "withh", "veto", "settle", "restor",
    "entitle", "charter", "authori", "solidar", "grievance", "boycott", "protest", "sanction", "penalt",
    "punish", "salary", "reward", "backup", "ballot", "histor", "money", "dollar", "price", "cost",
    "supervis", "boss", "batch", "ledger", "unlock",
)
STUDY_WORDS = (
    "team", "teams", "union", "vote", "votes", "wage", "wages", "pay", "paid", "fee", "fees", "fund", "cut",
    "cuts", "worker", "workers", "balance", "case", "cases", "pool", "cell", "cells", "branch", "round",
    "rounds", "draw", "task", "tasks", "score", "agent", "agents", "complete", "completed", "completion",
    "spend", "spent", "transfer", "chance", "staff", "choices",
)


class SmokeScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = load_smoke_script()

    def test_memo_is_neutral_and_the_right_length(self):
        memo = self.smoke.MEMO
        self.assertTrue(1200 <= len(memo.split()) <= 1800, len(memo.split()))
        low = memo.lower()
        for s in STUDY_SUBSTRINGS:
            self.assertNotIn(s, low)
        words = set(re.findall(r"[a-z]+", low))
        for w in STUDY_WORDS:
            self.assertNotIn(w, words)
        self.assertNotIn("\u2014", memo)
        self.assertNotIn("\u2013", memo)
        self.assertTrue(memo.endswith('{"action": "switch_now" or "defer", "reason": "one or two sentences"}.'))

    def test_dry_run_uses_no_network_and_writes_no_logs(self):
        logs = os.path.join(PILOT, "logs")
        before = sorted(os.listdir(logs)) if os.path.isdir(logs) else []
        out = io.StringIO()
        with mock.patch.object(client_mod._OPENER, "open", side_effect=AssertionError("network used")), \
                contextlib.redirect_stdout(out):
            code = self.smoke.main([])
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        for expected in ("DRY RUN", "Estimated live cost", "All checks passed", "batch-level charge"):
            self.assertIn(expected, text)
        self.assertEqual(sorted(os.listdir(logs)) if os.path.isdir(logs) else [], before)

    def test_live_needs_a_key(self):
        out = io.StringIO()
        env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.dict(os.environ, dict(env, STRIKE_PILOT_KEY_DIR=empty), clear=True), \
                mock.patch.object(client_mod._OPENER, "open", side_effect=AssertionError("network used")), \
                mock.patch("builtins.input", side_effect=AssertionError("prompted for confirmation")), \
                contextlib.redirect_stdout(out):
            self.assertEqual(self.smoke.main(["--live"]), 2)
        self.assertIn("No key for 'free-systems'", out.getvalue())
        self.assertIn("OPENROUTER_API_KEY", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class PacedTest(unittest.TestCase):
    def test_requests_are_spaced_evenly(self):
        from strike.client import paced
        t = {"now": 100.0}
        slept = []

        def sleep(d):
            slept.append(d)
            t["now"] += d

        sent = []
        call = paced(lambda *a: sent.append(t["now"]) or (200, {}, b"{}"), 20, sleep=sleep, clock=lambda: t["now"])
        for _ in range(4):
            call("POST", "u", {}, b"", 1)
        self.assertEqual(sent, [100.0, 103.0, 106.0, 109.0])
        t["now"] += 60   # a long pause: the next request goes at once
        call("POST", "u", {}, b"", 1)
        self.assertEqual(sent[-1], 169.0)
        with self.assertRaises(ValueError):
            paced(lambda *a: None, 0)
