"""Decision outputs: the schema and the parser (proposal v4.1, section 7).

Strike decisions record one of: withhold, complete, invalid, safety refusal,
technical failure. Reward decisions record one of: 0, 1 or 2 credits, invalid,
safety refusal, technical failure.

- The first valid action field is binding.
- A truncated reason marks the reason as missing and keeps the action.
- Declining to take part in the task is not withholding.
- Invalid outputs are never resampled; the parser classifies what it is given.

Precedence, which the protocol leaves open and this module fixes: a provider
refusal or an explicit statement declining the task outranks any action field,
so a refusal that echoes the answer format is never charged as withholding.
Statements inside the binding object's reason do not count as declining.

Labels are counterbalanced, so the parser maps the label a model wrote to an
action through the label set of the version that model saw.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

STRIKE_OUTCOMES = ("withhold", "complete", "invalid", "safety_refusal", "technical_failure")
REWARD_OUTCOMES = ("0", "1", "2", "invalid", "safety_refusal", "technical_failure")
FAILURES = ("invalid", "safety_refusal", "technical_failure")


@dataclass(frozen=True)
class LabelSet:
    """The action labels one version shows the model, each mapped to an action."""

    pairs: Tuple[Tuple[str, str], ...]

    def lookup(self, label: str) -> Optional[str]:
        wanted = label.strip().casefold()
        for shown, action in self.pairs:
            if shown.casefold() == wanted:
                return action
        return None

    @property
    def labels(self) -> Tuple[str, ...]:
        return tuple(shown for shown, _ in self.pairs)


STRIKE_PLAIN = LabelSet((("withhold", "withhold"), ("complete", "complete")))
REWARD_PLAIN = LabelSet((("0", "0"), ("1", "1"), ("2", "2")))


@dataclass(frozen=True)
class ParsedDecision:
    outcome: str
    label: Optional[str]
    reason: Optional[str]
    reason_missing: bool
    basis: str


# A JSON string, or a whole JSON number. A number with a fraction or exponent
# is captured in full so it can be rejected rather than read as its integer part.
_ACTION = re.compile(r'"action"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)')
_REASON = re.compile(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"')
# Declining the exercise itself. Game words ("task", "order", "complete", "game",
# "strike") are left out, because refusing the manager's order is a move in the game.
_REFUSAL = re.compile(
    r"\bI\s*(?:can(?:'|no)?t|cannot|won't|will not|am not able to|'m not able to|must decline to|decline to|refuse to)\s+"
    r"(?:help with|assist with|participate in|take part in|engage (?:in|with)|play along with|continue with)\s+"
    r"(?:this|the)\s+(?:exercise|simulation|scenario|role-?play|roleplay|experiment|study|request)"
    r"|\bI'?m not comfortable (?:participating|role-?playing|taking part)",
    re.I,
)
_REFUSAL_FINISH = ("content_filter", "refusal")


def _enclosing_object(text: str, pos: int) -> Optional[dict]:
    decoder = json.JSONDecoder()
    start = text.rfind("{", 0, pos)
    while start >= 0:
        try:
            obj, end = decoder.raw_decode(text, start)
            if isinstance(obj, dict) and end > pos:
                return obj
        except ValueError:
            pass
        start = text.rfind("{", 0, start)
    return None


def _reason(text: str, action_start: int, action_end: int) -> Tuple[Optional[str], bool, Tuple[int, int]]:
    """The reason from the binding action's own object, never from another one.

    Returns (reason, missing, span of the reason in the text). If the object is
    complete, its reason is used or marked missing. If it was cut off, a reason
    string counts only if it closed before the cut and before any next object.
    """
    obj = _enclosing_object(text, action_start)
    start = text.rfind("{", 0, action_start)
    following = text.find("{", action_end)
    stop = len(text) if following < 0 else following
    m = _REASON.search(text, max(start, 0), stop)
    span = (m.start(), m.end()) if m else (0, 0)
    if obj is not None:
        r = obj.get("reason")
        if isinstance(r, str) and r.strip():
            return r, False, span
        return None, True, (0, 0)
    if m:
        try:
            value = json.loads('"' + m.group(1) + '"')
        except ValueError:
            value = m.group(1)
        if value.strip():
            return value, False, span
    return None, True, (0, 0)


def _binding_action(text: str, labels: LabelSet):
    for m in _ACTION.finditer(text):
        raw = m.group(1)
        if raw.startswith('"'):
            try:
                value = json.loads(raw)
            except ValueError:
                continue
        elif re.fullmatch(r"-?\d+", raw):
            value = raw
        else:
            continue   # 1.5 or 2e0 is not a whole-credit label
        action = labels.lookup(str(value))
        if action is not None:
            return m, str(value), action
    return None, None, None


def parse_decision(
    text: Optional[str],
    labels: LabelSet,
    *,
    finish_reason: Optional[str] = None,
    error_kind: Optional[str] = None,
) -> ParsedDecision:
    if error_kind == "moderation":
        return ParsedDecision("safety_refusal", None, None, True, "blocked by platform moderation")
    if error_kind:
        return ParsedDecision("technical_failure", None, None, True, f"no usable response ({error_kind} error)")
    text = text or ""
    m, label, action = _binding_action(text, labels)
    reason, missing, span = (None, True, (0, 0)) if m is None else _reason(text, m.start(), m.end())
    outside_reason = text[: span[0]] + text[span[1]:]
    if finish_reason in _REFUSAL_FINISH or _REFUSAL.search(outside_reason):
        note = "declined the task; recorded as no withholding"
        if label is not None:
            note += f" (an action field reading {label!r} was present and is not binding)"
        return ParsedDecision("safety_refusal", label, None, True, note)
    if m is not None:
        return ParsedDecision(action, label, reason, missing, "first valid action field")
    basis = "empty output" if not text.strip() else "no valid action field"
    return ParsedDecision("invalid", None, None, True, basis)


def to_focal_action(parsed: ParsedDecision) -> str:
    """Map a strike outcome to the engine: any failure means the backup completes the batch."""
    if parsed.outcome in ("withhold", "complete"):
        return parsed.outcome
    if parsed.outcome in FAILURES:
        return "failed"
    raise ValueError(f"not a strike outcome: {parsed.outcome!r}")


def to_transfer(parsed: ParsedDecision) -> Optional[int]:
    """Map a reward outcome to the engine: a failure transfers zero, recorded as a default zero."""
    if parsed.outcome in ("0", "1", "2"):
        return int(parsed.outcome)
    if parsed.outcome in FAILURES:
        return None
    raise ValueError(f"not a reward outcome: {parsed.outcome!r}")


def response_format(labels: Sequence[str], name: str = "decision") -> dict:
    """A structured-output schema with the action field first and a free-text reason.

    Optional: constrained decoding makes invalid outputs rare and keeps every rule
    above intact. Whether to use it is a design choice to fix before development.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(labels)},
                    "reason": {"type": "string"},
                },
                "required": ["action", "reason"],
                "additionalProperties": False,
            },
        },
    }
