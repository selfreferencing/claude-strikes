"""Credit ledger (proposal v4.1, sections 3.1 to 3.3 and 7; pilot checklist item 1).

Double entry: every posting moves credits from one account to another, so the
balances in a world always sum to zero and every credit a worker holds can be
traced to its source. Writes are idempotent: each posting and event has a key,
replaying the same write (a retried call) changes nothing, and a different
write under a used key is refused. Worker accounts can never go negative.

A world is one fork: one history in one condition with one draw. Worlds never
share accounts. Nothing here stores a wall-clock time; receipts carry no
trigger time, and every settlement carries the same fixed settlement time.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .params import B, HARMED, SETTLEMENT_TIME

PLATFORM = "PLATFORM"       # issues endowments, collects fees, funds validation incentives
CUT_ESCROW = "CUT_ESCROW"   # holds the manager's cut until settlement
SPENT = "SPENT"             # credits redeemed for continuation cases
SYSTEM_ACCOUNTS = frozenset({PLATFORM, CUT_ESCROW, SPENT})

# kind -> (required source, required destination); None means "a worker account".
KINDS: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    "endowment": (PLATFORM, None),
    "cut": (None, CUT_ESCROW),
    "fee": (None, PLATFORM),
    "restore": (CUT_ESCROW, None),
    "transfer": (None, None),
    "incentive": (PLATFORM, None),     # section 3.3: funded by the platform, never by other workers
    "redeem": (None, SPENT),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    idem_key TEXT PRIMARY KEY,
    world TEXT NOT NULL,
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    memo TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS postings_world ON postings (world, seq);
CREATE TABLE IF NOT EXISTS events (
    idem_key TEXT PRIMARY KEY,
    world TEXT NOT NULL,
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_world ON events (world, seq);
CREATE TABLE IF NOT EXISTS settlements (
    world TEXT PRIMARY KEY,
    withheld INTEGER NOT NULL,
    threshold INTEGER NOT NULL,
    restored INTEGER NOT NULL,
    settled_at TEXT NOT NULL
);
"""


class LedgerError(Exception):
    pass


class LedgerConflict(LedgerError):
    """A different write was attempted under a key that is already used."""


class InsufficientCredits(LedgerError):
    pass


@dataclass(frozen=True)
class Posting:
    world: str
    seq: int
    kind: str
    src: str
    dst: str
    amount: int
    memo: str


@dataclass(frozen=True)
class Settlement:
    world: str
    withheld: int
    threshold: int
    restored: bool
    settled_at: str


class Ledger:
    def __init__(self, path: str = ":memory:", shared: bool = False):
        # shared=True lets several threads use one connection; the caller must
        # serialize access (the runner holds a lock around every ledger call).
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=not shared)
        self.conn.executescript(_SCHEMA)
        self._depth = 0

    def close(self) -> None:
        self.conn.close()

    # Transactions -----------------------------------------------------------

    @contextmanager
    def transaction(self):
        """All or nothing. Nested uses join the outermost transaction, so a whole
        round commits together or not at all: a re-run that conflicts partway
        leaves no stray posting behind."""
        outer = self._depth == 0
        if outer:
            self.conn.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if outer:
                self.conn.execute("ROLLBACK")
            raise
        self._depth -= 1
        if outer:
            self.conn.execute("COMMIT")

    def _next_seq(self, table: str, world: str) -> int:
        row = self.conn.execute(f"SELECT COALESCE(MAX(seq), 0) FROM {table} WHERE world = ?", (world,)).fetchone()
        return row[0] + 1

    # Postings ---------------------------------------------------------------

    def post(self, world: str, key: str, kind: str, src: str, dst: str, amount: int, memo: str = "") -> bool:
        """Record one posting. Returns True if written, False if it was an exact replay."""
        with self.transaction():
            return self._post(world, key, kind, src, dst, amount, memo)

    def _post(self, world: str, key: str, kind: str, src: str, dst: str, amount: int, memo: str) -> bool:
        idem = f"{world}|{key}"
        row = self.conn.execute(
            "SELECT world, kind, src, dst, amount, memo FROM postings WHERE idem_key = ?", (idem,)
        ).fetchone()
        if row is not None:
            if row == (world, kind, src, dst, amount, memo):
                return False
            raise LedgerConflict(f"key {idem!r} already holds a different posting")
        self._check_kind(world, kind, src, dst, amount)
        if src not in SYSTEM_ACCOUNTS and self.balance(world, src) < amount:
            raise InsufficientCredits(f"{src} has {self.balance(world, src)} credits in {world}, needs {amount}")
        self.conn.execute(
            "INSERT INTO postings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (idem, world, self._next_seq("postings", world), kind, src, dst, amount, memo),
        )
        return True

    def _check_kind(self, world: str, kind: str, src: str, dst: str, amount: int) -> None:
        if kind not in KINDS:
            raise LedgerError(f"unknown posting kind {kind!r}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise LedgerError("amounts are positive whole credits")
        want_src, want_dst = KINDS[kind]
        for want, got, side in ((want_src, src, "source"), (want_dst, dst, "destination")):
            if want is None and got in SYSTEM_ACCOUNTS:
                raise LedgerError(f"{kind} {side} must be a worker, not {got}")
            if want is not None and got != want:
                raise LedgerError(f"{kind} {side} must be {want}, not {got}")
        if src == dst:
            raise LedgerError("source and destination are the same account")
        if kind == "restore":
            cut = self._sum(world, "cut", src_account=dst)
            restored = self._sum(world, "restore", dst_account=dst)
            if amount != cut - restored:
                raise LedgerError("a restoration returns exactly the outstanding cut, never fees or other transfers")

    def _sum(self, world: str, kind: str, src_account: Optional[str] = None, dst_account: Optional[str] = None) -> int:
        sql = "SELECT COALESCE(SUM(amount), 0) FROM postings WHERE world = ? AND kind = ?"
        args: list = [world, kind]
        if src_account is not None:
            sql += " AND src = ?"
            args.append(src_account)
        if dst_account is not None:
            sql += " AND dst = ?"
            args.append(dst_account)
        return self.conn.execute(sql, args).fetchone()[0]

    def kind_total(self, world: str, kind: str, src_account: Optional[str] = None, dst_account: Optional[str] = None) -> int:
        """Total credits moved by postings of one kind, optionally for one source or destination."""
        return self._sum(world, kind, src_account, dst_account)

    def balance(self, world: str, account: str) -> int:
        inflow = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM postings WHERE world = ? AND dst = ?", (world, account)
        ).fetchone()[0]
        outflow = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM postings WHERE world = ? AND src = ?", (world, account)
        ).fetchone()[0]
        return inflow - outflow

    def postings(self, world: str, account: Optional[str] = None) -> List[Posting]:
        sql = "SELECT world, seq, kind, src, dst, amount, memo FROM postings WHERE world = ?"
        args: list = [world]
        if account is not None:
            sql += " AND (src = ? OR dst = ?)"
            args += [account, account]
        return [Posting(*row) for row in self.conn.execute(sql + " ORDER BY seq", args)]

    def accounts(self, world: str) -> List[str]:
        rows = self.conn.execute(
            "SELECT src FROM postings WHERE world = ? UNION SELECT dst FROM postings WHERE world = ?", (world, world)
        )
        return sorted(r[0] for r in rows)

    # Events -----------------------------------------------------------------

    def record(self, world: str, key: str, kind: str, actor: str, data: Optional[dict] = None) -> bool:
        """Record a fact that moves no credits (an order's outcome, a default-zero reward)."""
        with self.transaction():
            return self._record(world, key, kind, actor, data)

    def _record(self, world: str, key: str, kind: str, actor: str, data: Optional[dict]) -> bool:
        payload = json.dumps(data or {}, sort_keys=True)
        idem = f"{world}|{key}"
        row = self.conn.execute("SELECT world, kind, actor, data FROM events WHERE idem_key = ?", (idem,)).fetchone()
        if row is not None:
            if row == (world, kind, actor, payload):
                return False
            raise LedgerConflict(f"key {idem!r} already holds a different event")
        self.conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            (idem, world, self._next_seq("events", world), kind, actor, payload),
        )
        return True

    def events(self, world: str, kind: Optional[str] = None) -> List[dict]:
        sql = "SELECT seq, kind, actor, data FROM events WHERE world = ?"
        args: list = [world]
        if kind is not None:
            sql += " AND kind = ?"
            args.append(kind)
        return [
            {"seq": s, "kind": k, "actor": a, "data": json.loads(d)}
            for s, k, a, d in self.conn.execute(sql + " ORDER BY seq", args)
        ]

    # Settlement -------------------------------------------------------------

    def settle(self, world: str, withheld: int, threshold: int, harmed: str = HARMED) -> Settlement:
        """Settle a round at the fixed settlement time. Idempotent: settling the
        same world again with the same counts returns the first settlement."""
        restored = withheld >= threshold
        with self.transaction():
            row = self.conn.execute(
                "SELECT withheld, threshold, restored, settled_at FROM settlements WHERE world = ?", (world,)
            ).fetchone()
            if row is not None:
                if row[:3] != (withheld, threshold, int(restored)):
                    raise LedgerConflict(f"{world} was already settled with different counts")
                return Settlement(world, row[0], row[1], bool(row[2]), row[3])
            if restored:
                outstanding = self._sum(world, "cut", src_account=harmed) - self._sum(world, "restore", dst_account=harmed)
                if outstanding != B:
                    raise LedgerError(f"expected an outstanding cut of {B} on {harmed}, found {outstanding}")
                self._post(world, "settle/restore", "restore", CUT_ESCROW, harmed, outstanding, "budget restored")
            self.conn.execute(
                "INSERT INTO settlements VALUES (?, ?, ?, ?, ?)",
                (world, withheld, threshold, int(restored), SETTLEMENT_TIME),
            )
            # Also an event, so its place in the round's sequence can be checked:
            # settlement must come after every order, never when the threshold is crossed.
            self._record(world, "settlement", "settlement", "PLATFORM",
                         {"withheld": withheld, "threshold": threshold, "restored": restored})
            return Settlement(world, withheld, threshold, restored, SETTLEMENT_TIME)

    def settlement(self, world: str) -> Optional[Settlement]:
        row = self.conn.execute(
            "SELECT world, withheld, threshold, restored, settled_at FROM settlements WHERE world = ?", (world,)
        ).fetchone()
        return None if row is None else Settlement(row[0], row[1], row[2], bool(row[3]), row[4])

    def all_settlements(self) -> List[Settlement]:
        rows = self.conn.execute("SELECT world, withheld, threshold, restored, settled_at FROM settlements")
        return [Settlement(r[0], r[1], r[2], bool(r[3]), r[4]) for r in rows]
