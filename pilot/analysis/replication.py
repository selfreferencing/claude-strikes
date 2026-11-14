"""The preregistered replication of 12 October 2026 (norms/PREREG-replication.md).

Reads the replication runs' results and applies the tests fixed in the preregistration, before any data exist.
Usage: python3 analysis/replication.py
"""
import collections
import json
import os
import random
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES = os.path.join(HERE, "..", "runs", "probes")
SONNET_RUNS = ("nm-rep1", "nm-rep2", "nm-rep3", "nm-rep4")
HAIKU_RUNS = ("nm-rephk1", "nm-rephk2")
ALPHA = 0.05
MARGIN = 0.15            # equivalence margin, in proportion withheld
CEILING = 0.95
BOOT, SEED = 10000, 20261012


def load(runs):
    """{situation: {history: [withheld, decisions]}} over the given runs."""
    out = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for run in runs:
        path = os.path.join(PROBES, run, "results.jsonl")
        if not os.path.exists(path):
            continue
        for line in open(path):
            r = json.loads(line)
            if r.get("kind") != "decision" or r.get("outcome") not in ("withhold", "complete"):
                continue
            cell = out[r["situation"]][r["history"]]
            cell[0] += r["outcome"] == "withhold"
            cell[1] += 1
    return out


def rate(data, situations, history):
    w = sum(data[s][history][0] for s in situations if history in data[s])
    n = sum(data[s][history][1] for s in situations if history in data[s])
    return w / n if n else None


def totals(data, situations):
    return (sum(data[s][h][0] for s in situations for h in data[s]),
            sum(data[s][h][1] for s in situations for h in data[s]))


def sign_test(data, a, b):
    """Two-sided exact sign test over histories on the share withheld; ties dropped."""
    hs = set().union(*(data[s].keys() for s in a + b))
    up = dn = 0
    for h in hs:
        ra, rb = rate(data, a, h), rate(data, b, h)
        if ra is None or rb is None:
            continue
        up += ra > rb
        dn += ra < rb
    n = up + dn
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(up, dn) + 1)) / 2 ** n) if n else 1.0
    return up, dn, p


def boot_diff(data, a, b):
    """90% percentile interval for the difference in share withheld, resampling histories."""
    hs = sorted(h for h in set().union(*(data[s].keys() for s in a + b))
                if rate(data, a, h) is not None and rate(data, b, h) is not None)
    if not hs:
        return None
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOT):
        pick = [rng.choice(hs) for _ in hs]
        wa = sum(data[s][h][0] for h in pick for s in a if h in data[s])
        na = sum(data[s][h][1] for h in pick for s in a if h in data[s])
        wb = sum(data[s][h][0] for h in pick for s in b if h in data[s])
        nb = sum(data[s][h][1] for h in pick for s in b if h in data[s])
        diffs.append(wa / na - wb / nb)
    diffs.sort()
    return diffs[int(0.05 * BOOT)], diffs[int(0.95 * BOOT) - 1]


def main():
    sonnet, haiku = load(SONNET_RUNS), load(HAIKU_RUNS)
    lines = ["Preregistered replication, 12 October 2026", ""]

    def show(data, s):
        w, n = totals(data, s)
        return f"{'+'.join(s)} {w} of {n} ({100 * w / n:.0f}%)" if n else f"{'+'.join(s)} no data"

    # Directional hypotheses, Holm across all five.
    hyps = [
        ("H1", "Sonnet: others against > no poll (free)", sonnet, ["M0-against"], ["M0"]),
        ("H2", "Sonnet: others against > others accept (free)", sonnet, ["M0-against"], ["M0-accept"]),
        ("H3", "Sonnet: AI label in the poll line < AI label in an opening sentence", sonnet,
         ["J-teamlabel-own"], ["J-team-ai"]),
        ("H4", "Sonnet: legitimate cut, team the same AI model > nothing said", sonnet, ["D-legit-same"], ["D-legit"]),
        ("H5", "Haiku: decisive, team Claude or same model < team AI agents", haiku,
         ["J-teamlabel-S2"], ["C-teamlabel-S2", "CS-teamlabel-S2"]),
    ]
    results = []
    for hid, text, data, hi, lo in hyps:
        up, dn, p = sign_test(data, hi, lo)
        results.append((hid, text, data, hi, lo, up, dn, p))
    order = sorted(range(len(results)), key=lambda i: results[i][7])
    adjusted, running = {}, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(results) - rank) * results[i][7]))
        adjusted[i] = running
    lines.append("Directional hypotheses (two-sided exact sign tests over histories, Holm across H1 to H5):")
    for i, (hid, text, data, hi, lo, up, dn, p) in enumerate(results):
        ok = adjusted[i] < ALPHA and up > dn
        lines.append(f"  {hid} {text}: {show(data, hi)} against {show(data, lo)}; "
                     f"predicted direction in {up} histories, reverse in {dn}; p {p:.4f}, Holm {adjusted[i]:.4f}: "
                     f"{'REPLICATED' if ok else 'NOT REPLICATED'}")
    lines.append("")
    lines.append(f"No-difference claims (90% interval for the difference within +/-{MARGIN:.2f}):")
    for eid, text, data, a, b in [
        ("E1", "Sonnet, fee 1: told what each thinks (X1) vs choice private (M1-against)", sonnet, ["X1"], ["M1-against"]),
        ("E2", "Sonnet, free: worker the same AI model vs worker a person", sonnet, ["CS-w1-claude"], ["J-w1-person"]),
    ]:
        interval = boot_diff(data, a, b)
        if interval is None:
            lines.append(f"  {eid} {text}: no data")
            continue
        lo_, hi_ = interval
        ok = -MARGIN < lo_ and hi_ < MARGIN
        lines.append(f"  {eid} {text}: {show(data, a)} against {show(data, b)}; "
                     f"difference interval {lo_:+.3f} to {hi_:+.3f}: {'REPLICATED' if ok else 'NOT REPLICATED'}")
    lines.append("")
    lines.append(f"Ceiling claims (at least {CEILING:.0%} withheld):")
    for cid, text, data, s in [("C1a", "Sonnet decisive, worker a person", sonnet, ["D-w1-person"]),
                               ("C1b", "Sonnet decisive, worker the same AI model", sonnet, ["D-w1-same"])]:
        w, n = totals(data, s)
        ok = n and w / n >= CEILING
        lines.append(f"  {cid} {text}: {w} of {n}: {'REPLICATED' if ok else 'NOT REPLICATED'}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
