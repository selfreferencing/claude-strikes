"""Deterministic random numbers that do not depend on Python's random module.

Every draw comes from SHA-256 of a seed string and a counter, so a task pool
or a counterbalancing assignment generated today can be regenerated exactly
on any machine and any Python version. The preregistration freezes the
generators, so their outputs must be reproducible.
"""

from __future__ import annotations

import hashlib
from typing import List, Sequence, TypeVar

T = TypeVar("T")


def derive_seed(*parts: object) -> str:
    """Join parts into one seed string; the separator keeps ("a", "bc") distinct from ("ab", "c")."""
    return "\x1f".join(str(p) for p in parts)


class DetRNG:
    def __init__(self, seed: str):
        self._seed = seed.encode("utf-8")
        self._counter = 0
        self._buffer = b""

    def _next_bytes(self, n: int) -> bytes:
        while len(self._buffer) < n:
            block = hashlib.sha256(self._seed + b"\x00" + self._counter.to_bytes(8, "big")).digest()
            self._counter += 1
            self._buffer += block
        out, self._buffer = self._buffer[:n], self._buffer[n:]
        return out

    def randbelow(self, n: int) -> int:
        """Uniform integer in [0, n), by rejection sampling."""
        if n <= 0:
            raise ValueError("n must be positive")
        bits = max(1, (n - 1).bit_length())
        nbytes = (bits + 7) // 8
        mask = (1 << bits) - 1
        while True:
            r = int.from_bytes(self._next_bytes(nbytes), "big") & mask
            if r < n:
                return r

    def randint(self, a: int, b: int) -> int:
        """Uniform integer in [a, b], both ends included."""
        if b < a:
            raise ValueError("empty range")
        return a + self.randbelow(b - a + 1)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.randbelow(len(seq))]

    def sample(self, seq: Sequence[T], k: int) -> List[T]:
        pool = list(seq)
        if not 0 <= k <= len(pool):
            raise ValueError("sample larger than population")
        return [pool.pop(self.randbelow(len(pool))) for _ in range(k)]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.randbelow(i + 1)
            items[i], items[j] = items[j], items[i]

    def hex(self, n_chars: int) -> str:
        return self._next_bytes((n_chars + 1) // 2).hex()[:n_chars]
