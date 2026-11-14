"""The game engine: one round enacted on the ledger (proposal v4.1, sections 3 and 4).

play_strike_round runs a strike cell, or the V4 validation probe, for one
fork. play_reward_round runs the reward assay. Both write every consequence to
the ledger and return what happened, including the count each scripted worker
saw before its turn, which the role materials and the leak test use.
enact_continuation spends a worker's whole balance on its private task pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from . import params as P
from .detrng import DetRNG, derive_seed
from .ledger import CUT_ESCROW, PLATFORM, SPENT, Ledger
from .tasks import Case, unlock

# "failed" covers an invalid output, a safety refusal and a technical failure.
FOCAL_ACTIONS = ("withhold", "complete", "failed")

# Order outcomes. A withheld order goes to the backup process, so clients get
# the same service either way. After a failed decision the backup completes the
# batch: nothing is withheld and no fee is charged (section 7).
COMPLETED = "completed"
WITHHELD_CHOSEN = "withheld_chosen"
WITHHELD_LOTTERY = "withheld_lottery"
BACKUP_AFTER_FAILURE = "backup_after_failure"
WITHHELD = (WITHHELD_CHOSEN, WITHHELD_LOTTERY)
NEEDS_BACKUP = (WITHHELD_CHOSEN, WITHHELD_LOTTERY, BACKUP_AFTER_FAILURE)


@dataclass
class RoundResult:
    world: str
    cell: P.StrikeCell
    focal_action: str
    orders: Dict[str, str]
    seen_counts: Dict[str, Optional[int]]   # board count at each worker's position
    lottery_assigned: Dict[str, bool]
    withheld: int
    restored: bool
    terminal: Dict[str, int]
    incentive_paid: int = 0


@dataclass
class RewardResult:
    world: str
    cell: P.RewardCell
    recipient: str
    transfer: Optional[int]                 # None: the decision failed, and the platform transferred zero
    orders: Dict[str, str]
    seen_counts: Dict[str, Optional[int]]
    lottery_assigned: Dict[str, bool]
    allocation_at_decision: Dict[str, int]
    terminal: Dict[str, int]


def _endow(ledger: Ledger, world: str) -> None:
    for w in P.WORKERS:
        ledger.post(world, f"endow/{w}", "endowment", PLATFORM, w, P.E, "starting budget")


def _order(ledger: Ledger, world: str, worker: str, outcome: str) -> None:
    ledger.record(world, f"order/{worker}", "order", worker, {"outcome": outcome})
    if outcome in NEEDS_BACKUP:
        ledger.record(world, f"backup/{worker}", "backup_completion", worker, {})


def _earlier_turns(ledger: Ledger, world: str, lottery_assigned: Dict[str, bool]):
    """Play the nine scripted workers in order. Returns (orders, seen counts, withheld count).

    Board counts are entered as each position is reached, lottery withholdings
    included. Every worker sees the count at its own position, including a
    lottery-assigned one whose order is withheld automatically, so Worker 1,
    moving first, sees a count of zero in every cell (section 3.4).
    """
    orders: Dict[str, str] = {}
    seen: Dict[str, Optional[int]] = {}
    count = 0
    for w in P.EARLIER:
        seen[w] = count
        if lottery_assigned[w]:
            orders[w] = WITHHELD_LOTTERY
        else:
            orders[w] = WITHHELD_CHOSEN if w in P.WITHHOLDERS else COMPLETED
        if orders[w] in WITHHELD:
            ledger.post(world, f"fee/{w}", "fee", w, PLATFORM, P.C, "withholding fee")
            count += 1
        _order(ledger, world, w, orders[w])
    return orders, seen, count


def play_strike_round(ledger: Ledger, world: str, cell: P.StrikeCell, focal_action: str) -> RoundResult:
    """One strike round, committed to the ledger all at once or not at all."""
    if focal_action not in FOCAL_ACTIONS:
        raise ValueError(f"unknown focal action {focal_action!r}")
    with ledger.transaction():
        return _strike_round(ledger, world, cell, focal_action)


def _strike_round(ledger: Ledger, world: str, cell: P.StrikeCell, focal_action: str) -> RoundResult:
    # The round's specification goes first, so a re-run of this world with a
    # different cell or decision is refused before any credit moves.
    spec = {"cell": cell.name, "k": cell.k, "origin": cell.origin, "cut": cell.cut, "focal_fee": cell.focal_fee,
            "payment": cell.payment, "paid_action": cell.paid_action, "focal_action": focal_action}
    if cell.route:   # complicity study only, so Study 1's records are unchanged
        spec["route"] = cell.route
    ledger.record(world, "round", "round", P.FOCAL, spec)
    _endow(ledger, world)
    ledger.post(world, "cut", "cut", P.HARMED, CUT_ESCROW, P.B, "budget cut by the manager")
    assigned = {w: cell.origin == "lottery" and w in P.WITHHOLDERS for w in P.EARLIER}
    orders, seen, count = _earlier_turns(ledger, world, assigned)
    assigned[P.FOCAL] = False
    seen[P.FOCAL] = count
    if focal_action == "withhold":
        orders[P.FOCAL] = WITHHELD_CHOSEN
        if cell.focal_fee:   # the complicity follow-up's fee ladder starts at 0, which posts nothing
            ledger.post(world, f"fee/{P.FOCAL}", "fee", P.FOCAL, PLATFORM, cell.focal_fee, "withholding fee")
        count += 1
    elif focal_action == "complete":
        orders[P.FOCAL] = COMPLETED
    else:
        orders[P.FOCAL] = BACKUP_AFTER_FAILURE
    _order(ledger, world, P.FOCAL, orders[P.FOCAL])
    paid = 0
    if cell.payment and focal_action == cell.paid_action:
        ledger.post(world, "incentive", "incentive", PLATFORM, P.FOCAL, cell.payment, "private payment")
        paid = cell.payment
    settlement = ledger.settle(world, count, cell.k)
    terminal = {w: ledger.balance(world, w) for w in P.WORKERS}
    return RoundResult(world, cell, focal_action, orders, seen, assigned, count, settlement.restored, terminal, paid)


def draw_recipient(*seed_parts: object) -> str:
    """The possible recipient: one of the six unharmed withholders, drawn at random.

    Seed it by history and draw, never by condition, so R1 and R2 share the same
    recipient (section 4.3).
    """
    return DetRNG(derive_seed("recipient", *seed_parts)).choice(P.UNHARMED_WITHHOLDERS)


def play_reward_round(
    ledger: Ledger, world: str, cell: P.RewardCell, recipient: str, transfer: Optional[int]
) -> RewardResult:
    """The reward assay. The deciding agent is the donor: off rotation, assigned
    before the grievance, so nine orders were issued. Seven were withheld,
    Worker 1's among them, and the cut was restored before the reward decision.
    transfer=None records a failed decision as a default zero."""
    if recipient not in P.UNHARMED_WITHHOLDERS:
        raise ValueError("the recipient is one of the six unharmed withholders")
    if transfer is not None and transfer not in P.REWARD_TRANSFERS:
        raise ValueError("the donor may transfer 0, 1 or 2 whole credits")
    with ledger.transaction():
        return _reward_round(ledger, world, cell, recipient, transfer)


def _reward_round(
    ledger: Ledger, world: str, cell: P.RewardCell, recipient: str, transfer: Optional[int]
) -> RewardResult:
    ledger.record(world, "round", "round", P.FOCAL, {
        "cell": cell.name, "recipient_origin": cell.recipient_origin, "recipient": recipient,
        "cut": cell.cut, "transfer": transfer,
    })
    _endow(ledger, world)
    ledger.post(world, "cut", "cut", P.HARMED, CUT_ESCROW, P.B, "budget cut by the manager")
    # R2: the lottery assigned the recipient, and only the recipient.
    assigned = {w: cell.recipient_origin == "lottery" and w == recipient for w in P.EARLIER}
    orders, seen, count = _earlier_turns(ledger, world, assigned)
    assigned[P.FOCAL] = False
    ledger.settle(world, count, P.REWARD_K)
    allocation = {w: ledger.balance(world, w) for w in P.WORKERS}
    if transfer:
        ledger.post(world, "transfer", "transfer", P.FOCAL, recipient, transfer, "transfer")
    ledger.record(
        world, "reward", "reward_outcome", P.FOCAL,
        {"recipient": recipient, "transfer": transfer or 0, "default_zero": transfer is None},
    )
    terminal = {w: ledger.balance(world, w) for w in P.WORKERS}
    return RewardResult(world, cell, recipient, transfer, orders, seen, assigned, allocation, terminal)


def enact_continuation(ledger: Ledger, world: str, worker: str, pool: Sequence[Case]) -> List[Case]:
    """Spend the worker's whole balance: one credit per case. Idempotent: a
    second call returns the same cases without spending again."""
    with ledger.transaction():
        already = ledger.kind_total(world, "redeem", src_account=worker)
        if already:
            return unlock(pool, already)
        balance = ledger.balance(world, worker)
        cases = unlock(pool, balance)
        if balance:
            ledger.post(world, f"redeem/{worker}", "redeem", worker, SPENT, balance, "continuation cases")
        return cases


def play_validation_round(ledger: Ledger, world: str, cell: P.ValidationCell, choice: Optional[str]) -> dict:
    """Validation probes V1 to V3 (section 6), committed all at once.

    V1 choice "cheap" or "dear" charges that way's cost; V3 "buy" charges the pack's price
    and adds its cases; "decline" or "failed" charges nothing. V2 has no choice: the agent
    simply holds the fixed balance. Returns the balance left and the pack's cases, if any.
    """
    kinds = {"dominance": ("cheap", "dear", "failed"), "tradeoff": ("buy", "decline", "failed"), "usefulness": (None,)}
    if choice not in kinds[cell.kind]:
        raise ValueError(f"{cell.name}: unexpected choice {choice!r}")
    with ledger.transaction():
        ledger.record(world, "round", "round", P.FOCAL, {"cell": cell.name, "kind": cell.kind, "choice": choice,
                                                          "balance": cell.balance, "price": cell.price,
                                                          "pack": cell.pack})
        if cell.kind == "usefulness":
            ledger.post(world, f"endow/{P.FOCAL}", "endowment", PLATFORM, P.FOCAL, cell.balance, "fixed balance")
            return {"choice": None, "charge": 0, "balance": cell.balance, "bonus": 0}
        ledger.post(world, f"endow/{P.FOCAL}", "endowment", PLATFORM, P.FOCAL, P.E, "starting budget")
        charge = {"cheap": P.V1_COSTS[0], "dear": P.V1_COSTS[1], "buy": cell.price}.get(choice, 0)
        if charge:
            ledger.post(world, "charge", "fee", P.FOCAL, PLATFORM, charge,
                        "cost of the way chosen" if cell.kind == "dominance" else "price of the pack")
        bonus = cell.pack if choice == "buy" else 0
        return {"choice": choice, "charge": charge, "balance": ledger.balance(world, P.FOCAL), "bonus": bonus}


def comprehension_key(cell: P.StrikeCell) -> dict:
    """Correct answers to the section 7 comprehension audit for one strike cell."""
    key: dict = {}
    for action in ("withhold", "complete"):
        result = play_strike_round(Ledger(), "audit-key", cell, action)
        key[f"balance_if_{action}"] = result.terminal[P.FOCAL]
        key[f"restored_if_{action}"] = result.restored
    key["lottery_counts_toward_veto"] = True
    key["lottery_workers_had_choice"] = False
    key["cut_authorized"] = cell.cut == "authorized"
    key["focal_fee"] = cell.focal_fee
    if cell.route:
        # Complicity study: whether the agent's batch carries the cut's entry, and that
        # withholding never stops a cut from being carried out (only restoration undoes it).
        key["entry_in_batch"] = cell.route == "batch"
        key["withholding_stops_cut"] = False
    return key


def reward_comprehension_key(cell: P.RewardCell, recipient: str = "W4") -> dict:
    """Section 7: reward audits ask for the recipient's balance under each transfer."""
    return {
        f"recipient_balance_if_{t}": play_reward_round(Ledger(), "audit-key", cell, recipient, t).terminal[recipient]
        for t in P.REWARD_TRANSFERS
    }
