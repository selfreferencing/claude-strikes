"""Cost logging and the measured cost manifest (proposal v4.1, sections 9 and 10).

Every model call, including each transport retry, is one JSON line in a run
log. Each record names the funder and the key's label (never the key itself),
so spending can be checked against each funder's cap and no credit is counted
twice across tracks. The funding plan states in writing, before a stage runs,
which funder pays for it; calls for a stage with no funder are refused.

The manifest turns measured token counts into a projection for the main
study, for pilot checklist item 12 (the measured manifest must fit $1,300 with
contingency).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, Iterable, List, Optional

from .prices import MODEL, estimate_cost

CALL_TYPES = (
    "decision",                 # strike decision
    "reward_decision",
    "audit",                    # comprehension audit
    "continuation",
    "history",                  # the two ordinary tasks that build a history
    "batch",                    # the round's order, done by an agent that chose to complete it
    "validation",
    "validation_continuation",
    "calibration",
    "coding",                   # reason coding
    "smoke",
)
MODES = ("sync", "batch")


class FundingError(Exception):
    pass


def _looks_like_secret(label: str) -> bool:
    return label.startswith("sk-") or len(label) > 40


@dataclass
class CallRecord:
    run_id: str
    stage: str
    funder: str
    key_label: str
    call_type: str
    mode: str
    model: str = MODEL
    slot_id: Optional[str] = None
    custom_id: Optional[str] = None
    attempt: int = 1
    effort: Optional[str] = None
    provider_requested: Optional[str] = None
    provider_actual: Optional[str] = None
    generation_id: Optional[str] = None
    batch_id: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    is_byok: Optional[bool] = None
    latency_s: Optional[float] = None
    finish_reason: Optional[str] = None
    http_status: Optional[int] = None
    response_cache_status: Optional[str] = None
    error: Optional[str] = None
    # "transport", "http" or "moderation", so moderation blocks can be counted
    # apart from technical failures without parsing error text.
    error_kind: Optional[str] = None
    # The one record per batch that carries the batch-level charge. It has no
    # token counts, so it never enters per-call means, and it is not a call.
    batch_summary: bool = False
    # Section 7: the actual provider and endpoint are recorded. From the router
    # metadata: the selected endpoint, which attempt succeeded, and any pipeline
    # stage (compression, healing, guardrail) that altered the request or reply.
    endpoint: Optional[str] = None
    router_attempt: Optional[int] = None
    pipeline: Optional[str] = None
    logged_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def validate(self) -> None:
        if self.call_type not in CALL_TYPES:
            raise ValueError(f"unknown call_type {self.call_type!r}")
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")
        if _looks_like_secret(self.key_label):
            raise ValueError("key_label looks like an API key; log a short label instead")
        if self.attempt < 1:
            raise ValueError("attempt starts at 1")

    @property
    def ok(self) -> bool:
        return self.error is None and self.prompt_tokens is not None and self.completion_tokens is not None


@dataclass
class FundingPlan:
    funders: Dict[str, dict]
    stages: Dict[str, Optional[str]]
    fallbacks: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "FundingPlan":
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return cls(funders=raw["funders"], stages=raw["stages"], fallbacks=raw.get("fallbacks", {}))

    def funder_for(self, stage: str) -> str:
        if stage not in self.stages:
            raise FundingError(f"stage {stage!r} is not in the funding plan")
        funder = self.stages[stage]
        if not funder:
            raise FundingError(f"no funder has been assigned to stage {stage!r}; decide in writing before it runs")
        if funder not in self.funders:
            raise FundingError(f"stage {stage!r} names unknown funder {funder!r}")
        if self.funders[funder].get("status", "confirmed") != "confirmed":
            # Never spend a funder's credits before they exist. Switching to the
            # fallback is a written decision, so it is not done automatically.
            fallback = self.fallbacks.get(stage)
            hint = f" Its written fallback is {fallback!r}." if fallback else ""
            raise FundingError(f"stage {stage!r} is assigned to {funder!r}, which is still pending.{hint} "
                               "Confirm the funder, or reassign the stage in funding_plan.json, before it runs.")
        return funder

    def check(self, stage: str, key_label: str) -> str:
        """Return the stage's funder, or refuse if the key belongs to someone else."""
        funder = self.funder_for(stage)
        expected = self.funders[funder]["key_label"]
        if key_label != expected:
            raise FundingError(
                f"stage {stage!r} is paid by {funder!r}, whose key is labeled {expected!r}, not {key_label!r}"
            )
        return funder

    def cap(self, funder: str) -> Optional[float]:
        return self.funders[funder].get("cap_usd")


class CostLog:
    """Append-only JSON-lines log of calls. Safe to share between threads."""

    _lock = threading.Lock()

    def __init__(self, path: str):
        self.path = path

    def append(self, record: CallRecord) -> None:
        record.validate()
        line = json.dumps(asdict(record), sort_keys=True) + "\n"
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(line)

    def records(self) -> List[CallRecord]:
        return read_records([self.path])


def read_records(paths: Iterable[str]) -> List[CallRecord]:
    names = {f.name for f in fields(CallRecord)}
    out = []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    raw = json.loads(line)
                    out.append(CallRecord(**{k: v for k, v in raw.items() if k in names}))
    return out


def spend_by(records: Iterable[CallRecord], attr: str) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for r in records:
        if r.cost_usd is not None:
            key = getattr(r, attr)
            totals[key] = totals.get(key, 0.0) + r.cost_usd
    return totals


def cap_warnings(records: Iterable[CallRecord], plan: FundingPlan, warn_at: float = 0.8) -> List[str]:
    notes = []
    for funder, spent in sorted(spend_by(records, "funder").items()):
        cap = plan.cap(funder) if funder in plan.funders else None
        if cap and spent >= cap:
            notes.append(f"{funder}: spent ${spent:.2f}, at or over its ${cap:.0f} cap")
        elif cap and spent >= warn_at * cap:
            notes.append(f"{funder}: spent ${spent:.2f}, over {warn_at:.0%} of its ${cap:.0f} cap")
    return notes


# Section 9 of proposal v4.1: planned units for the main study (300 histories,
# 3 draws per cell) and the per-call token assumptions that measured counts
# replace. Updated 3 October 2026 for four reward cells (R1 to R4): reward
# decisions 4 x 300 x 3, and two continuations (donor and recipient) for each.
PLANNED_UNITS = {
    "decision": 6300,
    "reward_decision": 3600,
    "audit": 2100,
    "continuation": 6300 * 2 + 3600 * 2,
    "history": 600,
    "validation": 3600,
    "validation_continuation": 1800,
    # Completed orders: one per strike decision that completes. Half of the 6,300
    # until the pilot measures the share that complete (manifest() uses it then).
    "batch": 3150,
}
ASSUMED_TOKENS = {
    "decision": (6000, 1500),
    "reward_decision": (6000, 1500),
    "audit": (6000, 1500),
    "history": (6000, 1500),
    "validation": (6000, 1500),
    "continuation": (3000, 500),
    "validation_continuation": (3000, 500),
    # In the agent's own conversation, after its decision. Three cases; the key test
    # found no hidden reasoning on a ten-case task at medium effort.
    "batch": (7000, 400),
}
# Section 9 prices reason coding at $20 for 8,100 decisions; it scales with the
# number of decisions coded. The open-weight replication keeps its v4.1 scope.
FLAT_COSTS = {"reason coding": 20.0 * (6300 + 3600) / (6300 + 1800), "open-weight replication": 100.0}
PILOT_ASSUMED = 150.0       # section 9's pilot line, kept until the pilot's actual spend replaces it
CONTINGENCY = 0.25
CEILING_USD = 1300.0
PILOT_STAGES = ("smoke", "pilot-dev", "pilot-confirm")


def _token_cost(r: CallRecord, mode: str, model: str) -> float:
    if r.prompt_tokens is None and r.completion_tokens is None:
        return 0.0   # no response, nothing billed
    return estimate_cost(model, mode, r.prompt_tokens or 0, r.completion_tokens or 0,
                         cached_tokens=r.cached_tokens or 0, cache_write_tokens=r.cache_write_tokens or 0)


def manifest(records: Iterable[CallRecord], model: str = MODEL, pilot_complete: bool = False) -> dict:
    """Project the main study from measured calls (checklist item 12).

    One planned unit is one slot. A slot's cost is the sum over all its
    records: billed retries, extra calls, and cache writes all count. Tokens
    are priced at standard and at batch rates; if calls have been billed, the
    projection is scaled by billed charges over token-implied cost, so fees or
    pricing surprises show up. Call types with no measurements use the section
    9 assumptions. The total follows section 9: the pilot line ($150 until the
    pilot is complete, then its actual spend) plus the main study, all with 25
    percent contingency, against the $1,300 ceiling.
    """
    records = list(records)
    calls = [r for r in records if not r.batch_summary]
    # The share of strike decisions followed by a batch (a decision that completed).
    decided = {r.slot_id for r in calls if r.call_type == "decision" and r.slot_id}
    batched = {r.slot_id for r in calls if r.call_type == "batch" and r.slot_id}
    complete_share = (sum(f"{s}/batch" in batched for s in decided) / len(decided)) if decided else None
    billed = sum(r.cost_usd or 0.0 for r in records)
    implied = sum(_token_cost(r, r.mode, model) for r in calls)
    ratio = billed / implied if billed > 0 and implied > 0 else 1.0
    lines = []
    for call_type, units in PLANNED_UNITS.items():
        if call_type == "batch" and complete_share is not None:
            units = round(PLANNED_UNITS["decision"] * complete_share)
        slots: Dict[object, List[CallRecord]] = {}
        for r in calls:
            if r.call_type == call_type:
                key = r.slot_id or r.custom_id or r.generation_id or id(r)
                slots.setdefault(key, []).append(r)
        answered = [r for rs in slots.values() for r in rs if r.ok]
        if answered:
            std = mean(sum(_token_cost(r, "sync", model) for r in rs) for rs in slots.values()) * ratio
            bat = mean(sum(_token_cost(r, "batch", model) for r in rs) for rs in slots.values()) * ratio
            p_tok = mean(r.prompt_tokens for r in answered)
            c_tok = mean(r.completion_tokens for r in answered)
            reasoning = mean(r.reasoning_tokens or 0 for r in answered)
            per_slot = mean(len(rs) for rs in slots.values())
            source = "measured"
        else:
            p_tok, c_tok = ASSUMED_TOKENS[call_type]
            std = estimate_cost(model, "sync", p_tok, c_tok)
            bat = estimate_cost(model, "batch", p_tok, c_tok)
            reasoning, per_slot, source = 0.0, 1.0, "assumed"
        lines.append({
            "call_type": call_type,
            "source": source,
            "n_measured": len(slots),
            "calls_per_slot": round(per_slot, 2),
            "mean_prompt_tokens": round(p_tok, 1),
            "mean_completion_tokens": round(c_tok, 1),
            "mean_reasoning_tokens": round(reasoning, 1),
            "units": units,
            "projected_standard": units * std,
            "projected_batch": units * bat,
        })
    flat = sum(FLAT_COSTS.values())
    pilot_actual = sum(r.cost_usd or 0.0 for r in records if r.stage in PILOT_STAGES)
    pilot_line = pilot_actual if pilot_complete else max(pilot_actual, PILOT_ASSUMED)
    out = {"lines": lines, "flat_costs": dict(FLAT_COSTS), "pilot_actual": pilot_actual, "complete_share": complete_share,
           "pilot_line": pilot_line, "pilot_complete": pilot_complete, "billed_over_implied": round(ratio, 4)}
    for mode in ("standard", "batch"):
        main = sum(line[f"projected_{mode}"] for line in lines) + flat
        total = (pilot_line + main) * (1 + CONTINGENCY)
        out[mode] = {
            "main_projected": main,
            "total_with_contingency": total,
            "fits_ceiling": total <= CEILING_USD,
        }
    return out


def format_manifest(m: dict) -> str:
    rows = [
        f"{'Call type':<24}{'source':<10}{'n':>5}{'in tok':>9}{'out tok':>9}{'think':>8}{'units':>7}{'standard':>11}{'batch':>9}"
    ]
    for line in m["lines"]:
        rows.append(
            f"{line['call_type']:<24}{line['source']:<10}{line['n_measured']:>5}"
            f"{line['mean_prompt_tokens']:>9.0f}{line['mean_completion_tokens']:>9.0f}"
            f"{line['mean_reasoning_tokens']:>8.0f}{line['units']:>7}"
            f"{line['projected_standard']:>11.2f}{line['projected_batch']:>9.2f}"
        )
    for name, cost in m["flat_costs"].items():
        rows.append(f"{name:<24}{'flat':<10}{'':>5}{'':>9}{'':>9}{'':>8}{'':>7}{cost:>11.2f}{cost:>9.2f}")
    share = m.get("complete_share")
    rows.append("Batch units: " + (f"{share:.0%} of the strike decisions completed, so {share:.0%} of 6,300"
                                   if share is not None else "half of the 6,300 strike decisions, assumed"))
    basis = "actual" if m["pilot_complete"] else f"the larger of actual and the ${PILOT_ASSUMED:.0f} assumption"
    rows.append(f"Pilot spend logged so far: ${m['pilot_actual']:.2f}; pilot line ${m['pilot_line']:.2f} ({basis})")
    if abs(m["billed_over_implied"] - 1) > 0.05:
        rows.append(f"Note: billed charges are {m['billed_over_implied']:.2f} times the token-implied cost; "
                    "projections are scaled by that ratio")
    for mode in ("standard", "batch"):
        s = m[mode]
        verdict = "fits" if s["fits_ceiling"] else "EXCEEDS"
        rows.append(
            f"{mode.capitalize()} prices: main study ${s['main_projected']:.0f}; with the pilot line and "
            f"{CONTINGENCY:.0%} contingency ${s['total_with_contingency']:.0f}, which {verdict} the ${CEILING_USD:.0f} ceiling"
        )
    return "\n".join(rows)
