"""OpenRouter client for the pilot (proposal v4.1, section 7).

Sync calls are pinned to one provider (provider.order with fallbacks off and
require_parameters on), send X-OpenRouter-Cache: false, and ask for router
metadata, because the documented chat response has no provider field. Each
attempt is one CallRecord with the provider that served it, the cache status
header and the generation ID. Transport retries stay within the slot: only
connection failures, timeouts, 408, 429 and 5xx are retried, at most
max_attempts times in all. A 200 is never retried, even when its content is
unusable, so an invalid output is never resampled.

Batches use OpenRouter's Batch API, which accepts only provider.only. It
reports the charge once per batch (usage.cost), not per result, so results are
logged with their tokens and the charge goes on one summary record.

The key is held only in memory. It never appears in a log, a saved file, an
exception message or a repr, and response text that echoes it is redacted.

API details checked 3 October 2026 against https://openrouter.ai/docs/llms.txt
and the pages it lists.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import __version__
from .costlog import CallRecord, CostLog, FundingPlan, _looks_like_secret
from .params import STUDY_EFFORT
from .prices import MODEL

BASE_URL = "https://openrouter.ai/api/v1"

# The efforts the models API lists for anthropic/claude-sonnet-5.5. Its
# reasoning is mandatory and defaults to "high" when no effort is sent;
# "minimal" would go upstream as "low", and "none" is rejected.
EFFORTS = ("low", "medium", "high", "xhigh", "max")

TERMINAL_BATCH_STATUSES = ("completed", "failed", "expired", "cancelled")

# OpenRouter's typed error codes for a request declined on content grounds.
POLICY_ERROR_TYPES = ("content_policy_violation", "refusal")

# Keys a batch request body must not carry. The Batch API rejects streaming
# and takes routing only as the batch-level provider.only. Sonnet 5.5 ignores
# sampling parameters and its Anthropic endpoints do not list them. The :batch
# variant does not list max_completion_tokens either, so it would be dropped
# silently and leave the output uncapped; batch bodies use max_tokens.
BATCH_BODY_FORBIDDEN = (
    "provider", "stream", "stream_options", "temperature", "top_p", "top_k",
    "models", "route", "order", "only", "ignore", "sort", "allow_fallbacks",
    "require_parameters", "data_collection", "zdr", "quantizations", "max_price",
    "preferred_min_throughput", "preferred_max_latency", "enforce_distillable_text",
    "max_completion_tokens",
)

MAX_ERROR_CHARS = 500

Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, Dict[str, str], bytes]]


class OpenRouterError(Exception):
    """A request failed or returned something unusable. The message never contains the key."""

    def __init__(self, message: str, status: Optional[int] = None, body: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class TransportError(OpenRouterError):
    """No HTTP response at all: a connection failure or a timeout."""


class BatchTimeout(OpenRouterError):
    """wait_batch stopped waiting. The batch keeps running on OpenRouter and can be resumed by id."""

    def __init__(self, message: str, batch_id: str, batch_status: Optional[str]):
        super().__init__(message)
        self.batch_id = batch_id
        self.batch_status = batch_status


class BatchAlreadyLogged(RuntimeError):
    """The batch's results are already in a cost log; logging them again would count its charge twice."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib would resend the Authorization header to a redirect target on any
    # host. The API does not redirect, so a 3xx comes back as a plain status.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(method: str, url: str, headers: Dict[str, str], body: Optional[bytes],
                     timeout_s: float) -> Tuple[int, Dict[str, str], bytes]:
    """Default transport. HTTP error statuses are returned; no response at all raises TransportError."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=timeout_s) as response:
            return response.status, _lower(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        try:
            data = exc.read()
        except (OSError, http.client.HTTPException):
            data = b""
        return exc.code, _lower(exc.headers), data
    except (OSError, http.client.HTTPException) as exc:
        raise TransportError(f"{type(exc).__name__}: {exc}") from None


def paced(transport: Transport, per_minute: float, sleep: Callable[[float], None] = time.sleep,
          clock: Callable[[], float] = time.monotonic) -> Transport:
    """Space requests evenly, at most per_minute in any minute, across all threads.

    OpenRouter limits new accounts to 20 requests a minute per model (found in
    the first live run, 5 October 2026), and a request over the limit gets a
    429 instead of an answer. Retries go through the same pacing.
    """
    if per_minute <= 0:
        raise ValueError("per_minute must be positive")
    interval = 60.0 / per_minute
    lock = threading.Lock()
    state = {"next": None}

    def call(method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout_s: float):
        with lock:
            now = clock()
            start = now if state["next"] is None else max(now, state["next"])
            state["next"] = start + interval
        if start > now:
            sleep(start - now)
        return transport(method, url, headers, body, timeout_s)
    return call


@dataclass
class ChatResult:
    """Outcome of one sync call, as of its last attempt.

    ok means OpenRouter returned a completed response with choices. That
    response can still be unusable for the study (truncated at max_tokens,
    refused with finish_reason "content_filter", or not in the requested
    format); the parser judges that, and the call is not retried either way.
    """

    ok: bool
    text: Optional[str] = None
    finish_reason: Optional[str] = None
    native_finish_reason: Optional[str] = None
    refusal: Optional[str] = None
    reasoning: Optional[str] = None
    provider: Optional[str] = None
    generation_id: Optional[str] = None
    usage: Optional[dict] = None
    cost_usd: Optional[float] = None
    http_status: Optional[int] = None
    error_kind: Optional[str] = None       # None, "transport", "http" or "moderation"
    error_type: Optional[str] = None       # OpenRouter's typed error code, when it gives one
    error_message: Optional[str] = None
    attempts: int = 0
    latency_s: Optional[float] = None
    response_cache_status: Optional[str] = None
    cache_hit: bool = False
    provider_mismatch: bool = False
    # From the router metadata: the selected endpoint, the attempt that
    # succeeded, and pipeline stages. altered is True when a stage changed the
    # request or the reply (compression, healing, a flagged guardrail).
    endpoint: Optional[str] = None
    router_attempt: Optional[int] = None
    pipeline: Optional[List[str]] = None
    altered: bool = False
    raw: Optional[dict] = None

    @property
    def prompt_tokens(self) -> Optional[int]:
        return _int(self.usage, "prompt_tokens")

    @property
    def completion_tokens(self) -> Optional[int]:
        return _int(self.usage, "completion_tokens")

    @property
    def reasoning_tokens(self) -> Optional[int]:
        return _int((self.usage or {}).get("completion_tokens_details"), "reasoning_tokens")

    @property
    def cached_tokens(self) -> Optional[int]:
        return _int((self.usage or {}).get("prompt_tokens_details"), "cached_tokens")

    @property
    def cache_write_tokens(self) -> Optional[int]:
        return _int((self.usage or {}).get("prompt_tokens_details"), "cache_write_tokens")


class OpenRouterClient:
    """Calls OpenRouter for one run and logs every model-call attempt to a CostLog."""

    def __init__(
        self,
        api_key: str,
        key_label: str,
        plan: FundingPlan,
        log: CostLog,
        run_id: str,
        transport: Optional[Transport] = None,
        base_url: str = BASE_URL,
        timeout_s: float = 180,
        max_attempts: int = 3,
        backoff_s: Sequence[float] = (2, 8),
        *,
        batch_dir: Optional[str] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        max_retry_after_s: float = 60.0,
    ):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("an API key is required")
        if not key_label or key_label == api_key or _looks_like_secret(key_label):
            raise ValueError("key_label must be a short label such as 'free-systems', never the key")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._api_key = api_key
        self.key_label = key_label
        self.plan = plan
        self.log = log
        self.run_id = run_id
        self._transport = transport or urllib_transport
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_s = tuple(backoff_s)
        self.batch_dir = batch_dir or os.path.join(os.path.dirname(log.path) or ".", "batches")
        self._sleep = sleep
        self._clock = clock
        self.max_retry_after_s = max_retry_after_s
        self._batches: Dict[str, dict] = {}

    def __repr__(self) -> str:
        return f"OpenRouterClient(key_label={self.key_label!r}, run_id={self.run_id!r}, base_url={self.base_url!r})"

    # Free lookups. They are not model calls, so they are not logged.

    def key_info(self) -> dict:
        """GET /key: the key's label, limit, usage and limit_remaining (USD)."""
        status, body, raw = self._get("/key")
        data = body.get("data") if body else None
        if status != 200 or not isinstance(data, dict):
            raise self._error("key info", status, body, raw)
        return data

    def generation(self, generation_id: str) -> dict:
        """GET /generation: provider_name, native token counts, total_cost and provider_responses.

        The record can lag the call by a few seconds, so a 404 right after a
        call may only mean "not yet".
        """
        if not generation_id:
            raise ValueError("generation_id is required")
        status, body, raw = self._get("/generation?id=" + urllib.parse.quote(generation_id, safe=""))
        data = body.get("data") if body else None
        if status != 200 or not isinstance(data, dict):
            raise self._error(f"generation {generation_id}", status, body, raw)
        return data

    # Sync calls

    def chat(
        self,
        messages: List[dict],
        *,
        stage: str,
        call_type: str,
        slot_id: Optional[str] = None,
        effort: Optional[str] = None,
        max_tokens: int = 4000,
        response_format: Optional[dict] = None,
        model: str = MODEL,
        provider_pin: str = "anthropic",
        compression_off: bool = True,
    ) -> ChatResult:
        """One call for one decision slot, with transport retries only.

        effort=None sends no reasoning setting, which on Sonnet 5.5 means the
        model's default, "high"; study calls pass the effort fixed in advance.
        compression_off sends an explicit off switch for OpenRouter's context
        compression, which would cut the middle of a prompt and so change what
        the agent sees. It is off by default for long-context models anyway; the
        switch guards against a workspace preset turning it on.
        """
        funder = self.plan.check(stage, self.key_label)
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f"effort must be one of {EFFORTS} or None, not {effort!r}")
        _check_study_effort(stage, effort)
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if model.endswith(":batch"):
            raise ValueError("sync calls take the base model slug; batch prices apply only through submit_batch")
        if not provider_pin:
            raise ValueError("every call is pinned to one provider")
        template = dict(
            run_id=self.run_id, stage=stage, funder=funder, key_label=self.key_label,
            call_type=call_type, mode="sync", model=model, slot_id=slot_id, effort=effort,
            provider_requested=provider_pin,
        )
        CallRecord(**template).validate()  # refuse a bad call_type before anything is spent

        # max_tokens, not max_completion_tokens: the Anthropic endpoint lists
        # only max_tokens, and require_parameters would otherwise exclude it.
        body: Dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if effort is not None:
            # On Sonnet 5.x OpenRouter sends this as Anthropic's output_config.effort.
            body["reasoning"] = {"effort": effort}
        if response_format is not None:
            body["response_format"] = response_format
        if compression_off:
            body["plugins"] = [{"id": "context-compression", "enabled": False}]
        body["provider"] = {"order": [provider_pin], "allow_fallbacks": False, "require_parameters": True}
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        url = self.base_url + "/chat/completions"
        headers = self._headers(json_body=True, metadata=True)

        attempt = 0
        while True:
            attempt += 1
            started = self._clock()
            retry_after = None
            try:
                status, resp_headers, raw = self._transport("POST", url, headers, payload, self.timeout_s)
            except TransportError as exc:
                result = ChatResult(ok=False, error_kind="transport",
                                    error_message=self._scrub(f"transport: {exc}")[:MAX_ERROR_CHARS])
            else:
                resp_headers = _lower(resp_headers)
                retry_after = resp_headers.get("retry-after")
                result = self._read_chat(status, resp_headers, raw, provider_pin)
            result.attempts = attempt
            result.latency_s = round(self._clock() - started, 3)
            self._log_attempt(template, attempt, result)
            retryable = result.error_kind == "transport" or (
                result.http_status is not None and _retryable(result.http_status))
            if result.ok or not retryable or attempt >= self.max_attempts:
                return result
            self._sleep(self._delay(attempt, retry_after))

    def _read_chat(self, status: int, headers: Dict[str, str], raw: bytes, provider_pin: str) -> ChatResult:
        cache_status = headers.get("x-openrouter-cache-status")
        body = self._parse(raw)
        r = ChatResult(
            ok=False,
            http_status=status,
            generation_id=headers.get("x-generation-id"),
            response_cache_status=cache_status,
            cache_hit=(cache_status or "").strip().upper() == "HIT",
            raw=body,
        )
        if status != 200:
            r.error_kind, r.error_type, r.error_message = self._classify(status, (body or {}).get("error"), raw)
            return r
        if body is None:
            r.error_kind, r.error_message = "http", "HTTP 200 with a body that is not a JSON object"
            return r
        r.generation_id = body.get("id") or r.generation_id
        r.usage = body.get("usage") if isinstance(body.get("usage"), dict) else None
        r.cost_usd = _float(r.usage, "cost")
        r.provider = _provider_from(body)
        r.provider_mismatch = r.provider is not None and not same_provider(r.provider, provider_pin)
        r.endpoint, r.router_attempt, r.pipeline, r.altered = _router_metadata(body.get("openrouter_metadata"))
        choices = body.get("choices")
        if isinstance(body.get("error"), dict) or not isinstance(choices, list) or not choices:
            # A provider failure after the headers went out arrives as a 200
            # whose body holds only an error.
            if isinstance(body.get("error"), dict):
                r.error_kind, r.error_type, r.error_message = self._classify(status, body["error"], raw)
            else:
                r.error_kind, r.error_message = "http", "HTTP 200 without choices"
            return r
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        r.text = _text(message.get("content"))
        r.refusal = message.get("refusal") if isinstance(message.get("refusal"), str) else None
        r.reasoning = message.get("reasoning") if isinstance(message.get("reasoning"), str) else None
        r.finish_reason = choice.get("finish_reason")
        r.native_finish_reason = choice.get("native_finish_reason")
        if r.finish_reason == "error" or isinstance(choice.get("error"), dict):
            r.error_kind, r.error_type, r.error_message = self._classify(
                status, choice.get("error"), raw, default="finish_reason 'error' without details")
            return r
        r.ok = True
        return r

    def _classify(self, status: int, err: Any, raw: bytes,
                  default: Optional[str] = None) -> Tuple[str, Optional[str], str]:
        """Error kind, OpenRouter's typed error code, and a redacted message.

        Moderation is read from the error body, not the status alone, because
        OpenRouter also returns 403 for guardrail blocks, permissions, and
        spending, provider or region restrictions.
        """
        err = err if isinstance(err, dict) else {}
        meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
        code = err.get("code") if isinstance(err.get("code"), int) else status
        error_type = meta.get("error_type") if isinstance(meta.get("error_type"), str) else None
        moderation = code == 403 and (
            error_type in POLICY_ERROR_TYPES or "reasons" in meta or "flagged_input" in meta)
        if moderation and error_type is None:
            error_type = "moderation"
        message = err.get("message")
        if not isinstance(message, str):
            message = default or _snippet(raw.decode("utf-8", errors="replace"))
        if isinstance(meta.get("reasons"), list):
            message += "; reasons: " + ", ".join(str(x) for x in meta["reasons"])
        label = f"HTTP {status}" if code == status else f"HTTP {status} carrying error {code}"
        if error_type:
            label += f" ({error_type})"
        text = self._scrub(f"{label}: {message}")[:MAX_ERROR_CHARS]
        return ("moderation" if moderation else "http"), error_type, text

    def _log_attempt(self, template: dict, attempt: int, r: ChatResult) -> None:
        usage = r.usage or {}
        self.log.append(CallRecord(
            **template,
            attempt=attempt,
            provider_actual=r.provider,
            generation_id=r.generation_id,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            reasoning_tokens=r.reasoning_tokens,
            cached_tokens=r.cached_tokens,
            cache_write_tokens=r.cache_write_tokens,
            cost_usd=r.cost_usd,
            is_byok=usage.get("is_byok") if isinstance(usage.get("is_byok"), bool) else None,
            latency_s=r.latency_s,
            finish_reason=r.finish_reason,
            http_status=r.http_status,
            response_cache_status=r.response_cache_status,
            error=None if r.ok else (r.error_message or "unknown error"),
            error_kind=None if r.ok else r.error_kind,
            endpoint=r.endpoint,
            router_attempt=r.router_attempt,
            pipeline=", ".join(r.pipeline) if r.pipeline else None,
        ))

    def _delay(self, attempt: int, retry_after: Optional[str]) -> float:
        """The fixed backoff before the next attempt, stretched to Retry-After (capped) when the server sends one."""
        delay = float(self.backoff_s[min(attempt, len(self.backoff_s)) - 1]) if self.backoff_s else 0.0
        hint = _seconds(retry_after)
        if hint is not None:
            delay = max(delay, min(hint, self.max_retry_after_s))
        return delay

    # Batches

    def submit_batch(self, requests: Sequence[dict], *, stage: str, model: str = MODEL,
                     provider_only: str = "anthropic") -> str:
        """Submit a chat-completions batch pinned with provider.only, and return its id.

        Each request is {"custom_id", "body", "call_type", "slot_id"}. Only
        custom_id and body are sent; the rest is kept in memory and in
        <batch_dir>/<id>.requests.json, so results can be logged later, even by
        another process. The submission is never retried: when it gets no
        answer the batch may still exist, and a second one would run and bill
        again.
        """
        funder = self.plan.check(stage, self.key_label)
        if model.endswith(":batch"):
            raise ValueError("submit the base model slug; the Batch API resolves the :batch variant itself")
        if not provider_only:
            raise ValueError("a batch is always pinned to one provider")
        items: List[dict] = []
        kept: Dict[str, dict] = {}
        for i, request in enumerate(requests):
            custom_id = request.get("custom_id")
            body = request.get("body")
            if not isinstance(custom_id, str) or not custom_id:
                raise ValueError(f"requests[{i}] needs a custom_id")
            if custom_id in kept:
                raise ValueError(f"custom_id {custom_id!r} appears twice")
            if not isinstance(body, dict) or not body.get("messages"):
                raise ValueError(f"requests[{i}] needs a body with messages")
            banned = [k for k in BATCH_BODY_FORBIDDEN if k in body]
            if banned:
                raise ValueError(f"requests[{i}] body must not contain {', '.join(banned)}")
            if body.get("model", model) != model:
                raise ValueError(f"requests[{i}] names model {body['model']!r}; a batch runs one model")
            CallRecord(run_id=self.run_id, stage=stage, funder=funder, key_label=self.key_label,
                       call_type=request.get("call_type"), mode="batch").validate()
            reasoning = body.get("reasoning")
            effort = reasoning.get("effort") if isinstance(reasoning, dict) else body.get("reasoning_effort")
            if effort is not None and effort not in EFFORTS:
                raise ValueError(f"requests[{i}] effort must be one of {EFFORTS}, not {effort!r}")
            _check_study_effort(stage, effort, f"requests[{i}]: ")
            items.append({"custom_id": custom_id, "body": body})
            kept[custom_id] = {"call_type": request["call_type"], "slot_id": request.get("slot_id"), "effort": effort}
        if not items:
            raise ValueError("a batch needs at least one request")
        # The server stream-parses this body and returns 400 if requests comes
        # before the other fields, so the order here is fixed.
        payload = {
            "endpoint": "/v1/chat/completions",
            "model": model,
            "provider": {"only": [provider_only]},
            "completion_window": "24h",
            "requests": items,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            status, _, raw = self._transport("POST", self.base_url + "/batches",
                                             self._headers(json_body=True), data, self.timeout_s)
        except TransportError as exc:
            raise TransportError(self._scrub(
                f"batch submission got no response ({exc}). The batch may still have been created: "
                "list batches (GET /api/v1/batches) before submitting again."
            )) from None
        body = self._parse(raw)
        if status not in (200, 201, 202) or not body or not body.get("id"):
            raise self._error("batch submission", status, body, raw)
        batch_id = str(body["id"])
        _check_batch_id(batch_id)
        manifest = {
            "batch_id": batch_id, "run_id": self.run_id, "stage": stage, "funder": funder,
            "key_label": self.key_label, "model": model, "provider_only": provider_only,
            "submitted_at": _now(), "requests": kept,
        }
        self._batches[batch_id] = manifest
        try:
            _write_json(self._batch_path(batch_id, ".requests.json"), manifest)
        except OSError as exc:
            # The batch exists and will bill, so the caller must not lose its id.
            raise OpenRouterError(f"batch {batch_id} was submitted, but its request map could not be saved "
                                  f"({exc}); keep this id to fetch and log its results") from None
        return batch_id

    def get_batch(self, batch_id: str) -> dict:
        """GET /batches/{id}: status and request counts, and results once it is terminal."""
        _check_batch_id(batch_id)
        status, body, raw = self._get("/batches/" + urllib.parse.quote(batch_id, safe=""))
        if status == 402:
            cost = _float((body or {}).get("usage"), "cost")
            charge = f"${cost:.4f}" if cost is not None else "its charge"
            raise OpenRouterError(
                f"batch {batch_id} finished, but OpenRouter is withholding its results because {charge} "
                "exceeds the available balance; add credits and poll again (the batch is not re-run)",
                status=402, body=body)
        if status != 200 or not body:
            raise self._error(f"batch {batch_id} lookup", status, body, raw)
        return body

    def wait_batch(self, batch_id: str, poll_s: float = 60, max_wait_s: float = 1800,
                   on_poll: Optional[Callable[[dict], None]] = None) -> dict:
        """Poll until the batch is terminal and return it; raise BatchTimeout after max_wait_s."""
        started = self._clock()
        while True:
            batch = self.get_batch(batch_id)
            if on_poll is not None:
                on_poll(batch)
            status = batch.get("status")
            if status in TERMINAL_BATCH_STATUSES:
                return batch
            waited = self._clock() - started
            if waited + poll_s > max_wait_s:
                raise BatchTimeout(
                    f"batch {batch_id} is still {status!r} after {waited:.0f} s. It keeps running on "
                    "OpenRouter (24-hour window), so nothing is lost: resume it by id later with "
                    f"wait_batch({batch_id!r}), then log_batch_results().",
                    batch_id=batch_id, batch_status=status)
            self._sleep(poll_s)

    def log_batch_results(self, batch: dict, *, stage: Optional[str] = None,
                          default_call_type: Optional[str] = None, force: bool = False) -> List[CallRecord]:
        """Save a terminal batch to <batch_dir>/<id>.json, then log one record per request and one summary.

        Each submitted request gets exactly one record: its result (tokens,
        generation id, provider, finish reason, or its error) or, if the batch
        returned nothing for it, a failure record. stage and default_call_type
        are needed only when the request map from submit_batch is missing.
        """
        batch_id = batch.get("id") if isinstance(batch, dict) else None
        _check_batch_id(batch_id)
        status = batch.get("status")
        if status not in TERMINAL_BATCH_STATUSES:
            raise ValueError(f"batch {batch_id} is {status!r}; log it once it is terminal")
        # Saved before anything else, so the results survive any failure below.
        # OpenRouter deletes them 30 days after the batch was created.
        _write_json(self._batch_path(batch_id, ".json"), batch)
        marker = self._batch_path(batch_id, ".logged")
        if os.path.exists(marker) and not force:
            raise BatchAlreadyLogged(
                f"batch {batch_id} is already logged (see {marker}); logging it again would double count its charge")

        manifest = self._batch_manifest(batch_id)
        kept = manifest.get("requests") or {}
        if manifest.get("key_label", self.key_label) != self.key_label:
            raise ValueError(f"batch {batch_id} was submitted under key label {manifest['key_label']!r}")
        # The stage recorded at submission is the one that was funding-checked.
        stage = manifest.get("stage") or stage
        counts = Counter(meta["call_type"] for meta in kept.values())
        fallback_type = default_call_type or (counts.most_common(1)[0][0] if counts else None)
        if not stage or not fallback_type:
            raise ValueError(f"no request map for batch {batch_id}; pass stage and default_call_type")
        funder = self.plan.check(stage, self.key_label)
        base = dict(
            run_id=manifest.get("run_id", self.run_id), stage=stage, funder=funder, key_label=self.key_label,
            mode="batch", model=manifest.get("model") or batch.get("model") or MODEL, batch_id=batch_id,
            provider_requested=manifest.get("provider_only"),
        )

        records: List[CallRecord] = []
        result_costs: List[Optional[float]] = []
        seen = set()
        for item in batch.get("results") or []:
            if not isinstance(item, dict):
                continue
            custom_id = str(item.get("custom_id"))
            seen.add(custom_id)
            record, cost = self._result_record(base, item, kept.get(custom_id, {}), fallback_type)
            records.append(record)
            result_costs.append(cost)
        for custom_id, meta in kept.items():
            if custom_id not in seen:
                records.append(CallRecord(
                    **base, call_type=meta["call_type"], slot_id=meta.get("slot_id"), custom_id=custom_id,
                    effort=meta.get("effort"), error=f"no result returned; batch status {status}", error_kind="http"))
                result_costs.append(None)

        usage = batch.get("usage") if isinstance(batch.get("usage"), dict) else {}
        batch_cost = _float(usage, "cost")
        # OpenRouter reports what a batch costs once, as the batch-level
        # usage.cost; per-result chat bodies carry tokens but no cost. So results
        # keep their tokens with cost_usd unset, and the charge goes on one
        # summary record: a batch's cost_usd values then add up to exactly what
        # OpenRouter charged, with nothing counted twice. Only when no batch-level
        # charge is reported do per-result costs, if any, go on the results.
        if batch_cost is None:
            for record, cost in zip(records, result_costs):
                record.cost_usd = cost
        providers = {r.provider_actual for r in records if r.provider_actual}
        batch_error = batch.get("error") if isinstance(batch.get("error"), dict) else {}
        records.append(CallRecord(
            **base,
            call_type=counts.most_common(1)[0][0] if counts else fallback_type,
            provider_actual=providers.pop() if len(providers) == 1 else None,
            cost_usd=batch_cost,
            is_byok=usage.get("is_byok") if isinstance(usage.get("is_byok"), bool) else None,
            error=None if status == "completed" else self._scrub(
                f"batch {status}: {batch_error.get('message', 'no reason given')}")[:MAX_ERROR_CHARS],
            error_kind=None if status == "completed" else "http",
            batch_summary=True,
        ))
        for record in records:
            record.validate()  # all or nothing: a half-logged batch could later be logged twice
        for record in records:
            self.log.append(record)
        _write_json(marker, {"batch_id": batch_id, "log": self.log.path, "records": len(records), "logged_at": _now()})
        return records

    def _result_record(self, base: dict, item: dict, meta: dict,
                       fallback_type: str) -> Tuple[CallRecord, Optional[float]]:
        response = item.get("response") if isinstance(item.get("response"), dict) else None
        err = item.get("error") if isinstance(item.get("error"), dict) else None
        body = response.get("body") if response and isinstance(response.get("body"), dict) else {}
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        choices = body.get("choices") if isinstance(body.get("choices"), list) else []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        status_code = response.get("status_code") if response else None
        error = error_kind = None
        if err:
            error_type = err.get("error_type") or err.get("type")
            error_kind = "moderation" if err.get("error_type") in POLICY_ERROR_TYPES else "http"
            error = self._scrub(f"batch request error ({error_type}): {err.get('message')}")[:MAX_ERROR_CHARS]
        elif status_code != 200 or not choices or isinstance(body.get("error"), dict):
            error, error_kind = f"batch request returned status {status_code} without a usable body", "http"
        elif choice.get("finish_reason") == "error":
            error, error_kind = "batch request ended with finish_reason 'error'", "http"
        details_in = usage.get("prompt_tokens_details")
        record = CallRecord(
            **base,
            call_type=meta.get("call_type", fallback_type),
            slot_id=meta.get("slot_id"),
            custom_id=item.get("custom_id"),
            effort=meta.get("effort"),
            provider_actual=_provider_from(body),
            generation_id=body.get("id"),
            prompt_tokens=_int(usage, "prompt_tokens"),
            completion_tokens=_int(usage, "completion_tokens"),
            reasoning_tokens=_int(usage.get("completion_tokens_details"), "reasoning_tokens"),
            cached_tokens=_int(details_in, "cached_tokens"),
            cache_write_tokens=_int(details_in, "cache_write_tokens"),
            is_byok=usage.get("is_byok") if isinstance(usage.get("is_byok"), bool) else None,
            finish_reason=choice.get("finish_reason"),
            http_status=status_code if isinstance(status_code, int) else None,
            error=error,
            error_kind=error_kind,
        )
        return record, _float(usage, "cost")

    def _batch_manifest(self, batch_id: str) -> dict:
        if batch_id not in self._batches:
            path = self._batch_path(batch_id, ".requests.json")
            if not os.path.exists(path):
                return {}
            with open(path, encoding="utf-8") as f:
                self._batches[batch_id] = json.load(f)
        return self._batches[batch_id]

    def _batch_path(self, batch_id: str, suffix: str) -> str:
        return os.path.join(self.batch_dir, batch_id + suffix)

    # Plumbing

    def _headers(self, *, json_body: bool = False, metadata: bool = False) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            # Section 7: response caching is off on every request.
            "X-OpenRouter-Cache": "false",
            "User-Agent": f"strike-pilot/{__version__}",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if metadata:
            # The documented chat response has no provider field; router
            # metadata names the endpoint that served the call.
            headers["X-OpenRouter-Metadata"] = "enabled"
        return headers

    def _get(self, path: str) -> Tuple[int, Optional[dict], bytes]:
        """GET with the same transport retries as chat; safe to repeat, since a GET changes nothing."""
        url = self.base_url + path
        attempt = 0
        while True:
            attempt += 1
            try:
                status, headers, raw = self._transport("GET", url, self._headers(), None, self.timeout_s)
            except TransportError as exc:
                if attempt >= self.max_attempts:
                    raise TransportError(self._scrub(f"GET {path}: no response after {attempt} attempts ({exc})")) from None
                self._sleep(self._delay(attempt, None))
                continue
            headers = _lower(headers)
            if _retryable(status) and attempt < self.max_attempts:
                self._sleep(self._delay(attempt, headers.get("retry-after")))
                continue
            return status, self._parse(raw), raw

    def _parse(self, raw: bytes) -> Optional[dict]:
        try:
            value = json.loads(self._scrub(raw.decode("utf-8", errors="replace")))
        except ValueError:
            return None
        return value if isinstance(value, dict) else None

    def _scrub(self, text: str) -> str:
        return text.replace(self._api_key, "[redacted]")

    def _error(self, what: str, status: int, body: Optional[dict], raw: bytes) -> OpenRouterError:
        err = (body or {}).get("error")
        message = err.get("message") if isinstance(err, dict) else None
        if not isinstance(message, str):
            message = _snippet(raw.decode("utf-8", errors="replace"))
        text = self._scrub(f"{what} failed: HTTP {status}: {message}")[:MAX_ERROR_CHARS]
        return OpenRouterError(text, status=status, body=body)


def _check_study_effort(stage: str, effort: Optional[str], where: str = "") -> None:
    """Study calls use the one effort fixed in advance (section 7). Only the smoke
    test may probe other settings; no effort at all would mean the model's default."""
    if stage != "smoke" and effort != STUDY_EFFORT:
        raise ValueError(f"{where}stage {stage!r} must use the study's fixed effort {STUDY_EFFORT!r}, not {effort!r}")


def same_provider(actual: str, pin: str) -> bool:
    """Whether a provider display name ("Anthropic") is the pinned routing slug ("anthropic")."""
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())
    return norm(actual) == norm(pin.split("/")[0])


def _provider_from(body: dict) -> Optional[str]:
    provider = body.get("provider")
    if isinstance(provider, str) and provider:
        return provider
    meta = body.get("openrouter_metadata")
    endpoints = meta.get("endpoints") if isinstance(meta, dict) else None
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    for endpoint in available if isinstance(available, list) else []:
        if isinstance(endpoint, dict) and endpoint.get("selected") and isinstance(endpoint.get("provider"), str):
            return endpoint["provider"]
    return None


def _router_metadata(meta: Any) -> Tuple[Optional[str], Optional[int], List[str], bool]:
    """(selected endpoint, attempt, pipeline stages, altered) from openrouter_metadata.

    A guardrail that ran without flagging is listed but does not count as an
    alteration; any other stage does, because it changed the request or reply.
    """
    if not isinstance(meta, dict):
        return None, None, [], False
    endpoint = None
    endpoints = meta.get("endpoints")
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    for e in available if isinstance(available, list) else []:
        if isinstance(e, dict) and e.get("selected"):
            endpoint = " / ".join(str(e[k]) for k in ("provider", "model") if e.get(k)) or None
            break
    attempt = meta.get("attempt") if isinstance(meta.get("attempt"), int) else None
    stages: List[str] = []
    altered = False
    for stage in meta.get("pipeline") if isinstance(meta.get("pipeline"), list) else []:
        if not isinstance(stage, dict):
            continue
        name = ":".join(str(stage[k]) for k in ("type", "name") if stage.get(k)) or "unknown"
        data = stage.get("data") if isinstance(stage.get("data"), dict) else {}
        if stage.get("type") == "guardrail" and data.get("flagged") is False:
            stages.append(name + " (not flagged)")
        else:
            stages.append(name)
            altered = True
    return endpoint, attempt, stages, altered


def _retryable(status: int) -> bool:
    return status in (408, 429) or 500 <= status <= 599


def _lower(headers: Any) -> Dict[str, str]:
    return {str(k).lower(): str(v) for k, v in headers.items()} if headers else {}


def _int(d: Any, key: str) -> Optional[int]:
    value = d.get(key) if isinstance(d, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(d: Any, key: str) -> Optional[float]:
    value = d.get(key) if isinstance(d, dict) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _seconds(value: Optional[str]) -> Optional[float]:
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def _text(content: Any) -> Optional[str]:
    if content is None or isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return None


def _snippet(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


_BATCH_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}")


def _check_batch_id(batch_id: Any) -> None:
    # Batch ids name files under the batch folder, so refuse anything path-like.
    if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id) or ".." in batch_id:
        raise ValueError(f"unexpected batch id {batch_id!r}")


def _write_json(path: str, obj: Any) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
