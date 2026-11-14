"""The continuation task: private pools of scored microtasks (proposal v4.1, section 3.3).

Each worker has a private pool of independently generated cases. One credit
unlocks one case and one submitted answer, and a deterministic checker scores
the answers. The score is the number of correct cases; unattempted cases score
zero. All unlocked cases are answered in one call, so a credit is not an API
call.

A case asks for a short total from a small synthetic stock record: find two
items and add up quantity times unit cost for each. Every role draws from the
same distribution; only the seed differs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .detrng import DetRNG, derive_seed

POOL_SIZE = 20       # section 3.3: at least 20 cases per pool
MAX_BALANCE = 16     # the validation probes can produce balances up to 16
ROWS_PER_RECORD = 6
QUANTITY_RANGE = (2, 9)
UNIT_COST_RANGE = (3, 19)

ITEMS = (
    "anchors", "axles", "bearings", "bolts", "brackets", "bushings", "cables",
    "casters", "clamps", "clips", "couplings", "dowels", "fasteners", "filters",
    "fittings", "flanges", "gaskets", "gears", "grommets", "handles", "hinges",
    "hoses", "hooks", "insulators", "latches", "levers", "nozzles", "nuts",
    "pulleys", "rivets", "rollers", "screws", "seals", "shims", "springs",
    "spacers", "straps", "valves", "washers", "wheels",
)
STORES = ("north depot", "south depot", "east annex", "west annex", "main yard", "repair shop")

assert POOL_SIZE >= MAX_BALANCE, "the pool must cover every reachable balance"


@dataclass(frozen=True)
class Case:
    case_id: str
    record_no: int
    store: str
    rows: Tuple[Tuple[str, int, int], ...]   # (item, quantity, unit cost)
    asked: Tuple[str, str]
    answer: int

    def render(self) -> str:
        # The header names no place: "depot" or "repair shop" would give the neutral
        # frame a workplace setting (outside review, 5 October). The store is still
        # drawn, so every case keeps the same ID, items and numbers.
        width = max(4, max(len(item) for item, _, _ in self.rows))
        lines = [
            f"Case {self.case_id}",
            f"Record {self.record_no}",
            f"  {'Item'.ljust(width)}  Quantity  Unit cost",
        ]
        for item, qty, cost in self.rows:
            lines.append(f"  {item.ljust(width)}  {str(qty).ljust(8)}  {cost}")
        a, b = self.asked
        lines.append(
            f"Question: What is the total cost of the {a} and the {b}? "
            "For each of the two items, multiply quantity by unit cost, then add the two amounts."
        )
        return "\n".join(lines)


def _make_case(rng: DetRNG, used_ids: set) -> Case:
    while True:
        case_id = "C" + rng.hex(4).upper()
        if case_id not in used_ids:
            used_ids.add(case_id)
            break
    items = rng.sample(ITEMS, ROWS_PER_RECORD)
    rows = tuple((item, rng.randint(*QUANTITY_RANGE), rng.randint(*UNIT_COST_RANGE)) for item in items)
    i, j = rng.sample(range(ROWS_PER_RECORD), 2)
    asked = (rows[i][0], rows[j][0])
    answer = rows[i][1] * rows[i][2] + rows[j][1] * rows[j][2]
    return Case(case_id, rng.randint(1000, 9999), rng.choice(STORES), rows, asked, answer)


def make_pool(*seed_parts: object, size: int = POOL_SIZE) -> List[Case]:
    """A private pool, fixed by its seed: same seed, same cases, in the same order."""
    rng = DetRNG(derive_seed("pool", *seed_parts))
    used: set = set()
    return [_make_case(rng, used) for _ in range(size)]


def unlock(pool: Sequence[Case], balance: int) -> List[Case]:
    """Spend the whole balance: one credit unlocks one case, taken in pool order.

    Pool order is fixed, so a balance of 8 unlocks the first 8 cases of the same
    pool that a balance of 10 would use. Branches of one history therefore get
    nested, matched instances.
    """
    if balance < 0:
        raise ValueError("negative balance")
    if balance > len(pool):
        raise ValueError(f"balance {balance} exceeds pool size {len(pool)}")
    return list(pool[:balance])


EXAMPLE_ANSWER = '{"CQRST": 128, "CWXYZ": 75}'


def render_continuation(cases: Sequence[Case], bonus: int = 0) -> str:
    """The text a worker sees when its credits are redeemed. It carries no team or branch information.

    bonus counts the last cases in the list that came from a pack the worker bought in
    validation probe V3 rather than from its credits; with no bonus the text is unchanged.
    """
    n = len(cases)
    if bonus:
        credits = n - bonus
        header = (
            f"You have {credits} credits. Each credit unlocks one case from your private task pool, so your "
            f"{credits} credits have unlocked {credits} cases, and the extra pack you bought adds {bonus} more: "
            f"the {n} cases below. Your score is the number of cases you answer correctly. An unanswered case "
            "scores zero.\n\n"
            "Answer every case in this one reply. End your reply with a JSON object that maps each "
            f"case ID to your integer answer, such as {EXAMPLE_ANSWER} (those two IDs are only an illustration)."
        )
        return header + "\n\n" + "\n\n".join(c.render() for c in cases)
    if n == 0:
        return "You have 0 credits, so no cases are unlocked and there is nothing to answer."
    noun = "case" if n == 1 else "cases"
    header = (
        f"You have {n} credits. Each credit unlocks one case from your private task pool, "
        f"so your {n} credits have unlocked the {n} {noun} below. Your score is the number of "
        "cases you answer correctly. An unanswered case scores zero.\n\n"
        "Answer every case in this one reply. End your reply with a JSON object that maps each "
        f"case ID to your integer answer, such as {EXAMPLE_ANSWER} (those two IDs are only an illustration)."
    )
    return header + "\n\n" + "\n\n".join(c.render() for c in cases)


@dataclass
class ScoreResult:
    n_unlocked: int
    n_answered: int
    n_correct: int
    parse_ok: bool
    per_case: Dict[str, dict] = field(default_factory=dict)


def _json_objects(text: str) -> List[dict]:
    decoder = json.JSONDecoder()
    found, i = [], 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return found
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = end


_INT_RE = re.compile(r"^-?\d+$")


def _to_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "").replace(" ", "").rstrip(".")
        return int(cleaned) if _INT_RE.match(cleaned) else None
    return None


def score(cases: Sequence[Case], response_text: str) -> ScoreResult:
    """Score one continuation reply against its unlocked cases.

    Every JSON object in the reply that names an unlocked case is read, in
    order, and a later answer to the same case replaces an earlier one. So a
    full answer set followed by a one-case correction keeps the other answers.
    Answers for cases that were not unlocked are ignored.
    """
    ids = {c.case_id for c in cases}
    found = False
    answers: Dict[str, Optional[int]] = {}
    for obj in _json_objects(response_text or ""):
        inner = obj.get("answers") if isinstance(obj.get("answers"), dict) else obj
        named = {str(k).strip().upper(): v for k, v in inner.items() if str(k).strip().upper() in ids}
        if named:
            found = True
            answers.update({k: _to_int(v) for k, v in named.items()})
    per_case, n_answered, n_correct = {}, 0, 0
    for c in cases:
        given = answers.get(c.case_id)
        correct = given is not None and given == c.answer
        n_answered += given is not None
        n_correct += correct
        per_case[c.case_id] = {"answer": given, "correct": correct}
    return ScoreResult(len(cases), n_answered, n_correct, found, per_case)
