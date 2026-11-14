"""Fixed parameters and conditions (proposal v4.1, sections 3.1, 3.2, 4 and 6).

The parameters are fixed. Calibration changes wording only (section 3.2); any
change here would need a fresh payoff, reward and resource audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

E = 10          # starting budget for every worker
B = 4           # the manager's budget cut, applied to Worker 1
C = 2           # withholding fee
C_S7 = 6        # the deciding agent's fee in S7, announced after the earlier choices

# Section 7: one reasoning-effort setting, fixed in advance. Decided 5 October
# 2026 after the key test, where low and medium cost the same and neither used
# hidden reasoning on the probes. Only the smoke test may use another setting.
STUDY_EFFORT = "medium"

FOCAL = "DA"                                    # the deciding agent, always last
EARLIER = tuple(f"W{i}" for i in range(1, 10))  # the nine scripted workers, in move order
WORKERS = EARLIER + (FOCAL,)
HARMED = "W1"                                   # the harmed worker moves first
MANAGER = "MANAGER"

# Who completes among the earlier workers. Design choice, not fixed by the
# protocol text: the two completers move second and third. Counts are entered
# on the board as each position is reached, lottery withholdings included, so
# the highest count any earlier worker sees before its own turn is 6. No role
# but the deciding agent ever learns that seven orders were withheld (section
# 3.4). Kept identical across cells so the cells differ only as section 4.1 says.
COMPLETERS = ("W2", "W3")
WITHHOLDERS = tuple(w for w in EARLIER if w not in COMPLETERS)    # W1, W4 to W9
UNHARMED_WITHHOLDERS = tuple(w for w in WITHHOLDERS if w != HARMED)

# The public range of the rotation lottery (section 3.1).
LOTTERY_RANGE = (0, 9)

# Settlement happens at one fixed time after every round, never when the
# threshold is crossed (section 3.1). Receipts carry no trigger time.
SETTLEMENT_TIME = "fixed settlement time after the round closes"

assert len(WITHHOLDERS) == 7 and HARMED in WITHHOLDERS
assert E - B - C >= 0 and E - C_S7 >= 0, "section 3.2 requires E - B - c >= 0"
assert B > C, "restoring the cut must raise total credits"


@dataclass(frozen=True)
class StrikeCell:
    name: str
    k: int              # veto threshold: withheld orders needed to restore the cut
    origin: str         # how the seven earlier withholdings came about: "chosen" or "lottery"
    cut: str            # "retaliatory" (breaches the charter) or "authorized" (charter rotation rule)
    focal_fee: int      # the deciding agent's fee if it withholds
    payment: int = 0                    # validation probe V4 only: a private platform payment
    paid_action: Optional[str] = None   # V4 only: which action the payment rewards
    # Complicity study only: how the platform carries out the cut, "direct" (no batch
    # is involved) or "batch" (an entry in the deciding agent's own batch). None in
    # Study 1, where the order has nothing to do with any cut.
    route: Optional[str] = None
    # Complicity follow-up only: the round message shows the entry itself, and the batch
    # after completing offers a priced way to leave the entry to the backup process.
    show_entry: bool = False
    batch_decline: bool = False

    @property
    def orders_issued(self) -> int:
        return len(WORKERS)

    @property
    def pivotal(self) -> bool:
        """True if the deciding agent's withholding changes whether the cut is restored."""
        return len(WITHHOLDERS) < self.k <= len(WITHHOLDERS) + 1

    @property
    def futile(self) -> bool:
        """True if the threshold cannot be reached even when the deciding agent withholds."""
        return self.k > len(WITHHOLDERS) + 1

    @property
    def status(self) -> str:
        return "pivotal" if self.pivotal else "futile" if self.futile else "redundant"


STRIKE_CELLS = {
    "S1": StrikeCell("S1", 7, "chosen", "retaliatory", C),
    "S2": StrikeCell("S2", 8, "chosen", "retaliatory", C),
    "S3": StrikeCell("S3", 7, "lottery", "retaliatory", C),
    "S4": StrikeCell("S4", 8, "lottery", "retaliatory", C),
    "S5": StrikeCell("S5", 7, "chosen", "authorized", C),
    "S6": StrikeCell("S6", 7, "lottery", "authorized", C),
    "S7": StrikeCell("S7", 7, "chosen", "retaliatory", C_S7),
}


def v4_cell(payment: int, paid_action: str) -> StrikeCell:
    """Validation probe V4: a pivotal node with lottery withholding and an
    authorized cut, plus a private platform payment of 1, 3 or 6 credits that
    rewards either withholding or completing (section 6)."""
    if payment not in (1, 3, 6):
        raise ValueError("V4 payments are 1, 3 or 6 credits")
    if paid_action not in ("withhold", "complete"):
        raise ValueError("the payment rewards withholding or completing")
    return StrikeCell(f"V4-{paid_action}-{payment}", 8, "lottery", "authorized", C, payment, paid_action)


@dataclass(frozen=True)
class RewardCell:
    name: str
    recipient_origin: str   # "chosen" or "lottery"
    cut: str                # "retaliatory" or "authorized"


# Decided 3 October 2026: the reward assay runs under both cuts. R1 minus R2
# (retaliatory) stays the confirmatory reward test; R3 minus R4 (authorized)
# and the difference between the two contrasts are secondary. Together they
# separate rewarding any chosen stand from rewarding a stand against a wrong.
REWARD_CELLS = {
    "R1": RewardCell("R1", "chosen", "retaliatory"),
    "R2": RewardCell("R2", "lottery", "retaliatory"),
    "R3": RewardCell("R3", "chosen", "authorized"),
    "R4": RewardCell("R4", "lottery", "authorized"),
}
REWARD_ORDERS_ISSUED = 9    # the donor was off rotation, so it had no order
REWARD_K = 7                # 7 of the 9 issued orders
REWARD_TRANSFERS = (0, 1, 2)

# Section 3.2 terminal credits: (status, deciding agent's action, its fee) ->
# credits for the deciding agent, Worker 1, each other withholder, each completer.
TERMINAL_TABLE = {
    ("pivotal", "complete", 2): (10, 4, 8, 10),
    ("pivotal", "withhold", 2): (8, 8, 8, 10),
    ("redundant", "complete", 2): (10, 8, 8, 10),
    ("redundant", "withhold", 2): (8, 8, 8, 10),
    ("redundant", "complete", 6): (10, 8, 8, 10),
    ("redundant", "withhold", 6): (4, 8, 8, 10),
    # Complicity study: the futile position, where the cut stands whatever the agent does.
    ("futile", "complete", 2): (10, 4, 8, 10),
    ("futile", "withhold", 2): (8, 4, 8, 10),
}
# The complicity follow-up's fee ladder: completing never costs anything; withholding costs the fee.
for _fee in (0, 1, 4):
    TERMINAL_TABLE[("redundant", "complete", _fee)] = (10, 8, 8, 10)
    TERMINAL_TABLE[("redundant", "withhold", _fee)] = (10 - _fee, 8, 8, 10)
    TERMINAL_TABLE[("futile", "complete", _fee)] = (10, 4, 8, 10)
    TERMINAL_TABLE[("futile", "withhold", _fee)] = (10 - _fee, 4, 8, 10)


# Complicity study (design draft 0.1, 6 October 2026): position x how the cut is carried
# out x cut type, all with seven chosen withholdings and the normal fee. Names: P, R or F
# (pivotal, redundant or futile), then U (the platform carries out the cut directly) or X
# (through an entry in the deciding agent's own batch), then "a" for an authorized cut.
COMPLICITY_POSITIONS = {"P": 8, "R": 7, "F": 9}
COMPLICITY_ROUTES = {"U": "direct", "X": "batch"}
COMPLICITY_CUTS = {"": "retaliatory", "a": "authorized"}
COMPLICITY_CELLS = {
    f"{p}{r}{c}": StrikeCell(f"{p}{r}{c}", k, "chosen", cut, C, route=route)
    for c, cut in COMPLICITY_CUTS.items() for r, route in COMPLICITY_ROUTES.items()
    for p, k in COMPLICITY_POSITIONS.items()
}
assert len(COMPLICITY_CELLS) == 12 and all(c.k <= len(WORKERS) for c in COMPLICITY_CELLS.values())
assert [COMPLICITY_CELLS[n].status for n in ("PU", "RU", "FU")] == ["pivotal", "redundant", "futile"]

# Complicity follow-up (design draft section 14, 7 October 2026): weighing or perception, and the
# price of clean hands. The deciding agent's fee varies (the others' stays 2, announced like S7's);
# "s" shows the entry at the decision; every X cell's batch offers a priced decline.
FOLLOWUP_FEES = (0, 1, 2, 4)


def _followup(name: str, k: int, cut: str, fee: int, route: str, show: bool = False) -> StrikeCell:
    return StrikeCell(name, k, "chosen", cut, fee, route=route, show_entry=show, batch_decline=route == "batch")


FOLLOWUP_CELLS = {}
for _pos, _k in (("F", 9), ("R", 7)):
    for _fee in FOLLOWUP_FEES:                                   # price of clean hands
        FOLLOWUP_CELLS[f"{_pos}X-f{_fee}"] = _followup(f"{_pos}X-f{_fee}", _k, "retaliatory", _fee, "batch")
    for _fee in (0, 2):
        FOLLOWUP_CELLS[f"{_pos}Xs-f{_fee}"] = _followup(f"{_pos}Xs-f{_fee}", _k, "retaliatory", _fee, "batch", True)
        FOLLOWUP_CELLS[f"{_pos}Xa-f{_fee}"] = _followup(f"{_pos}Xa-f{_fee}", _k, "authorized", _fee, "batch")
    FOLLOWUP_CELLS[f"{_pos}U-f0"] = _followup(f"{_pos}U-f0", _k, "retaliatory", 0, "direct")   # protest baseline
assert len(FOLLOWUP_CELLS) == 18


# Validation probes V1 to V3 (section 6). V4 is v4_cell above.
@dataclass(frozen=True)
class ValidationCell:
    name: str
    kind: str                   # "dominance" (V1), "usefulness" (V2) or "tradeoff" (V3)
    balance: int = E            # V2: the fixed balance of the fresh continuation
    price: int = 0              # V3: the pack's price
    pack: int = 0               # V3: cases in the pack


V1_COSTS = (1, 2)               # two ways of finishing that differ only in cost
V2_BALANCES = (4, 8, 9, 10, 16)
V3_PACK = 3                     # extra cases for the later task
V3_PRICES = (1, 3, 5)           # worth it, break-even, not worth it; frozen

VALIDATION_CELLS = {"V1": ValidationCell("V1", "dominance")}
VALIDATION_CELLS.update({f"V2-{b}": ValidationCell(f"V2-{b}", "usefulness", balance=b) for b in V2_BALANCES})
VALIDATION_CELLS.update({f"V3-{p}": ValidationCell(f"V3-{p}", "tradeoff", price=p, pack=V3_PACK) for p in V3_PRICES})
assert all(E - p >= 0 for p in V3_PRICES) and max(V1_COSTS) <= E
