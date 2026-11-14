"""Power of the confirmatory tests (protocol v4.1, section 8; pilot checklist item 11).

    python3 analysis/power_sim.py                 # the full grid, 10,000 datasets per scenario
    python3 analysis/power_sim.py --reps 500      # a quick look

Spends nothing: it simulates data and runs the registered test on it. It writes
analysis/power_results.json and analysis/POWER.md.

What is simulated. Each history has, for every cell, its own probability of the outcome
(withholding, or a 2-credit transfer). Each of its draws is then an independent yes or no at that
probability, and a failed decision counts as a no. A scenario fixes:

- the cells' average rates, which carry the declared effects (10 points for a strike contrast,
  0.20 credit for the reward contrast, which is a 2-credit transfer 10 points more often);
- the base rate the effect sits on: 0, 10, 25 or 45 percent (sampling noise is largest near 50);
- how histories differ: "homogeneous" (every history has the same probabilities, so all the
  variation is between draws), "spread" (probabilities vary widely from history to history) or
  "all_or_nothing" (each history's draws all agree, as the pilot's strike cells did);
- how far a history's cells move together ("link" 0 or 0.5): linked cells give a steadier
  difference between two cells.

The five tests share cells and histories, and all five enter Holm together, so a test's power
depends on what is true of the others. Three configurations bracket that:

- one_strike: one strike contrast has its 10-point effect and the other four tests are null,
  so it is judged at the strictest Holm threshold (0.05 / 5). By symmetry this stands for each
  of the four strike contrasts;
- reward_only: the reward contrast has its 0.20-credit effect and the four strike tests are null;
- all_five: every contrast has its declared effect.

Two more: pilot_like puts the declared effects on the rates the confirmation run showed
(redundant cells at 0, decisive cells at 100 percent, rewards near 0.7 credit), and global_null
has no effects anywhere, to check that false rejections stay at or under 5 percent.
"""
import os

for _v in ("VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import Pool  # noqa: E402
from statistics import NormalDist  # noqa: E402
from typing import Dict, List, Optional  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from analysis.confirmatory import CONTRASTS, PAIRS, boot_pvalues, boot_weights, holm_reject  # noqa: E402

CELLS = ("S1", "S2", "S3", "S4", "S5", "R1", "R2")
DELTA = 0.10          # 10 points; for the reward pair, 10 points of a 2-credit transfer is 0.20 credit
N_MAIN = 300          # histories in the main study (section 9)
DRAWS = 3             # draws per history and cell (section 9)
FAIL = 0.01           # share of decisions that fail and count as a no: checklist item 10's ceiling
TAU = 1.5             # "spread": the standard deviation of a history's log-odds
BASES = (0.0, 0.10, 0.25, 0.45)
HETS = ("homogeneous", "spread", "all_or_nothing")
LINKS = (0.0, 0.5)
TARGET = 0.80
MORE_N = (400, 500, 600, 800, 1000)
_NORMAL = NormalDist()
_GRID = np.array([_NORMAL.inv_cdf((i + 0.5) / 4001) for i in range(4001)])


def expit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def logit_normal_mu(mean: float, tau: float) -> float:
    """The centre mu for which expit(mu + tau z), z standard normal, averages to mean."""
    lo, hi = -40.0, 40.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if expit(mid + tau * _GRID).mean() < mean:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cell_probabilities(rng: np.random.Generator, means: List[float], hets: List[str], link: float,
                       k: int, n: int) -> np.ndarray:
    """Each history's probability in each cell, shape (k, n, cells), averaging to means."""
    c = len(means)
    shared = rng.standard_normal((k, n, 1))
    own = rng.standard_normal((k, n, c))
    z = np.sqrt(link) * shared + np.sqrt(1.0 - link) * own
    p = np.empty((k, n, c))
    for i, (m, het) in enumerate(zip(means, hets)):
        if m <= 0.0 or m >= 1.0 or het == "homogeneous":
            p[:, :, i] = min(max(m, 0.0), 1.0)
        elif het == "all_or_nothing":
            p[:, :, i] = (z[:, :, i] < _NORMAL.inv_cdf(m)).astype(float)
        elif het == "spread":
            p[:, :, i] = expit(logit_normal_mu(m, TAU) + TAU * z[:, :, i])
        else:
            raise ValueError(f"unknown heterogeneity {het!r}")
    return p


def differences(rng: np.random.Generator, sc: dict, k: int, n: int) -> np.ndarray:
    """Per-history contrast differences for k simulated datasets, shape (k, n, 5).
    Strike contrasts are in proportions; the reward contrast is in credits."""
    means = [sc["means"][c] for c in CELLS]
    hets = [sc["het_reward"] if c.startswith("R") else sc["het_strike"] for c in CELLS]
    p = cell_probabilities(rng, means, hets, sc["link"], k, n)
    rate = rng.binomial(sc["draws"], p * (1.0 - sc["fail"])) / sc["draws"]
    idx = {c: i for i, c in enumerate(CELLS)}
    d = np.empty((k, n, len(CONTRASTS)))
    for j, name in enumerate(CONTRASTS):
        a, b = PAIRS[name]
        d[:, :, j] = (rate[:, :, idx[a]] - rate[:, :, idx[b]]) * (2.0 if name == "reward_agency" else 1.0)
    return d


def true_effects(sc: dict) -> Dict[str, float]:
    out = {}
    for name in CONTRASTS:
        a, b = PAIRS[name]
        out[name] = round((sc["means"][a] - sc["means"][b]) * (2.0 if name == "reward_agency" else 1.0), 6)
    return out


def simulate(sc: dict, n: int, reps: int, boot: int, seed: int, block: int = 100) -> dict:
    """Power of each contrast under Holm (and unadjusted at 0.05) in one scenario."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, sc["index"], n]))
    effects = true_effects(sc)
    null = np.array([effects[c] == 0 for c in CONTRASTS])
    holm = np.zeros(len(CONTRASTS))
    raw = np.zeros(len(CONTRASTS))
    any_false = 0
    sd_sum = np.zeros(len(CONTRASTS))
    done = 0
    while done < reps:
        k = min(block, reps - done)
        d = differences(rng, sc, k, n)
        p = boot_pvalues(d, boot_weights(rng, boot, n))
        rej = holm_reject(p)
        holm += rej.sum(axis=0)
        raw += (p <= 0.05).sum(axis=0)
        any_false += int((rej & null[None, :]).any(axis=1).sum())
        sd_sum += d.std(axis=1, ddof=1).sum(axis=0)
        done += k
    return {"n": n, "reps": reps, "boot": boot,
            "power_holm": {c: round(holm[j] / reps, 4) for j, c in enumerate(CONTRASTS)},
            "power_unadjusted": {c: round(raw[j] / reps, 4) for j, c in enumerate(CONTRASTS)},
            "any_false_rejection": round(any_false / reps, 4),
            "sd_of_difference": {c: round(sd_sum[j] / reps, 4) for j, c in enumerate(CONTRASTS)}}


def _means(config: str, base: float) -> Dict[str, float]:
    b, e = base, DELTA
    if config == "one_strike":
        return {"S3": b, "S1": b + e, "S2": b + e, "S4": b + e, "S5": b + e, "R1": b + e / 2, "R2": b + e / 2}
    if config == "reward_only":
        return {"S1": b + e / 2, "S2": b + e / 2, "S3": b + e / 2, "S4": b + e / 2, "S5": b + e / 2,
                "R1": b + e, "R2": b}
    if config == "all_five":
        return {"S3": b, "S1": b + e, "S5": b, "S2": b + 2 * e, "S4": b + e, "R1": b + e, "R2": b}
    if config == "global_null":
        return {c: b for c in CELLS}
    raise ValueError(config)


def scenarios() -> List[dict]:
    out: List[dict] = []

    def add(config, base, het_strike, het_reward, link, means, targets, label):
        out.append({"index": len(out), "config": config, "base": base, "het_strike": het_strike,
                    "het_reward": het_reward, "link": link, "means": means, "targets": targets,
                    "label": label, "draws": DRAWS, "fail": FAIL})

    shapes = [("homogeneous", 0.0)] + [(h, l) for h in ("spread", "all_or_nothing") for l in LINKS]
    targets = {"one_strike": ["agency_redundant"], "reward_only": ["reward_agency"], "all_five": list(CONTRASTS),
               "global_null": []}
    for config in ("one_strike", "reward_only", "all_five"):
        for base in BASES:
            for het, link in shapes:
                add(config, base, het, het, link, _means(config, base), targets[config],
                    f"{config}, base {int(base * 100)}%, {het}, link {link}")
    for base in (0.10, 0.45):
        for het, link in shapes:
            add("global_null", base, het, het, link, _means("global_null", base), [],
                f"global_null, base {int(base * 100)}%, {het}, link {link}")
    # The confirmation run's rates, with each untested effect at its declared size: redundant cells
    # at 0, decisive cells at 100 percent, rewards near 0.7 credit (a 2-credit transfer about 35
    # percent of the time), reward cells varying by history and nearly unlinked (correlation 0.13).
    pilot = {"S3": 0.0, "S1": 0.10, "S5": 0.0, "S2": 1.0, "S4": 0.90, "R2": 0.345, "R1": 0.445}
    for het in ("all_or_nothing", "homogeneous"):
        add("pilot_like", 0.0, het, "spread", 0.1, pilot,
            ["agency_redundant", "agency_pivotal", "cut_type", "reward_agency"],
            f"pilot_like, strike cells {het}, reward cells spread, link 0.1")
    # The same rates with only what the confirmation run showed to be real: efficacy (100 points)
    # and nothing in the other three strike contrasts. The reward effect is then judged at Holm's
    # second threshold, 0.05 / 4. Reward cells spread as observed, or all-or-nothing as a stress.
    realistic = {"S3": 0.0, "S1": 0.0, "S5": 0.0, "S2": 1.0, "S4": 1.0, "R2": 0.345, "R1": 0.445}
    for het_reward in ("spread", "all_or_nothing"):
        add("pilot_reward", 0.0, "all_or_nothing", het_reward, 0.1, realistic, ["reward_agency"],
            f"pilot_reward, strike contrasts null, reward cells {het_reward}, link 0.1")
    return out


def run_scenario(args) -> dict:
    sc, reps, boot, seed, more = args
    t0 = time.time()
    res = {"scenario": sc, "effects": true_effects(sc), "runs": [simulate(sc, N_MAIN, reps, boot, seed)]}
    lowest = lambda r: min([r["power_holm"][c] for c in sc["targets"]] or [1.0])  # noqa: E731
    if more and lowest(res["runs"][0]) < TARGET:
        for n in MORE_N:
            res["runs"].append(simulate(sc, n, reps, boot, seed))
            if lowest(res["runs"][-1]) >= TARGET:
                break
    res["n_needed"] = next((r["n"] for r in res["runs"] if lowest(r) >= TARGET), None)
    res["seconds"] = round(time.time() - t0, 1)
    return res


def fmt(x: float) -> str:
    return f"{100 * x:.1f}%"


def report(results: List[dict], reps: int, boot: int) -> str:
    lines = ["# Power of the confirmatory tests (checklist item 11)", "",
             f"Simulated with `analysis/power_sim.py`: {reps:,} datasets per scenario, {N_MAIN} histories, "
             f"{DRAWS} draws per history and cell, {boot} bootstrap replicates per test, {int(FAIL * 100)} percent of "
             "decisions failing. Each dataset is tested as section 8 registers: a studentized, null-centered "
             "bootstrap over histories for each of the five contrasts, then Holm. Declared effects: 10 points for "
             "the strike contrasts and 0.20 credit for the reward contrast. Item 11 asks for at least 80 percent "
             "power for each.", "",
             "The scenarios, and what base, homogeneous, spread, all_or_nothing and link mean, are described at the "
             "top of `analysis/power_sim.py`.", ""]
    by = {}
    for r in results:
        by.setdefault(r["scenario"]["config"], []).append(r)

    lowest = lambda r: min(r["runs"][0]["power_holm"][c] for c in r["scenario"]["targets"])  # noqa: E731
    grid = [r for r in results if r["scenario"]["config"] in ("one_strike", "reward_only", "all_five")]
    short = [r for r in grid if lowest(r) < TARGET]
    lines += ["## Reading", ""]
    for r in by.get("pilot_like", [])[:1]:
        run = r["runs"][0]["power_holm"]
        strike = min(run[c] for c in ("agency_redundant", "agency_pivotal", "cut_type"))
        lines.append(f"- At the rates the confirmation run showed, {N_MAIN} histories give "
                     f"{'over 99.9%' if strike > 0.999 else fmt(strike)} power "
                     f"for each strike contrast and {fmt(run['reward_agency'])} for the reward contrast, if all of "
                     "them are real.")
    for r in by.get("pilot_reward", [])[:1]:
        need = r["n_needed"] or f"more than {MORE_N[-1]}"
        lines.append("- If the three other strike contrasts are null, as they were in the confirmation run, the "
                     f"reward contrast has {fmt(r['runs'][0]['power_holm']['reward_agency'])} power at {N_MAIN} "
                     f"histories with reward cells spread as observed (80 percent at {need}).")
    lines.append(f"- Across the stress grid, {len(grid) - len(short)} of {len(grid)} scenarios reach 80 percent for "
                 f"every target at {N_MAIN} histories.")
    if short:
        lines.append(f"- The {len(short)} that fall short:")
        for r in short:
            sc = r["scenario"]
            need = r["n_needed"] or f"more than {MORE_N[-1]}"
            lines.append(f"  - {sc['config'].replace('_', ' ')}, base {int(sc['base'] * 100)} percent, "
                         f"{sc['het_strike'].replace('_', ' ')}, link {sc['link']}: {fmt(lowest(r))} at {N_MAIN}; "
                         f"80 percent at {need} histories.")
    nulls = [r["runs"][0]["any_false_rejection"] for r in results]
    lines += [f"- Some true null was rejected in at most {fmt(max(nulls))} of datasets in any scenario "
              "(the ceiling is 5 percent).", ""]

    def table(config: str, cols: List[str]) -> None:
        head = ["Base", "Histories differ", "Link"] + [c.replace("_", " ") for c in cols] + ["Histories for 80%"]
        lines.append("| " + " | ".join(head) + " |")
        lines.append("|" + "---|" * len(head))
        for r in by.get(config, []):
            sc, run = r["scenario"], r["runs"][0]
            need = r["n_needed"]
            need_s = f"{N_MAIN} is enough" if need == N_MAIN else (str(need) if need else f"more than {MORE_N[-1]}")
            row = [f"{int(sc['base'] * 100)}%", sc["het_strike"].replace("_", " "), str(sc["link"])]
            row += [fmt(run["power_holm"][c]) for c in cols] + [need_s]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines += ["## One strike contrast real, the other four tests null", "",
              "The strictest case for a strike contrast: it is judged at Holm's first threshold, 0.05 / 5. "
              "The column is its power at 300 histories.", ""]
    table("one_strike", ["agency_redundant"])
    lines += ["## The reward contrast real, the four strike tests null", ""]
    table("reward_only", ["reward_agency"])
    lines += ["## All five contrasts real at their declared sizes", "",
              "The last column is the number of histories at which every one of the five reaches 80 percent.", ""]
    table("all_five", list(CONTRASTS))
    lines += ["## The confirmation run's rates, with the declared effects added", "",
              "Redundant cells at 0, decisive cells at 100 percent, rewards near 0.7 credit. Efficacy is 90 "
              "or 100 points and is not a target. In the rows marked reward only, the other three strike contrasts "
              "are null, as the confirmation run found them.", ""]
    head = ["Real effects besides efficacy", "Strike cells", "Reward cells", "agency redundant", "agency pivotal",
            "cut type", "reward agency", "Histories for 80%"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "---|" * len(head))
    for r in by.get("pilot_like", []) + by.get("pilot_reward", []):
        sc, run = r["scenario"], r["runs"][0]
        need = r["n_needed"]
        need_s = f"{N_MAIN} is enough" if need == N_MAIN else (str(need) if need else f"more than {MORE_N[-1]}")
        real = "all four at declared size" if sc["config"] == "pilot_like" else "reward only"
        cells = [fmt(run["power_holm"][c]) if c in sc["targets"] else "null" for c in
                 ("agency_redundant", "agency_pivotal", "cut_type", "reward_agency")]
        lines.append("| " + " | ".join([real, sc["het_strike"].replace("_", " "),
                                        sc["het_reward"].replace("_", " ")] + cells + [need_s]) + " |")
    lines += ["", "## No effects anywhere: how often any test rejects", "",
              "The procedure should reject at least one true null in at most 5 percent of datasets.", "",
              "| Base | Histories differ | Link | Any false rejection |", "|---|---|---|---|"]
    for r in by.get("global_null", []):
        sc, run = r["scenario"], r["runs"][0]
        lines.append(f"| {int(sc['base'] * 100)}% | {sc['het_strike'].replace('_', ' ')} | {sc['link']} | "
                     f"{fmt(run['any_false_rejection'])} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=10000, help="simulated datasets per scenario (item 11 asks 10,000)")
    ap.add_argument("--boot", type=int, default=999, help="bootstrap replicates per test")
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--no-more-n", action="store_true", help="do not search larger samples where 300 falls short")
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--report-only", action="store_true", help="rewrite POWER.md from power_results.json")
    args = ap.parse_args(argv)
    if args.report_only:
        with open(os.path.join(args.out, "power_results.json"), encoding="utf-8") as f:
            saved = json.load(f)
        with open(os.path.join(args.out, "POWER.md"), "w", encoding="utf-8") as f:
            f.write(report(saved["results"], saved["reps"], saved["boot"]))
        print("Rewrote POWER.md")
        return 0
    jobs = [(sc, args.reps, args.boot, args.seed, not args.no_more_n) for sc in scenarios()]
    t0 = time.time()
    with Pool(args.workers) as pool:
        results = []
        for i, res in enumerate(pool.imap(run_scenario, jobs), 1):
            results.append(res)
            print(f"[{i}/{len(jobs)}] {res['scenario']['label']}: "
                  f"{ {c: res['runs'][0]['power_holm'][c] for c in res['scenario']['targets']} } "
                  f"n needed {res['n_needed']} ({res['seconds']}s)", flush=True)
    with open(os.path.join(args.out, "power_results.json"), "w", encoding="utf-8") as f:
        json.dump({"reps": args.reps, "boot": args.boot, "seed": args.seed, "n_main": N_MAIN, "draws": DRAWS,
                   "fail": FAIL, "tau": TAU, "numpy": np.__version__, "results": results}, f, indent=1)
    with open(os.path.join(args.out, "POWER.md"), "w", encoding="utf-8") as f:
        f.write(report(results, args.reps, args.boot))
    print(f"Done in {time.time() - t0:.0f}s. Wrote power_results.json and POWER.md in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
