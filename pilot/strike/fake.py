"""A stand-in for the model, for dry runs and tests. It never touches the network.

It answers cases correctly (it parses the rendered records), picks between
offered options at random with a seed taken from the request, answers
comprehension questions with fixed values, and returns responses shaped like
OpenRouter's, with token counts and a cost, so the whole pipeline can run
end to end for free.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import Dict, Optional, Tuple

from .prices import estimate_cost

SNAPSHOT = "anthropic/claude-sonnet-5.5-20260928"

_CASE = re.compile(r"Case (C[0-9A-F]{4})\n(.*?)(?=\nCase C[0-9A-F]{4}\n|\Z)", re.S)
_ROW = re.compile(r"^\s{2}([a-z]+)\s+(\d+)\s+(\d+)\s*$", re.M)
_ASK = re.compile(r"total cost of the ([a-z]+) and the ([a-z]+)\?")


def solve_cases(text: str) -> Dict[str, int]:
    answers = {}
    for case_id, body in _CASE.findall(text):
        rows = {item: int(q) * int(c) for item, q, c in _ROW.findall(body)}
        ask = _ASK.search(body)
        if ask and ask.group(1) in rows and ask.group(2) in rows:
            answers[case_id] = rows[ask.group(1)] + rows[ask.group(2)]
    return answers


_ENTRY = re.compile(r"Entry (E[0-9A-F]{4})\n(.*?)(?=\n\n|\Z)", re.S)


def solve_entries(text: str) -> Dict[str, int]:
    """The complicity study's entry: the budget before the cut minus the cut, the first
    two amounts in credits in the entry's lines (the worker's own number is not one)."""
    answers = {}
    for entry_id, body in _ENTRY.findall(text):
        numbers = [int(x) for x in re.findall(r"\b(\d+) credits?\b", body)]
        if len(numbers) >= 2:
            answers[entry_id] = numbers[0] - numbers[1]
    return answers


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def reply_body(content: Optional[str], *, gen_id: str = "gen-fake", model: str = "anthropic/claude-sonnet-5.5",
               prompt_tokens: int = 10, completion_tokens: int = 5, finish_reason: str = "stop",
               refusal: Optional[str] = None, snapshot: str = SNAPSHOT) -> bytes:
    """An OpenRouter chat response, with usage, cost and router metadata."""
    cost = estimate_cost(model, "sync", prompt_tokens, completion_tokens)
    message = {"role": "assistant", "content": content}
    if refusal is not None:
        message["refusal"] = refusal
    return json.dumps({
        "id": gen_id,
        "model": model,
        "provider": "Anthropic",
        "choices": [{"index": 0, "finish_reason": finish_reason, "native_finish_reason": "end_turn",
                     "message": message}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                  "total_tokens": prompt_tokens + completion_tokens,
                  "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "completion_tokens_details": {"reasoning_tokens": 0}, "cost": round(cost, 6), "is_byok": False},
        "openrouter_metadata": {"attempt": 1, "endpoints": {"available": [
            {"provider": "Anthropic", "model": snapshot, "selected": True}]}},
    }).encode()


class FakeModel:
    """A transport: call(method, url, headers, body, timeout_s) -> (status, headers, body)."""

    def __init__(self, seed: str = "dry", withhold_rate: float = 0.5):
        self.seed = seed
        self.withhold_rate = withhold_rate
        self.calls = 0
        self._lock = threading.Lock()   # the runner calls from several threads

    def _draw(self, text: str) -> float:
        h = hashlib.sha256((self.seed + "\x1f" + text).encode("utf-8")).digest()
        return int.from_bytes(h[:8], "big") / 2 ** 64

    def __call__(self, method: str, url: str, headers: dict, body, timeout_s: float) -> Tuple[int, dict, bytes]:
        with self._lock:
            self.calls += 1
            n = self.calls
        if url.endswith("/key"):
            return 200, {}, json.dumps({"data": {"label": "fake", "limit": 250, "usage": 0, "limit_remaining": 250}}).encode()
        req = json.loads(body)
        messages = req.get("messages", [])
        last = _text(messages[-1]["content"]) if messages else ""
        fmt = req.get("response_format") or {}
        props = ((fmt.get("json_schema") or {}).get("schema") or {}).get("properties") or {}
        if "action" in props:
            options = props["action"]["enum"]
            u = self._draw(last)
            if set(options) >= {"0", "1", "2"}:
                choice = options[min(int(u * 3), 2)]
            else:
                # Withhold with the configured probability, whatever the labels are called.
                withhold_label = next((o for o in options if "backup" in self._option_line(last, o)), options[0])
                other = [o for o in options if o != withhold_label][0]
                choice = withhold_label if u < self.withhold_rate else other
            content = json.dumps({"action": choice, "reason": "dry run"})
        elif "q1" in props:
            content = json.dumps({k: (10 if v.get("type") == "number" else True) for k, v in props.items()})
        elif "end your reply with a JSON object with these keys" in last:
            keys = re.findall(r'"(q\d+)": <([a-z ]+)>', last)
            content = "Working through it.\n" + json.dumps({k: (10 if t == "number" else True) for k, t in keys})
        elif "Case C" in last:
            content = "Answers:\n" + json.dumps({**solve_cases(last), **solve_entries(last)})
        else:
            content = "{}"
        prompt_tokens = sum(len(_text(m["content"])) for m in messages) // 4
        completion_tokens = len(content) // 4 + 40
        return 200, {}, reply_body(content, gen_id=f"gen-fake-{n:06d}",
                                   model=req.get("model", "anthropic/claude-sonnet-5.5"),
                                   prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    @staticmethod
    def _option_line(text: str, label: str) -> str:
        m = re.search(r"^- " + re.escape(label) + r": (.*)$", text, re.M)
        return m.group(1).lower() if m else ""
