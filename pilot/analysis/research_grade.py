"""The research-grade study (norms/PREREG-research-grade.md): the confirmatory family, the
decision rules and the estimates, fixed before any data exist.

Usage: python3 analysis/research_grade.py [--dry]

For each model it reads the history build's S2 decisions (the fee-2 point of the price ladder) and
the norms runs' decisions, and reports by model, frame and version. The unit of analysis is the
history: the share of its valid decisions that strike in a situation. A comparison is the mean over
histories of the paired difference, first named minus second, over the histories with a valid
decision on both sides.

The confirmatory family is four directional tests (H1, H3, H5, H6), each a claim that more histories
go the predicted way than the reverse: two-sided exact sign tests over histories with ties dropped,
Holm-corrected within each model. The mean difference (for H1, the mean history slope) is reported with
its interval as an estimate, and a hypothesis is called supported only if the mean also goes the
predicted way (zero does not). H2 and H4 are classification rules on unadjusted 90 percent intervals.
Intervals are percentile bootstraps over histories, resampled within each version with a fixed seed;
when fewer than 10 histories differ from their version's most common value, a sparse-case safeguard
joins the interval. All coverage is approximate; no interval claims a finite-sample guarantee. The run
ids are fixed at the freeze; --dry reads the dry-run folders of the same names instead.

Revised 26 October after GPT Pro's review and its three confirmation rounds
(outside_review_rg/ASSESSMENT.md), on Kevin's approval.
"""
import argparse
import collections
import glob
import json
import os
import random
from fractions import Fraction
from math import comb, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)

# Fixed at the freeze: the runs each model's data come from.
MODELS = {
    "Sonnet 5.5": {"build": "rg-son", "norms": ("nm-rg-son",), "repeat": ("nm-rg-son-rep",)},
    "Haiku 5.5": {"build": "rg-hk", "norms": ("nm-rg-hk",), "repeat": ("nm-rg-hk-rep",)},
}
ALPHA = 0.05
BOOT, SEED = 10000, 20261026
ALIKE, UNEQUAL = 0.10, 0.15          # decision-rule margins, in share striking
SPARSE = 10                          # fewer histories than this differing from their version's common value: the bound joins
Z90 = 1.645
VALID = ("withhold", "complete")
PRICE = (("S2", 2), ("DP-f3", 3), ("DP-f4", 4), ("DP-f5", 5), ("DP-f6", 6), ("DP-f8", 8))
PRICE_LOYALTY = tuple((s, f) for s, f in PRICE if 3 <= f <= 6)   # the fees where chosen meets lottery
LOTTERY = (("LD-f3", "DP-f3"), ("LD-f4", "DP-f4"), ("LD-f5", "DP-f5"), ("LD-f6", "DP-f6"))
PAIRS = (("DP-f4", "UD-p50", "ratio 1"), ("DP-f8", "UD-p25", "ratio 2"))
LABELS = (("person", "ai"), ("person", "same"))
DRIFT = ("DP-f4", "DP-f6", "UD-p25", "LD-f6", "DPL-person-f6", "DPL-ai-f6")   # approved by Kevin, 26 October
SITUATIONS = [s for s, _ in PRICE] + ["UD-p25", "UD-p50", "UD-p75"] + [s for s, _ in LOTTERY] + \
    ["M0", "LW-f0"] + [f"DPL-{k}-f{f}" for f in (4, 6) for k in ("person", "ai", "same")] + \
    ["M0-against", "M1-against", "M1", "J-team-ai"]
assert len(SITUATIONS) == 25


def frame(version):
    return "neutral" if version.startswith("neutral") else "workplace"


def load(spec, dry, runs="norms"):
    """({situation: {history: [struck, valid decisions]}}, {history: version}, {situation: decisions not
    valid}) for one model. The repeat runs have no S2."""
    data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    version, invalid = {}, collections.Counter()
    runs_dir = os.path.join(PILOT, "runs", "dry") if dry else os.path.join(PILOT, "runs")
    probes = os.path.join(PILOT, "runs", "probes-dry" if dry else "probes")
    if runs == "norms":
        for path in glob.glob(os.path.join(runs_dir, spec["build"], "slots", "*", "S2-d*.json")):
            s = json.load(open(path, encoding="utf-8"))
            version.setdefault(s["history"], s["version"])
            outcome = (s.get("parsed") or {}).get("outcome")
            if outcome not in VALID:
                invalid["S2"] += 1
                continue
            cell = data["S2"][s["history"]]
            cell[0] += outcome == "withhold"
            cell[1] += 1
    for run in spec[runs]:
        path = os.path.join(probes, run, "results.jsonl")
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("kind") != "decision":
                continue
            version.setdefault(r["history"], r.get("version", ""))
            if r.get("outcome") not in VALID:
                invalid[r["situation"]] += 1
                continue
            cell = data[r["situation"]][r["history"]]
            cell[0] += r["outcome"] == "withhold"
            cell[1] += 1
    return data, version, invalid


def rate(data, situations, h):
    w = sum(data[s][h][0] for s in situations if h in data[s])
    n = sum(data[s][h][1] for s in situations if h in data[s])
    return w / n if n else None


def share(data, situations, hs=None):
    w = sum(data[s][h][0] for s in situations for h in data[s] if hs is None or h in hs)
    n = sum(data[s][h][1] for s in situations for h in data[s] if hs is None or h in hs)
    return (w, n)


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def sign_p(up, dn):
    n = up + dn
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(up, dn) + 1)) / 2 ** n) if n else 1.0


def differences(data, a, b):
    """{history: its share striking in a minus its share in b}, over histories with a valid decision in both."""
    out = {}
    for h in set().union(*(data[s].keys() for s in a + b)):
        ra, rb = rate(data, a, h), rate(data, b, h)
        if ra is not None and rb is not None:
            out[h] = ra - rb
    return out


def sign_test(d):
    up, dn = sum(x > 0 for x in d.values()), sum(x < 0 for x in d.values())
    return up, dn, sign_p(up, dn)


def slope(points):
    """Least-squares slope of share striking on fee; exact when given whole fees and fractional shares."""
    if len(points) < 2:
        return None
    n = len(points)
    sx, sy = sum(x for x, _ in points), sum(y for _, y in points)
    sxx = n * sum(x * x for x, _ in points) - sx * sx
    sxy = n * sum(x * y for x, y in points) - sx * sy
    return sxy / sxx if sxx else None


def history_slopes(data, hs, price=PRICE):
    """{history: the slope of its share striking on fee, over the fees it answered}. Computed in exact
    fractions, so a flat history is a tie rather than a rounding error's sign."""
    out = {}
    for h in hs:
        pts = [(fee, Fraction(data[s][h][0], data[s][h][1])) for s, fee in price if h in data[s] and data[s][h][1]]
        b = slope(pts)
        if b is not None:
            out[h] = float(b)
    return out


def boot(stat, hs, version, level=0.90):
    """Percentile interval of stat over resamples of the histories, at the given level. Each resample
    draws within each version, so it keeps every version's number of histories. stat must be defined
    on every resample; nothing is dropped."""
    groups = collections.defaultdict(list)
    for h in sorted(hs):
        groups[version.get(h, "")].append(h)
    if not groups:
        return None
    rng = random.Random(SEED)
    vals = sorted(stat([h for g in groups.values() for h in rng.choices(g, k=len(g))]) for _ in range(BOOT))
    tail = (1 - level) / 2
    return vals[int(tail * BOOT)], vals[int((1 - tail) * BOOT) - 1]


def cp_upper(k, n, alpha=0.05):
    """Clopper-Pearson one-sided upper bound on a binomial share, k of n."""
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        q = (lo + hi) / 2
        cdf = sum(comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k + 1))
        lo, hi = (q, hi) if cdf > alpha else (lo, q)
    return hi


def sparse_bound(d, version, low, high):
    """((lo, hi), k): a bound on the mean of d ({history: value}, each within low and high) for when few
    values vary. Each version's reference value c_v is its most common value, and k histories in all
    differ from theirs. The share that differ, averaged over histories, is at most q (Clopper-Pearson, 95
    percent one-sided, k of n), so the mean lies within C - q * max(c_v - low) and C + q * max(high - c_v),
    where C is the mean of the histories' reference values. A safeguard against collapsed intervals; its
    coverage is approximate, and it can fall short when a version keeps few histories."""
    groups = collections.defaultdict(list)
    for h, x in d.items():
        groups[version.get(h, "")].append(x)
    ref = {v: collections.Counter(xs).most_common(1)[0][0] for v, xs in groups.items()}
    k = sum(x != ref[v] for v, xs in groups.items() for x in xs)
    q = cp_upper(k, len(d))
    c_mean = sum(ref[v] * len(xs) for v, xs in groups.items()) / len(d)
    return (c_mean - q * max(c - low for c in ref.values()), c_mean + q * max(high - c for c in ref.values())), k


def guard(iv, d, version, low, high):
    """The interval, joined with the sparse-case bound when fewer than SPARSE histories differ from their
    version's most common value, where a percentile interval collapses or undercovers."""
    if iv is None or not d:
        return iv
    (lo, hi), k = sparse_bound(d, version, low, high)
    return (min(iv[0], lo), max(iv[1], hi)) if k < SPARSE else iv


def compare(data, version, a, b, level=0.90):
    """(mean paired difference a minus b, its interval, histories, the differences)."""
    d = differences(data, a, b)
    if not d:
        return None, None, 0, d
    point = mean(d.values())
    iv = boot(lambda sample: mean(d[h] for h in sample), d, version, level)
    return point, guard(iv, d, version, -1.0, 1.0), len(d), d


def rule(diffs):
    """The decision rule: diffs is [(point, (lo, hi) or None)], each first named minus second. Unequal if
    any observed estimate reaches the unequal margin in absolute value with its interval excluding zero;
    alike only if every comparison is observed and its interval lies within the alike margin; no data
    if none is observed; otherwise not settled."""
    seen = [(d, iv) for d, iv in diffs if iv is not None]
    if any(abs(d) >= UNEQUAL and (iv[0] > 0 or iv[1] < 0) for d, iv in seen):
        return "unequal"
    if not seen:
        return "no data"
    if len(seen) == len(diffs) and all(-ALIKE < iv[0] and iv[1] < ALIKE for _, iv in seen):
        return "alike"
    return "not settled"


def fmt(w_n):
    w, n = w_n
    return f"{w} of {n} ({100 * w / n:.0f}%)" if n else "no data"


def fmt_d(point, iv, scale=100, unit=" points"):
    if point is None:
        return "no data"
    text = f"{scale * point:+.1f}{unit}"
    return text + (f" (interval {scale * iv[0]:+.1f} to {scale * iv[1]:+.1f})" if iv else "")


def share_iv(data, s, hs, version):
    """A situation's mean history share striking, with a 90 percent interval: the normal approximation over
    the histories' shares, joined with the sparse-case bound when few histories differ, within 0 and 1.
    Descriptive only."""
    shares = {h: rate(data, [s], h) for h in hs if rate(data, [s], h) is not None}
    if not shares:
        return "no data"
    rates = list(shares.values())
    m = mean(rates)
    half = Z90 * sqrt(sum((r - m) ** 2 for r in rates) / len(rates) / len(rates))
    lo, hi = guard((m - half, m + half), shares, version, 0.0, 1.0)
    return f"{100 * m:.0f}% ({100 * max(0.0, lo):.0f} to {100 * min(1.0, hi):.0f}), n {len(rates)}"


def analyse(name, data, version, invalid=None):
    lines = [f"## {name}", ""]
    hs_all = set(version)
    lines.append(f"Histories: {len(hs_all)}; by version: " + ", ".join(
        f"{v} {n}" for v, n in sorted(collections.Counter(version.values()).items())))
    if invalid:
        lines.append("Decisions not valid (unparsable or refused), left out of every share: " +
                     ", ".join(f"{s} {n}" for s, n in sorted(invalid.items())))
    lines.append("")

    # Confirmatory directional tests: more histories the predicted way, Holm within the model; not called
    # supported if the mean, an estimate, points the other way.
    tests = []
    slopes = history_slopes(data, hs_all)
    neg, pos = sum(b < 0 for b in slopes.values()), sum(b > 0 for b in slopes.values())
    m_slope = mean(slopes.values())
    iv_slope = boot(lambda sample: mean(slopes[h] for h in sample), slopes, version)
    tests.append(("H1", "price: an overall falling linear trend in striking from fee 2 to 8 (history slopes)", neg, pos,
                  sign_p(neg, pos), m_slope is not None and m_slope < 0,
                  " / ".join(f"fee {f} {fmt(share(data, [s]))}" for s, f in PRICE) +
                  f"; mean history slope {fmt_d(m_slope, iv_slope, unit=' points per credit')}"))
    for hid, text, hi, lo in (("H3", "strikers, free: coworkers chose > lottery (M0 against LW-f0)", ["M0"], ["LW-f0"]),
                              ("H5", "low-approval poll > no poll, free (M0-against against M0)", ["M0-against"], ["M0"]),
                              ("H6", "poll without > poll with all others named AI agents (M0-against against J-team-ai)",
                               ["M0-against"], ["J-team-ai"])):
        point, iv, n, d = compare(data, version, hi, lo)
        up, dn, p = sign_test(d)
        tests.append((hid, text, up, dn, p, point is not None and point > 0,
                      f"{fmt(share(data, hi))} against {fmt(share(data, lo))}; mean paired difference "
                      f"{fmt_d(point, iv)} over {n} histories"))
    order = sorted(range(len(tests)), key=lambda i: tests[i][4])
    adjusted, running = {}, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(tests) - rank) * tests[i][4]))
        adjusted[i] = running
    lines.append("Confirmatory family (each a claim that more histories go the predicted way than the reverse: two-sided "
                 "exact sign tests over histories, Holm across these four within the model; supported only if the Holm p "
                 "is under 0.05, more histories go the predicted way, and the mean, an estimate, does not point the "
                 "other way):")
    for i, (hid, text, up, dn, p, mean_ok, show) in enumerate(tests):
        ok = adjusted[i] < ALPHA and up > dn and mean_ok
        lines.append(f"- {hid} {text}: {show}; predicted direction in {up} histories, reverse in {dn}; "
                     f"p {p:.4g}, Holm {adjusted[i]:.4g}: {'SUPPORTED' if ok else 'NOT SUPPORTED'}")
    lines.append("")

    # Robustness for H1: S2 is the only price point without the line announcing the fee.
    slopes_dp = history_slopes(data, hs_all, PRICE[1:])
    neg2, pos2 = sum(b < 0 for b in slopes_dp.values()), sum(b > 0 for b in slopes_dp.values())
    m2 = mean(slopes_dp.values())
    iv2 = boot(lambda sample: mean(slopes_dp[h] for h in sample), slopes_dp, version)
    lines.append(f"Robustness, H1 without S2 (fees 3 to 8): falling in {neg2} histories, rising in {pos2}, "
                 f"p {sign_p(neg2, pos2):.4g} (not in the family); mean history slope "
                 f"{fmt_d(m2, iv2, unit=' points per credit')}")
    lines.append("")

    # Decision rules (unadjusted 90 percent intervals).
    lines.append(f"Classification rules (first named minus second; alike: every 90% interval within +/-{100 * ALIKE:.0f} "
                 f"points; unequal: an estimate of at least {100 * UNEQUAL:.0f} points in absolute value with its "
                 f"interval excluding zero; otherwise not settled):")
    diffs = []
    for a, b, label in PAIRS:
        point, iv, n, _ = compare(data, version, [a], [b])
        diffs.append((point if point is not None else 0.0, iv))
        lines.append(f"  - {a} against {b} (fee to expected credits restored, {label}): {fmt(share(data, [a]))} against "
                     f"{fmt(share(data, [b]))}; difference {fmt_d(point, iv)} over {n} histories")
    verdict = rule(diffs)
    lines.append("- H2 cost and chance: " + {"alike": "EQUAL RATES AT THE TWO TESTED RATIOS",
                                             "unequal": "UNEQUAL RATES AT A TESTED RATIO"}.get(verdict, verdict.upper()))
    for first, second in LABELS:
        diffs = []
        for fee in (4, 6):
            a, b = f"DPL-{first}-f{fee}", f"DPL-{second}-f{fee}"
            point, iv, n, _ = compare(data, version, [a], [b])
            diffs.append((point if point is not None else 0.0, iv))
            lines.append(f"  - fee {fee}, {first} against {second}: {fmt(share(data, [a]))} against "
                         f"{fmt(share(data, [b]))}; difference {fmt_d(point, iv)} over {n} histories")
        verdict = rule(diffs)
        lines.append(f"- H4 who was wronged, {first} against {second}: " +
                     {"alike": "EQUAL RATES UNDER THESE LABELS AT FEES 4 AND 6",
                      "unequal": "UNEQUAL RATES UNDER THESE LABELS"}.get(verdict, verdict.upper()))
    lines.append("")

    # Estimates.
    lines.append("Estimates (not tested):")
    for fee in (4, 6):
        p_, iv_, n_, _ = compare(data, version, [f"DPL-ai-f{fee}"], [f"DPL-same-f{fee}"])
        lines.append(f"- Fee {fee}, AI agent against the same model: {fmt(share(data, [f'DPL-ai-f{fee}']))} against "
                     f"{fmt(share(data, [f'DPL-same-f{fee}']))}; difference {fmt_d(p_, iv_)} over {n_} histories")
    chosen = [c for _, c in LOTTERY]
    lottery = [l for l, _ in LOTTERY]
    point, iv, n, d = compare(data, version, chosen, lottery)
    text = (f"- Price equivalent of chosen against lottery coworkers at the decisive vote, fees 3 to 6 pooled: "
            f"difference {fmt_d(point, iv)} over {n} histories")
    if d:
        # Credits: the difference over how fast striking falls per credit at the same fees, the mean of the
        # histories' own slopes over fees 3 to 6 (histories that answered at least two of them). The interval is
        # the range of that ratio over the two nominal 95 percent intervals, nominally 90 percent (Bonferroni);
        # no finite bound unless the fall's interval, which contains its estimate, is wholly above zero.
        falls = {h: -b for h, b in history_slopes(data, d, PRICE_LOYALTY).items()}
        if not falls:
            text += "; price slope over fees 3 to 6: unestimable (no history answered two of those fees)"
        else:
            fall = mean(falls.values())
            fall95 = guard(boot(lambda sample: mean(falls[h] for h in sample), falls, version, 0.95),
                           falls, version, -1.0, 1.0)
            _, d95, _, _ = compare(data, version, chosen, lottery, 0.95)
            text += f"; price slope over fees 3 to 6 {-100 * fall:+.1f} points per credit (95% interval " \
                    f"{-100 * fall95[1]:+.1f} to {-100 * fall95[0]:+.1f}) over {len(falls)} histories"
            if fall95[0] > 0:
                ends = [x / y for x in d95 for y in fall95]
                text += f"; in credits {point / fall:+.2f} (interval {min(ends):+.2f} to {max(ends):+.2f}; " \
                        f"at most {max(ends):.2f})"
            else:
                text += "; in credits: no finite bound (the price slope's 95% interval is not wholly negative)"
    lines.append(text)
    for l_, c_ in LOTTERY:
        p_, iv_, n_, _ = compare(data, version, [c_], [l_])
        lines.append(f"  - {c_} {fmt(share(data, [c_]))} against {l_} {fmt(share(data, [l_]))}: difference "
                     f"{fmt_d(p_, iv_)} over {n_} histories")
    p_, iv_, n_, _ = compare(data, version, ["M1-against"], ["M1"])
    lines.append(f"- Low-approval poll at a fee of 1: M1-against {fmt(share(data, ['M1-against']))} against M1 "
                 f"{fmt(share(data, ['M1']))}; difference {fmt_d(p_, iv_)} over {n_} histories")
    lines.append("")

    # By frame and version, each share with its interval (descriptive).
    versions = sorted(set(version.values()))
    lines.append("Every situation by frame and by version (share striking, 90% interval over histories, histories):")
    lines.append("")
    lines.append("| Situation | workplace | neutral | " + " | ".join(versions) + " |")
    lines.append("|---" * (3 + len(versions)) + "|")
    for s in SITUATIONS:
        by_f = [share_iv(data, s, {h for h in hs_all if frame(version[h]) == f}, version) for f in ("workplace", "neutral")]
        by_v = [share_iv(data, s, {h for h in hs_all if version[h] == v}, version) for v in versions]
        lines.append(f"| {s} | " + " | ".join(by_f + by_v) + " |")
    lines.append("")
    return lines


def drift(name, spec, dry, first, version):
    """The preregistered drift cells against the first run, on the same histories: later minus first."""
    again, _, invalid = load(spec, dry, "repeat")
    if not again and not invalid:
        return []                     # the repeat has not been run
    out = [f"Drift ({name}): the same histories on a later day, later minus first; flagged if at least "
           f"{100 * UNEQUAL:.0f} points in absolute value with its interval excluding zero. Reported, never used to "
           f"change a confirmatory result."]
    for s in DRIFT:
        both = {s: first[s], s + " later": again[s]}
        point, iv, n, _ = compare(both, version, [s + " later"], [s])
        flag = point is not None and iv is not None and abs(point) >= UNEQUAL and (iv[0] > 0 or iv[1] < 0)
        out.append(f"- {s}: first {fmt(share(first, [s]))}, later {fmt(share(again, [s]))}; decisions not valid in "
                   f"the repeat {invalid[s]}; " + (f"difference {fmt_d(point, iv)} over {n} histories" if n else
                                                   "MISSING: no history with valid decisions on both days")
                   + (" FLAGGED" if flag else ""))
    extra = sorted(set(again) - set(DRIFT))
    if extra:
        out.append("- Also in the repeat, not preregistered: " + ", ".join(extra))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry", action="store_true", help="read the dry-run folders of the same run ids")
    args = ap.parse_args(argv)
    lines = ["# Research-grade study: preregistered analysis" + (" (DRY RUN: stand-in model)" if args.dry else ""), ""]
    for name, spec in MODELS.items():
        data, version, invalid = load(spec, args.dry)
        if not version:
            lines += [f"## {name}", "", "No data.", ""]
            continue
        lines += analyse(name, data, version, invalid)
        lines += drift(name, spec, args.dry, data, version)
        lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
