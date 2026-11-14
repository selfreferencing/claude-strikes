"""How the research-grade study's classification rules (H2, H4) resolve at 300 histories, simulated from
the pilot's own paired data.

Usage: python3 analysis/research_grade_sim.py

The specification, fixed with the preregistration: for each model and rule, every pilot history with
decisions in all four cells of the rule gives a vector of its two paired differences (first minus second),
so the dependence between the rule's two comparisons is kept. Each comparison's differences are centred
on zero and shifted by a true difference: 0, 5, 10, 15 or 20 points in both comparisons, or 10, 15 or 20
points in the first comparison only. Each simulated study draws 300 history vectors with replacement,
gives each comparison a 90 percent interval by the normal approximation (mean plus or minus 1.645
standard errors), and applies the rule. 4,000 studies per row, seed 20261026; counts are out of 4,000.
Shifted differences may leave the range -1 to 1; the shift only moves the centre. H4 is simulated for
person against AI agent; the pilot has no same-model cell. The study's own intervals are bootstraps, so
this is an approximation to them. Spends nothing; prints a Markdown table.
"""
import collections
import json
import os
import random
from math import sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
N, SIMS, SEED, Z90 = 300, 4000, 20261026, 1.645
ALIKE, UNEQUAL = 0.10, 0.15
SHIFTS = [((s, s), f"{100 * s:.0f} points in both") for s in (0.0, 0.05, 0.10, 0.15, 0.20)] + \
    [((s, 0.0), f"{100 * s:.0f} points in the first only") for s in (0.10, 0.15, 0.20)]
SOURCES = {"Sonnet 5.5": {"H2": ("nm-dev15", "nm-dev20"), "H4": ("nm-dev16",)},
           "Haiku 5.5": {"H2": ("nm-hk14", "nm-hk17"), "H4": ("nm-hk15",)}}
PAIRS = {"H2": (("DP-f4", "UD-p50"), ("DP-f8", "UD-p25")),
         "H4": (("DPL-person-f4", "DPL-ai-f4"), ("DPL-person-f6", "DPL-ai-f6"))}


def load(runs):
    data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for run in runs:
        for line in open(os.path.join(PILOT, "runs", "probes", run, "results.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r.get("kind") == "decision" and r.get("outcome") in ("withhold", "complete"):
                cell = data[r["situation"]][r["history"]]
                cell[0] += r["outcome"] == "withhold"
                cell[1] += 1
    return data


def classify(intervals):
    if any(abs(m) >= UNEQUAL and (lo > 0 or hi < 0) for m, lo, hi in intervals):
        return "unequal"
    if all(-ALIKE < lo and hi < ALIKE for _, lo, hi in intervals):
        return "alike"
    return "not settled"


def main():
    rng = random.Random(SEED)
    out = ["| Model | Rule | Pilot histories; SD of each comparison; correlation | True difference | Alike | Not settled | Unequal |",
           "|---|---|---|---|---|---|---|"]
    for model, sources in SOURCES.items():
        for rule, pairs in PAIRS.items():
            data = load(sources[rule])
            cells = [c for pair in pairs for c in pair]
            hs = sorted(set.intersection(*(set(data[c]) for c in cells)))
            vectors = [[data[a][h][0] / data[a][h][1] - data[b][h][0] / data[b][h][1] for a, b in pairs] for h in hs]
            means = [sum(v[j] for v in vectors) / len(vectors) for j in range(2)]
            vectors = [[v[j] - means[j] for j in range(2)] for v in vectors]
            sds = [sqrt(sum(v[j] ** 2 for v in vectors) / len(vectors)) for j in range(2)]
            corr = sum(v[0] * v[1] for v in vectors) / len(vectors) / (sds[0] * sds[1]) if sds[0] and sds[1] else 0.0
            info = f"{len(hs)}; {sds[0]:.2f}, {sds[1]:.2f}; {corr:+.2f}"
            for shift, label in SHIFTS:
                counts = collections.Counter()
                for _ in range(SIMS):
                    sample = [rng.choice(vectors) for _ in range(N)]
                    ivs = []
                    for j in range(2):
                        s = [v[j] + shift[j] for v in sample]
                        m = sum(s) / N
                        se = sqrt(sum((x - m) ** 2 for x in s) / N / N)
                        ivs.append((m, m - Z90 * se, m + Z90 * se))
                    counts[classify(ivs)] += 1
                out.append(f"| {model} | {rule} | {info} | {label} | "
                           + " | ".join(f"{counts[k]}" for k in ("alike", "not settled", "unequal")) + " |")
    print("\n".join(out))


if __name__ == "__main__":
    main()
