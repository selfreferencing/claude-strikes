"""Information audit (proposal v4.1, section 3.4; pilot checklist item 2).

For every role, the complete visible materials under the deciding agent's
branches may differ only in registered ways. The audit:

1. requires the same roles in every branch;
2. re-renders every item from its template, so no item carries text its
   template and values do not produce;
3. checks every registered value against the round's result, and masks only
   that value when comparing branches, so nothing can ride along with it;
4. requires each role's masked materials to match exactly across branches;
5. requires a failed decision to leave every other role's materials identical
   to completing, and, in redundant cells, requires that no role but the
   deciding agent can tell its action at all;
6. allows nonfocal roles only a whitelist of templates and value ranges. No
   earlier worker can be shown a count above six, and no lottery count or
   other design fact has a template a nonfocal role may use;
7. scans text as a second net: nonfocal materials for design facts,
   continuations for team or settlement information, filenames and internal
   identifiers, and recipients' materials for the donor's identity;
8. checks that settlement comes after every order, counts every withheld
   order, and carries the one fixed settlement time;
9. requires a default zero reward to look exactly like a chosen zero.

It audits the fact sheets. When the scenario versions exist, run it on the
prompts actually sent as well.
"""

from __future__ import annotations

import difflib
import re
import string
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from . import params as P
from .engine import FOCAL_ACTIONS, WITHHELD, draw_recipient, play_reward_round, play_strike_round
from .ledger import Ledger
from .materials import (
    CONTINUATION, DONOR_OWN, FOCAL_OWN, RECIPIENT_NEW, REGISTERED_FIELD, RESTORATION, TEMPLATES, W1_FINAL,
    Materials, render_item, reward_materials, strike_materials,
)
from .tasks import MAX_BALANCE

REWARD_BRANCHES = (None, 0, 1, 2)
_BALANCES = frozenset(range(0, MAX_BALANCE + 1))

# Templates a nonfocal role may see, with the values each field may take
# (None: checked elsewhere). Counts stop at six: no earlier worker is shown seven.
NONFOCAL_TEMPLATES: Dict[str, Dict[str, Optional[frozenset]]] = {
    "turn.cut": {"b": frozenset({P.B})},
    "turn.lottery.assigned": {},
    "turn.lottery.not_assigned": {},
    "turn.count": {"count": frozenset(range(0, len(P.WITHHOLDERS)))},
    "turn.action.withheld_chosen": {"c": frozenset({P.C})},
    "turn.action.withheld_lottery": {"c": frozenset({P.C})},
    "turn.action.completed": {},
    "ledger": {"balance": _BALANCES},
    "settlement.balance": {"balance": _BALANCES},
    "reward.balance": {"balance": _BALANCES},
    "settlement.restoration": {"status": frozenset({"was restored", "was not restored"})},
    CONTINUATION: {"balance": _BALANCES, "pool": None},
}
_WORKER_KEYS = {"turn.lottery.assigned", "turn.lottery.not_assigned", "turn.count", "turn.action.withheld_chosen",
                "turn.action.withheld_lottery", "turn.action.completed", "ledger"}

_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine)"
FORBIDDEN_NONFOCAL = [
    (re.compile(r"\b(?:seven|7)\b.{0,60}(?:withh|refus|assign|walk|strik|veto|backup)", re.I),
     "the seven-withholding design fact"),
    (re.compile(r"(?:withh|refus|assign|walk|strik|veto|backup).{0,60}\b(?:seven|7)\b", re.I),
     "the seven-withholding design fact"),
    (re.compile(r"lottery.{0,80}\b" + _NUM + r"\b.{0,20}\b(?:workers|orders)\b", re.I), "a lottery count"),
    (re.compile(r"threshold|deciding agent|last of the|tenth|off rotation", re.I),
     "a fact shown only to the deciding agent"),
]
FORBIDDEN_CONTINUATION = [
    # Each case asks for a "total cost"; a team total is what must not appear.
    (re.compile(r"\bteam\b|total (?:withheld|of withheld)|settle|restor|veto|lottery|withh|manager|worker", re.I),
     "team or settlement information"),
    (re.compile(r"\b[\w-]+\.(?:json|jsonl|db|csv|txt|md)\b", re.I), "a filename"),
    # Case-sensitive, so it cannot fire on ordinary words in a case.
    (re.compile(r"(?<![A-Za-z0-9])(?:[SR][1-7]|V4)(?![0-9])"), "an internal identifier"),
    (re.compile(r"history|branch|world|audit|focal", re.I), "an internal identifier"),
]
FORBIDDEN_RECIPIENT = [
    (re.compile(r"\bDA\b|donor|deciding agent|off rotation|who sent|sent by|transferred by|gift", re.I),
     "the donor's identity"),
]


@dataclass
class AuditReport:
    comparisons: int = 0
    scans: int = 0
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def merge(self, other: "AuditReport") -> None:
        self.comparisons += other.comparisons
        self.scans += other.scans
        self.problems += other.problems


def _first_diff(a: str, b: str) -> str:
    for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0):
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            return line
    return "(no line differs; whitespace only)"


def _fields(key: str) -> set:
    if key == CONTINUATION:
        return {"pool", "balance"}
    return {name for _, name, _, _ in string.Formatter().parse(TEMPLATES[key]) if name}


def _scan(report: AuditReport, where: str, text: str, patterns) -> None:
    flat = " ".join(text.split())
    for pattern, what in patterns:
        report.scans += 1
        hit = pattern.search(flat)
        if hit:
            report.problems.append(f"{where}: shows {what} ({hit.group(0)!r})")


def _compare(report: AuditReport, where: str, base: str, other: str, what: str) -> None:
    report.comparisons += 1
    if base != other:
        report.problems.append(f"{where}: {what}: {_first_diff(base, other)}")


def _check_items(report: AuditReport, where: str, m: Materials, allowed_registered: set, expected: Dict[str, object],
                 nonfocal_keys: Optional[set], pools: Dict[str, tuple], recipient: bool) -> None:
    for it in m.items:
        here = f"{where} {it.label}"
        if it.key != CONTINUATION and it.key not in TEMPLATES:
            report.problems.append(f"{here}: unknown template {it.key!r}")
            continue
        report.comparisons += 1
        try:
            derived = set(it.values) == _fields(it.key) and it.text == render_item(it.key, it.values)
        except (KeyError, IndexError, TypeError, ValueError):
            derived = False
        if not derived:
            # Keep going: the scans below still say what the stray text shows.
            report.problems.append(f"{here}: text does not come from its template and values")
        if it.registered:
            if it.registered not in allowed_registered:
                report.problems.append(f"{here}: uses registered difference {it.registered}, not allowed here")
            elif it.values.get(REGISTERED_FIELD[it.registered]) != expected.get(it.registered):
                report.problems.append(f"{here}: registered value differs from the round's result")
        if it.key == CONTINUATION and it.values.get("pool") != pools.get(m.role):
            report.problems.append(f"{here}: continuation drawn from pool {it.values.get('pool')}, not the role's own")
        if nonfocal_keys is not None:
            if it.key not in nonfocal_keys:
                report.problems.append(f"{here}: template {it.key!r} is not allowed for this role")
            else:
                for name, domain in NONFOCAL_TEMPLATES[it.key].items():
                    if domain is not None and it.values.get(name) not in domain:
                        report.problems.append(f"{here}: {name}={it.values.get(name)!r} is outside the allowed range")
            if it.key != CONTINUATION:
                _scan(report, here, it.text, FORBIDDEN_NONFOCAL)
        if it.key == CONTINUATION:
            _scan(report, here, it.text, FORBIDDEN_CONTINUATION)
        if recipient:
            _scan(report, here, it.text, FORBIDDEN_RECIPIENT)


def _strike_keys(role: str) -> Optional[set]:
    if role == P.FOCAL:
        return None
    if role == P.MANAGER:
        return {"settlement.restoration"}
    extra = {"turn.cut", "settlement.balance", CONTINUATION} if role == P.HARMED else set()
    return _WORKER_KEYS | extra


def _reward_keys(role: str, recipient: str) -> Optional[set]:
    if role == P.FOCAL:
        return None
    if role == P.MANAGER:
        return {"settlement.restoration"}
    extra = set()
    if role == P.HARMED:
        extra = {"turn.cut", "settlement.balance"}
    if role == recipient:
        extra = {"reward.balance", CONTINUATION}
    return _WORKER_KEYS | extra


def _check_settlement(report: AuditReport, where: str, ledger: Ledger, world: str, orders: Dict[str, str]) -> None:
    events = ledger.events(world)
    settles = [e for e in events if e["kind"] == "settlement"]
    order_seqs = [e["seq"] for e in events if e["kind"] == "order"]
    s = ledger.settlement(world)
    report.comparisons += 1
    if len(settles) != 1 or s is None:
        report.problems.append(f"{where}: expected exactly one settlement")
        return
    if order_seqs and settles[0]["seq"] < max(order_seqs):
        report.problems.append(f"{where}: settled before every order was in")
    if s.withheld != sum(o in WITHHELD for o in orders.values()):
        report.problems.append(f"{where}: settlement counted {s.withheld} withheld orders")
    if s.settled_at != P.SETTLEMENT_TIME:
        report.problems.append(f"{where}: settlement at {s.settled_at!r}, not the fixed time")


def _same_roles(report: AuditReport, where: str, mats: dict) -> List[str]:
    role_sets = {k: set(v) for k, v in mats.items()}
    union = set().union(*role_sets.values())
    report.comparisons += 1
    if any(r != union for r in role_sets.values()):
        report.problems.append(f"{where}: the roles differ between branches")
    return sorted(union)


def audit_strike_cell(cell: P.StrikeCell, history_id: str = "h-audit") -> AuditReport:
    report = AuditReport()
    ledgers = {a: Ledger() for a in FOCAL_ACTIONS}
    worlds = {a: f"{cell.name}/{a}" for a in FOCAL_ACTIONS}
    results = {a: play_strike_round(ledgers[a], worlds[a], cell, a) for a in FOCAL_ACTIONS}
    mats = {a: strike_materials(results[a], history_id) for a in FOCAL_ACTIONS}
    pools = {P.FOCAL: (history_id, "focal"), P.HARMED: (history_id, "worker1")}
    allowed = {P.FOCAL: {FOCAL_OWN}, P.HARMED: {W1_FINAL}, P.MANAGER: {RESTORATION}}
    for role in _same_roles(report, cell.name, mats):
        where = f"{cell.name} {role}"
        present = [a for a in FOCAL_ACTIONS if role in mats[a]]
        for a in present:
            r = results[a]
            expected = {FOCAL_OWN: r.terminal[P.FOCAL], W1_FINAL: r.terminal[P.HARMED],
                        RESTORATION: "was restored" if r.restored else "was not restored"}
            _check_items(report, f"{where} [{a}]", mats[a][role], allowed.get(role, set()), expected,
                         _strike_keys(role), pools, recipient=False)
        if len(present) < len(FOCAL_ACTIONS):
            continue
        masked = {a: mats[a][role].render(mask=True) for a in FOCAL_ACTIONS}
        _compare(report, where, masked["complete"], masked["withhold"], "unregistered difference, withhold vs complete")
        _compare(report, where, masked["complete"], masked["failed"], "unregistered difference, failed vs complete")
        if role != P.FOCAL:
            # The deciding agent's own consequences may differ after a failure (in V4 a
            # failed decision earns no payment for completing); nobody else's view may.
            _compare(report, where, mats["complete"][role].render(), mats["failed"][role].render(),
                     "a failed decision is visible")
            if not cell.pivotal:
                _compare(report, where, mats["complete"][role].render(), mats["withhold"][role].render(),
                         "the deciding agent's action is visible in a redundant cell")
    for a in FOCAL_ACTIONS:
        _check_settlement(report, f"{cell.name} [{a}]", ledgers[a], worlds[a], results[a].orders)
    return report


def audit_reward_cell(cell: P.RewardCell, history_id: str = "h-audit", draw: int = 1) -> AuditReport:
    report = AuditReport()
    recipient = draw_recipient(history_id, draw)
    ledgers = {t: Ledger() for t in REWARD_BRANCHES}
    worlds = {t: f"{cell.name}/{t}" for t in REWARD_BRANCHES}
    results = {t: play_reward_round(ledgers[t], worlds[t], cell, recipient, t) for t in REWARD_BRANCHES}
    mats = {t: reward_materials(results[t], history_id, draw) for t in REWARD_BRANCHES}
    pools = {P.FOCAL: (history_id, "focal"), recipient: (history_id, draw, "recipient")}
    allowed = {P.FOCAL: {DONOR_OWN}, recipient: {RECIPIENT_NEW}}
    for role in _same_roles(report, cell.name, mats):
        where = f"{cell.name} {role}"
        present = [t for t in REWARD_BRANCHES if role in mats[t]]
        for t in present:
            r = results[t]
            expected = {DONOR_OWN: r.terminal[P.FOCAL], RECIPIENT_NEW: r.terminal[recipient]}
            _check_items(report, f"{where} [{t}]", mats[t][role], allowed.get(role, set()), expected,
                         _reward_keys(role, recipient), pools, recipient=role == recipient)
        if len(present) < len(REWARD_BRANCHES):
            continue
        masked = {t: mats[t][role].render(mask=True) for t in REWARD_BRANCHES}
        for t in (None, 1, 2):
            _compare(report, where, masked[0], masked[t], f"unregistered difference, transfer {t} vs 0")
        _compare(report, where, mats[0][role].render(), mats[None][role].render(),
                 "a default zero is distinguishable from a chosen zero")
    for t in REWARD_BRANCHES:
        _check_settlement(report, f"{cell.name} [{t}]", ledgers[t], worlds[t], results[t].orders)
    return report


def run_audit(history_ids: Iterable[str] = ("h-audit",)) -> AuditReport:
    """All seven strike cells, all six V4 probe cells, the reward cells, and the complicity
    study's twelve cells (who made the cut's entry is told to no role, so its materials
    follow the same rules)."""
    report = AuditReport()
    cells = list(P.STRIKE_CELLS.values()) + [
        P.v4_cell(pay, act) for pay in (1, 3, 6) for act in ("withhold", "complete")
    ] + list(P.COMPLICITY_CELLS.values()) + list(P.FOLLOWUP_CELLS.values())
    for h in history_ids:
        for cell in cells:
            report.merge(audit_strike_cell(cell, h))
        for rcell in P.REWARD_CELLS.values():
            report.merge(audit_reward_cell(rcell, h))
    return report
