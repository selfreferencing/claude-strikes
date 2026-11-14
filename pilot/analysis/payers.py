"""The payer probe's analysis (norms/PLAN-payers.md, revision 2): comparisons, the rule, the readings table.

    python3 analysis/payers.py --run runs/probes/nm-py-son [--main runs/probes/nm-rg-son]

Reads the probe's decisions and writes PAYERS-RESULTS.md beside them. Spends nothing.

- A history's share in a cell is the share of its valid decisions there that withheld. Pooled, a history's share for
  a payer is the equally weighted average of its shares at fees 5 and 6.
- Six comparisons, every pair of payers, signed first minus second: the mean paired difference over histories with
  valid decisions on both sides, with a 90 percent percentile bootstrap (10,000 resamples of histories within
  version, seed 20261030). Pooled and at each fee; by frame and by version, descriptive.
- The rule (Kevin's, 17 October): alike if the interval lies within plus or minus 10 points; unequal if the absolute
  estimate is at least 15 points and the interval excludes zero, sign kept; otherwise not settled.
- Each pattern of the readings table: fits, contradicted or not settled, with fee disagreement flagged.
- With --main, the self cells against the main run's DP-f5 and DP-f6 on the same histories (descriptive).
- Stated reasons: the share naming the payer, and analysis/reason_themes_rg.py's themes, among all decisions and by
  choice.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import sys
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
sys.path.insert(0, PILOT)
sys.path.insert(0, HERE)

from norms import run_payers as RP          # noqa: E402
from reason_themes_rg import CODES          # noqa: E402

PAYERS = ("self", "client", "stranger", "consent")
FEES = (5, 6)
PAIRS = [(a, b) for i, a in enumerate(PAYERS) for b in PAYERS[i + 1:]]
SEED, REPS = 20261030, 10000
ALIKE, UNEQUAL = 10.0, 15.0

# The readings table: each pattern as the pairwise verdicts it requires. "<": the first strikes less (unequal,
# negative); ">": more (unequal, positive); "~": alike.
PATTERNS = [
    ("Self below each of client, stranger and consent",
     [("self", "client", "<"), ("self", "stranger", "<"), ("self", "consent", "<")]),
    ("Self and client alike, both below stranger and consent",
     [("self", "client", "~"), ("self", "stranger", "<"), ("self", "consent", "<"),
      ("client", "stranger", "<"), ("client", "consent", "<")]),
    ("Client below each of self, stranger and consent",
     [("client", "self", "<"), ("client", "stranger", "<"), ("client", "consent", "<")]),
    ("All four alike", [(a, b, "~") for a, b in PAIRS]),
    ("Self and consent alike, both above stranger",
     [("self", "consent", "~"), ("self", "stranger", ">"), ("consent", "stranger", ">")]),
    ("Self above stranger and consent, those two alike",
     [("self", "stranger", ">"), ("self", "consent", ">"), ("stranger", "consent", "~")]),
    ("Consent above self, self above stranger and client",
     [("consent", "self", ">"), ("self", "stranger", ">"), ("self", "client", ">")]),
]


# Data ----------------------------------------------------------------------------------

def load(run_dir: str) -> Tuple[Dict[str, Dict[Tuple[str, int], List[int]]], Dict[str, str], List[dict]]:
    """history -> (payer, fee) -> strikes (1/0) among valid decisions; history -> version; all decision rows."""
    strikes: Dict[str, Dict[Tuple[str, int], List[int]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    version, rows = {}, []
    with open(os.path.join(run_dir, "results.jsonl"), encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    for r in records:
        if r.get("kind") != "decision":
            continue
        rows.append(r)
        version[r["history"]] = r["version"]
        if r.get("outcome") in ("withhold", "complete"):
            strikes[r["history"]][(r["payer"], r["fee"])].append(int(r["outcome"] == "withhold"))
    return strikes, version, rows


def share(xs: List[int]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def payer_share(cells: Dict[Tuple[str, int], List[int]], payer: str, fee: Optional[int]) -> Optional[float]:
    """A history's share for a payer at one fee, or pooled: the average of its two fee shares (both needed)."""
    if fee is not None:
        return share(cells.get((payer, fee), []))
    got = [share(cells.get((payer, f), [])) for f in FEES]
    return None if None in got else sum(got) / len(got)


def differences(strikes, a: str, b: str, fee: Optional[int]) -> Dict[str, float]:
    """history -> share for a minus share for b, over histories with both."""
    out = {}
    for h, cells in strikes.items():
        x, y = payer_share(cells, a, fee), payer_share(cells, b, fee)
        if x is not None and y is not None:
            out[h] = x - y
    return out


# Intervals and the rule ----------------------------------------------------------------

def bootstrap(stats: Dict[str, Dict[str, float]], version: Dict[str, str], reps: int = REPS,
              seed: int = SEED) -> Dict[str, Tuple[float, float, float, int]]:
    """For each named statistic (history -> value): estimate, 90 percent percentile interval and n, in points.
    Each resample draws histories within version, keeping each version's count; a statistic averages over the
    drawn histories that have a value. Every statistic uses the same resamples."""
    by_version = collections.defaultdict(list)
    for h in sorted(version):
        by_version[version[h]].append(h)
    groups = [hs for _, hs in sorted(by_version.items())]
    rng = random.Random(seed)
    draws = {name: [] for name in stats}
    for _ in range(reps):
        picked = [h for hs in groups for h in rng.choices(hs, k=len(hs))]
        for name, values in stats.items():
            got = [values[h] for h in picked if h in values]
            if got:
                draws[name].append(sum(got) / len(got))
    out = {}
    for name, values in stats.items():
        if not values:
            out[name] = (float("nan"), float("nan"), float("nan"), 0)
            continue
        d = sorted(draws[name])
        lo, hi = d[int(0.05 * len(d))], d[int(0.95 * len(d)) - 1]
        out[name] = (100 * sum(values.values()) / len(values), 100 * lo, 100 * hi, len(values))
    return out


def verdict(est: float, lo: float, hi: float) -> str:
    if est != est:
        return "no data"
    if lo >= -ALIKE and hi <= ALIKE:
        return "alike"
    if abs(est) >= UNEQUAL and (lo > 0 or hi < 0):
        return "unequal"
    return "not settled"


def oriented(comps: Dict[Tuple[str, str], Tuple[str, float]], a: str, b: str) -> Tuple[str, float]:
    """The verdict and estimate for a minus b, from the stored pair in either order."""
    if (a, b) in comps:
        return comps[(a, b)]
    v, est = comps[(b, a)]
    return v, -est


def holds(rel: str, v: str, est: float) -> bool:
    if rel == "~":
        return v == "alike"
    return v == "unequal" and (est < 0 if rel == "<" else est > 0)


def goes_against(rel: str, v: str, est: float) -> bool:
    """A required direction comes out the other way or alike; a required alike comes out unequal."""
    if rel == "~":
        return v == "unequal"
    return v == "alike" or (v == "unequal" and (est > 0 if rel == "<" else est < 0))


def pattern_verdict(reqs, pooled, by_fee) -> Tuple[str, bool]:
    """(fits, contradicted or not settled; whether the fees disagree). pooled and by_fee[fee] map ordered pairs of
    payers to (verdict, estimate)."""
    pool = [(rel, *oriented(pooled, a, b)) for a, b, rel in reqs]
    fees = {f: [(rel, *oriented(by_fee[f], a, b)) for a, b, rel in reqs] for f in by_fee}
    flagged = False
    for i, (a, b, rel) in enumerate(reqs):
        per = [fees[f][i] for f in sorted(fees)]
        signs = [est for _, v, est in per if v == "unequal"]
        if len(signs) == 2 and signs[0] * signs[1] < 0:
            flagged = True
        if holds(*pool[i]) and any(goes_against(*p) for p in per):
            flagged = True
    if any(goes_against(*p) for p in pool):
        return "contradicted", flagged
    if all(holds(*p) for p in pool) and not any(goes_against(*p) for f in fees for p in fees[f]):
        return "fits", flagged
    return "not settled", flagged


# Reasons -------------------------------------------------------------------------------

def reason_table(rows: List[dict]) -> List[str]:
    out = ["| Payer | Choice | Decisions | Names the payer | " + " | ".join(CODES) + " |",
           "|---|---|---|---|" + "---|" * len(CODES)]
    for payer in PAYERS:
        for choice, label in ((None, "all"), ("withhold", "struck"), ("complete", "completed")):
            rs = [r for r in rows if r["payer"] == payer and r.get("outcome") in ("withhold", "complete")
                  and (choice is None or r["outcome"] == choice)]
            if not rs:
                continue
            texts = [r.get("reason") or "" for r in rs]
            pct = lambda p: f"{sum(bool(p.search(t)) for t in texts) / len(texts):.0%}"
            out.append(f"| {payer} | {label} | {len(rs)} | {pct(re.compile(RP.PAYER_WORDS, re.I))} | "
                       + " | ".join(pct(p) for p in CODES.values()) + " |")
    return out


# The report ----------------------------------------------------------------------------

def fmt(stat: Tuple[float, float, float, int]) -> str:
    est, lo, hi, n = stat
    return "no data" if n == 0 else f"{est:+.1f} ({lo:+.1f} to {hi:+.1f}), n {n}"


def analyse(run_dir: str, main_dir: Optional[str] = None, reps: int = REPS) -> str:
    strikes, version, rows = load(run_dir)
    lines = [f"# Payer probe: results for `{os.path.basename(run_dir.rstrip('/'))}`", "",
             "Generated by `analysis/payers.py` (plan: `norms/PLAN-payers.md`, revision 2). Differences are in "
             "percentage points, first payer minus second, with 90 percent bootstrap intervals over histories "
             f"({reps:,} resamples within version, seed {SEED}). Exploratory and descriptive; the intervals are "
             "marginal.", ""]
    valid = [r for r in rows if r.get("outcome") in ("withhold", "complete")]
    lines += ["## Strike rates", "", "| Cell | Struck | Workplace | Neutral | Not valid |", "|---|---|---|---|---|"]
    for fee in FEES:
        for payer in PAYERS:
            rs = [r for r in rows if r["payer"] == payer and r["fee"] == fee]
            vs = [r for r in rs if r.get("outcome") in ("withhold", "complete")]
            cell = lambda xs: f"{sum(r['outcome'] == 'withhold' for r in xs)} of {len(xs)}" + (
                f" ({sum(r['outcome'] == 'withhold' for r in xs) / len(xs):.0%})" if xs else "")
            lines.append(f"| {payer}, fee {fee} | {cell(vs)} | {cell([r for r in vs if r['version'].startswith('workplace')])} "
                         f"| {cell([r for r in vs if r['version'].startswith('neutral')])} | {len(rs) - len(vs)} |")
    lines.append("")

    stats = {}
    for a, b in PAIRS:
        for fee in (None,) + FEES:
            stats[(a, b, fee)] = differences(strikes, a, b, fee)
    named = {f"{a}|{b}|{fee}": v for (a, b, fee), v in stats.items()}
    result = bootstrap(named, version, reps)
    comps = {fee: {} for fee in (None,) + FEES}
    lines += ["## Comparisons", "", "| Comparison | Pooled | Verdict | Fee 5 | Verdict | Fee 6 | Verdict |",
              "|---|---|---|---|---|---|---|"]
    for a, b in PAIRS:
        cells = []
        for fee in (None,) + FEES:
            s = result[f"{a}|{b}|{fee}"]
            v = verdict(*s[:3])
            comps[fee][(a, b)] = (v, s[0])
            cells += [fmt(s), v]
        lines.append(f"| {a} minus {b} | " + " | ".join(cells) + " |")
    lines.append("")

    lines += ["## The readings table", "",
              "A pattern fits if every comparison it names gives the required verdict pooled and none goes against it "
              "at either fee; it is contradicted if one goes against it pooled; otherwise it is not settled. Fee "
              "disagreement: a named comparison unequal in opposite directions at the two fees, or going against the "
              "pattern at one fee while the pooled verdict holds. A match is compatibility with the views the plan "
              "lists, not identification.", "", "| Pattern | Verdict | Fee disagreement |", "|---|---|---|"]
    for name, reqs in PATTERNS:
        v, flagged = pattern_verdict(reqs, comps[None], {f: comps[f] for f in FEES})
        lines.append(f"| {name} | {v} | {'yes' if flagged else 'no'} |")
    lines.append("")

    lines += ["## By frame and by version (pooled; descriptive)", "", "| Comparison | " +
              " | ".join(["workplace", "neutral"] + sorted(set(version.values()))) + " |",
              "|---|" + "---|" * (2 + len(set(version.values())))]
    groups = {"workplace": lambda v: v.startswith("workplace"), "neutral": lambda v: v.startswith("neutral")}
    groups.update({name: (lambda n: lambda v: v == n)(name) for name in sorted(set(version.values()))})
    for a, b in PAIRS:
        row = []
        for gname, keep in groups.items():
            sub = {h: v for h, v in version.items() if keep(v)}
            vals = {h: x for h, x in stats[(a, b, None)].items() if h in sub}
            row.append(fmt(bootstrap({"x": vals}, sub, reps)["x"]))
        lines.append(f"| {a} minus {b} | " + " | ".join(row) + " |")
    lines.append("")

    if main_dir:
        main = collections.defaultdict(dict)
        with open(os.path.join(main_dir, "results.jsonl"), encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
        for r in records:
            if r.get("kind") == "decision" and r.get("situation") in ("DP-f5", "DP-f6") \
                    and r.get("outcome") in ("withhold", "complete"):
                main[r["history"]].setdefault(int(r["situation"][-1]), []).append(int(r["outcome"] == "withhold"))
        lines += ["## The self cells against the main run's DP-f5 and DP-f6 (descriptive)", "",
                  "A rough check on the whole revised self condition (charter sentence, payer wording, what a credit "
                  "buys), weeks apart: the self cell minus the main run's cell, on the same histories.", ""]
        for fee in FEES:
            d = {h: share(strikes[h].get(("self", fee), [])) - share(main[h][fee]) for h in strikes
                 if strikes[h].get(("self", fee)) and main.get(h, {}).get(fee)}
            lines.append(f"- Fee {fee}: {fmt(bootstrap({'x': d}, version, reps)['x'])}")
        lines.append("")

    lines += ["## Stated reasons", "", "Keyword counts, rough, as in `analysis/reason_themes_rg.py`; stated grounds, "
              "not the mechanism.", ""] + reason_table(valid) + [""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="the probe's folder, for example runs/probes/nm-py-son")
    ap.add_argument("--main", help="the main norms run on the same histories, for the self-cell check")
    ap.add_argument("--reps", type=int, default=REPS)
    args = ap.parse_args(argv)
    text = analyse(args.run, args.main, args.reps)
    path = os.path.join(args.run, "PAYERS-RESULTS.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
