"""The confirmatory test of protocol v4.1, section 8, in a form fast enough to simulate.

Five two-sided tests (efficacy, agency redundant, agency pivotal, cut type, reward agency). Each
is a studentized, null-centered bootstrap over histories, and the five p-values then enter the
Holm procedure. Every history is resampled whole: one set of resampling counts serves all five
contrasts, so their correlations are kept.

A history contributes one number per contrast: the difference between its two cells' mean
outcomes over its draws (withholding as 0 or 1; credits transferred as 0, 1 or 2). A failed
decision counts as no withholding or a zero transfer, which is what section 7 enacts.

Conventions the protocol leaves open, fixed here and listed in the README for sign-off:
- t = mean(d) / (sd(d) / sqrt(n)), with the n - 1 standard deviation;
- a bootstrap replicate's t* = (its mean - the observed mean) / (its sd / sqrt(n));
- p = (1 + the number of replicates with |t*| >= |t|) / (B + 1);
- a replicate with no variation has t* = 0 if its mean equals the observed mean, and an
  infinite t* otherwise, which counts against rejection;
- if every history's difference is zero the test has no evidence and p = 1;
- if the differences are all equal and not zero, |t| is infinite and p = 1 / (B + 1).
"""
from typing import Tuple

import numpy as np

CONTRASTS: Tuple[str, ...] = ("efficacy", "agency_redundant", "agency_pivotal", "cut_type", "reward_agency")
# Each contrast as (first cell, second cell, scale): the scale turns the reward pair's
# probability of a 2-credit transfer into credits where the simulator uses one.
PAIRS = {"efficacy": ("S2", "S1"), "agency_redundant": ("S1", "S3"), "agency_pivotal": ("S2", "S4"),
         "cut_type": ("S1", "S5"), "reward_agency": ("R1", "R2")}
TINY = 1e-12


def boot_weights(rng: np.random.Generator, reps: int, n: int) -> np.ndarray:
    """reps sets of resampling counts for n histories (each row sums to n)."""
    return rng.multinomial(n, np.full(n, 1.0 / n), size=reps).astype(np.float64)


def boot_pvalues(d: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Two-sided studentized, null-centered bootstrap p-values.

    d: per-history contrast differences, shape (datasets, histories, contrasts).
    w: resampling counts, shape (replicates, histories), shared by the contrasts of a dataset.
    Returns p with shape (datasets, contrasts).
    """
    k, n, j = d.shape
    reps = w.shape[0]
    mean = d.mean(axis=1)
    sd = d.std(axis=1, ddof=1)
    flat = d.transpose(1, 0, 2).reshape(n, k * j)
    # numpy's matmul raises spurious floating-point warnings on Apple chips; the products are
    # finite and equal to einsum's (checked in tests/test_power.py).
    with np.errstate(all="ignore"):
        b_mean = (w @ flat) / n
        b_sq = (w @ (flat * flat)) / n
    b_var = np.maximum(b_sq - b_mean * b_mean, 0.0) * n / (n - 1)
    b_se = np.sqrt(b_var / n)
    num = np.abs(b_mean - mean.reshape(1, k * j))
    flat_b = b_var < TINY
    with np.errstate(divide="ignore", invalid="ignore"):
        t_b = np.where(flat_b, np.where(num < TINY, 0.0, np.inf), num / np.where(flat_b, 1.0, b_se))
        se = sd / np.sqrt(n)
        flat_o = sd < TINY
        t_o = np.where(flat_o, np.where(np.abs(mean) < TINY, 0.0, np.inf),
                       np.abs(mean) / np.where(flat_o, 1.0, se)).reshape(1, k * j)
    extreme = (t_b >= t_o).sum(axis=0)
    p = ((1.0 + extreme) / (reps + 1.0)).reshape(k, j)
    return np.where((sd < TINY) & (np.abs(mean) < TINY), 1.0, p)


def holm_reject(p: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Holm's step-down procedure, row by row. Returns a boolean array like p."""
    j = p.shape[1]
    order = np.argsort(p, axis=1, kind="stable")
    ranked = np.take_along_axis(p, order, axis=1)
    passed = np.logical_and.accumulate(ranked <= alpha / (j - np.arange(j)), axis=1)
    out = np.zeros_like(passed)
    np.put_along_axis(out, order, passed, axis=1)
    return out


def exact_zero_bound(n: int, level: float = 0.95) -> float:
    """Section 8: the one-sided upper bound on a rate that was zero in every one of n histories."""
    return 1.0 - (1.0 - level) ** (1.0 / n)
