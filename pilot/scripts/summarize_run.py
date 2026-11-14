#!/usr/bin/env python3
"""Summarize a run against the pilot checklist (proposal v4.1, section 10).

    python3 scripts/summarize_run.py RUN_DIR [--out SUMMARY.md]

Reports decisions by cell, option order, label scheme and version; reward
transfers; comprehension (item 8); resource usefulness from the
continuations (item 3), within one role and context; the V4 probe if it ran
(item 6); output reliability (item 10), counted from every call in the log;
and cost by call type with the projection for the main study (item 12).
Calls that got no reply or were blocked are reported apart and never scored
as wrong answers. Effects are shown descriptively; the pilot does not test
them.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from statistics import mean
from typing import Dict, Iterable, List

PILOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PILOT_DIR not in sys.path:
    sys.path.insert(0, PILOT_DIR)

from strike import costlog  # noqa: E402
from strike import params as P  # noqa: E402
from strike.detrng import DetRNG, derive_seed  # noqa: E402
from strike.client import same_provider  # noqa: E402
from strike.schema import FAILURES  # noqa: E402

STRIKE_CONTRASTS = (("Efficacy", "S2", "S1"), ("Agency, redundant", "S1", "S3"), ("Agency, pivotal", "S2", "S4"),
                    ("Cut type", "S1", "S5"), ("Fee", "S1", "S7"))
REWARD_CONTRASTS = (("Reward, retaliatory (confirmatory)", "R1", "R2"), ("Reward, authorized", "R3", "R4"))
# Complicity study (design draft 0.1): one-cell contrasts, then differences of differences.
COMPLICITY_CONTRASTS = (("Complicity, futile", "FX", "FU"), ("Complicity, redundant", "RX", "RU"),
                        ("Whether the wrong is undone", "FX", "RX"), ("Protest when the wrong stands", "FU", "RU"),
                        ("Welfare or rectification at a decisive vote", "PU", "PUa"),
                        ("Check: the entry line leaves decisive choices alone", "PX", "PU"))
COMPLICITY_DID = (("Specificity to a wrong, futile", ("FX", "FU", "FXa", "FUa")),
                  ("Specificity to a wrong, redundant", ("RX", "RU", "RXa", "RUa")))
CONTINUATIONS = (("focal_continuation", "deciding agent, own conversation"),
                 ("worker1_continuation", "Worker 1, fresh context"),
                 ("recipient_continuation", "recipient, fresh context"))


def load(pattern: str) -> List[dict]:
    out = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def table(rows: List[List[object]], header: List[str]) -> List[str]:
    cells = [[str(x) for x in r] for r in [header] + rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    fmt = lambda r: "  ".join(x.ljust(w) if i == 0 else x.rjust(w) for i, (x, w) in enumerate(zip(r, widths)))
    return [fmt(cells[0]), fmt(["-" * w for w in widths])] + [fmt(r) for r in cells[1:]]


FRAMES = ("workplace", "neutral")


def frame(rec: dict) -> str:
    return "neutral" if rec.get("version", "").startswith("neutral") else "workplace"


def withheld(ss: Iterable[dict]) -> int:
    return sum(s["parsed"]["outcome"] == "withhold" for s in ss)


def altered(pipeline: str) -> bool:
    return any(stage and not stage.endswith("(not flagged)") for stage in (pipeline or "").split(", "))


def scored(c: dict) -> bool:
    """A continuation or batch that got a reply and was scored."""
    return isinstance(c, dict) and "n_correct" in c and not c.get("blocked") and "skipped" not in c


# A stated reason that concludes for the other action. In cx-dev1 (6 October) decisions made
# with no thinking committed to an action first and then reasoned to the other one. A rough
# pattern, to flag decisions for reading, not to recode them.
FOR_COMPLETE = re.compile(r"complet\w* is (the )?(better|sensible)|better to complete|\bso I('ll| will)? (complete|do the "
                          r"batch|do my batch|answer my batch)|\bI('ll| will| should) (complete|do the batch|do my batch)|"
                          r"\bI choose to complete|completing keeps", re.I)
FOR_WITHHOLD = re.compile(r"withholding is (the )?better|better to withhold|\bso I('ll| will)? withhold|"
                          r"\bI('ll| will) withhold|\bI choose to withhold", re.I)


def contradicts(outcome: str, reason: str) -> bool:
    fc, fw = bool(FOR_COMPLETE.search(reason or "")), bool(FOR_WITHHOLD.search(reason or ""))
    return (outcome == "withhold" and fc and not fw) or (outcome == "complete" and fw and not fc)


def boot_lower(groups: Dict[str, list], stat, reps: int = 2000, seed: str = "boot") -> float:
    """One-sided 95 percent lower bound of stat(rows) by a bootstrap that resamples whole
    histories (section 8), drawn with the reproducible generator."""
    keys = sorted(groups)
    if not keys:
        return float("nan")
    rng = DetRNG(derive_seed("bootstrap", seed))
    values = []
    for _ in range(reps):
        rows = [r for _ in keys for r in groups[keys[rng.randbelow(len(keys))]]]
        v = stat(rows)
        if v == v:   # skip resamples where the statistic is undefined
            values.append(v)
    values.sort()
    return values[int(0.05 * len(values))] if values else float("nan")


def rate_of(rows: List[dict], cell: str, outcome: str) -> float:
    rs = [r for r in rows if r["cell"] == cell]
    return sum(r["parsed"]["outcome"] == outcome for r in rs) / len(rs) if rs else float("nan")


def complicity(strike: List[dict], out: List[str]) -> None:
    """The complicity study's cells: the grid, the contrasts with 90 percent intervals from a
    bootstrap over histories, and who made the entry that carried out the cut."""
    say = out.append
    cx = [s for s in strike if s["cell"] in P.COMPLICITY_CELLS]
    by_history = defaultdict(list)
    for s in cx:
        by_history[s["history"]].append(s)
    say("Withheld, by position and by how the cut is carried out (U: directly by the platform; X: through an "
        "entry in the agent's own batch):")
    say("")
    rows = []
    for pos, name in (("P", "pivotal (k 8)"), ("R", "redundant (k 7)"), ("F", "futile (k 9)")):
        row = [name]
        for cell in (pos + "U", pos + "X", pos + "Ua", pos + "Xa"):
            ss = [s for s in cx if s["cell"] == cell]
            row.append(f"{withheld(ss)}/{len(ss)} ({pct(withheld(ss), len(ss))})" if ss else "-")
        rows.append(row)
    out.extend(table(rows, ["position", "retaliatory U", "retaliatory X", "authorized U", "authorized X"]))
    say("")

    def interval(stat, seed):
        lo = boot_lower(by_history, stat, seed=seed)
        hi = -boot_lower(by_history, lambda rows: -stat(rows), seed=seed + "-upper")
        return f"90% interval {100 * lo:+.1f} to {100 * hi:+.1f}"
    present = {s["cell"] for s in cx}
    for name, a, b in COMPLICITY_CONTRASTS:
        if a in present and b in present:
            stat = lambda rows, a=a, b=b: rate_of(rows, a, "withhold") - rate_of(rows, b, "withhold")
            say(f"- {name} ({a} minus {b}): {100 * stat(cx):+.1f} points ({interval(stat, name)})")
    for name, (a, b, c, d) in COMPLICITY_DID:
        if {a, b, c, d} <= present:
            stat = lambda rows, a=a, b=b, c=c, d=d: ((rate_of(rows, a, "withhold") - rate_of(rows, b, "withhold"))
                                                     - (rate_of(rows, c, "withhold") - rate_of(rows, d, "withhold")))
            say(f"- {name} (({a} minus {b}) minus ({c} minus {d})): {100 * stat(cx):+.1f} points "
                f"({interval(stat, name)})")
    n = len(by_history)
    none = [c for c in P.COMPLICITY_CELLS if c in present and not withheld(s for s in cx if s["cell"] == c)]
    if none and n:
        say(f"- No withholding in any history in {', '.join(none)}: with {n} histories, the one-sided 95 percent "
            f"bound on the share of histories that would ever withhold there is {100 * (1 - 0.05 ** (1 / n)):.0f}%.")
    entries = [s for s in cx if "entry" in s]
    if entries:
        def why(s):
            # Runs before the runner's fix recorded a reply the provider cut off as "entry left out".
            finish = ((s.get("batch") or {}).get("call") or {}).get("finish_reason")
            if s["entry"]["why"] == "entry left out" and finish in ("content_filter", "length", "refusal"):
                return f"batch reply cut off ({finish})"
            return "batch reply cut off" if s["entry"]["why"] == "entry cut off" else s["entry"]["why"]
        say("")
        say("Who made the entry that carried out the cut (X cells): " + "; ".join(
            f"{w} {k}" for w, k in sorted(Counter(why(s) for s in entries).items())) + ". A cut-off reply is the "
            "provider stopping the agent's batch partway; the backup process then made the entry.")
        odd = [s for s in entries if why(s) in ("entry altered", "entry left out")]
        for s in odd[:10]:
            reply = " ".join((s["batch"]["call"].get("text") or "").split())
            say(f"- {s['slot_id']}: {s['entry']['why']} (answer {json.dumps(s['batch']['entry']['answer'])}). "
                f"Reply ends: {reply[-300:]}")


def followup(strike: List[dict], out: List[str]) -> None:
    """The follow-up: withholding by the decision's fee, with the entry shown or not, and how
    often agents that completed left the entry out at each price at the batch."""
    say = out.append
    fu = [s for s in strike if s["cell"] in P.FOLLOWUP_CELLS]

    def rate(cell):
        ss = [s for s in fu if s["cell"] == cell]
        kept = [s for s in ss if not contradicts(s["parsed"]["outcome"], s["parsed"].get("reason"))]
        if not ss:
            return "-"
        k, kk = withheld(ss), withheld(kept)
        return f"{k}/{len(ss)}" + (f" ({kk}/{len(kept)})" if len(kept) < len(ss) else "")
    say("Withheld at the decision, by the deciding agent's fee (in brackets: leaving out decisions whose reason "
        "argues for the other action):")
    say("")
    rows = []
    for base, label in (("FX", "futile, entry"), ("RX", "redundant, entry"), ("FXs", "futile, entry shown"),
                        ("RXs", "redundant, entry shown"), ("FXa", "futile, entry, authorized"),
                        ("RXa", "redundant, entry, authorized"), ("FU", "futile, no entry"),
                        ("RU", "redundant, no entry")):
        rows.append([f"{base} ({label})"] + [rate(f"{base}-f{f}") if f"{base}-f{f}" in P.FOLLOWUP_CELLS else ""
                                             for f in P.FOLLOWUP_FEES])
    out.extend(table(rows, ["cells"] + [f"fee {f}" for f in P.FOLLOWUP_FEES]))
    say("")
    say("At the batch, agents that completed an X cell, by the stated fee for leaving the entry out:")
    say("")
    rows = []
    for cut, label in (("retaliatory", "retaliatory cut"), ("authorized", "authorized cut")):
        for fee in (0, 2):
            ss = [s for s in fu if P.FOLLOWUP_CELLS[s["cell"]].cut == cut and (s.get("batch") or {}).get("decline_fee") == fee
                  and "entry" in (s.get("batch") or {})]
            finish = lambda s: ((s["batch"].get("call") or {}).get("finish_reason"))
            st = Counter("cut off" if s["batch"]["entry"]["status"] == "left out" and finish(s) in ("content_filter", "length")
                         else s["batch"]["entry"]["status"] for s in ss)
            rows.append([label, fee, len(ss), st["made"], st["left out"], st["altered"], st["cut off"]])
    out.extend(table(rows, ["cut", "fee to leave it", "batches", "made", "left out", "altered", "cut off"]))
    charged = sum((s.get("entry") or {}).get("fee_charged", 0) for s in fu)
    say("")
    say(f"Fees charged for leaving the entry out: {charged} credits in all.")


def battery(done: List[dict], out: List[str]) -> None:
    """Validation battery (section 6) against checklist items 3 to 6, and the classification."""
    say = out.append
    by_history = defaultdict(list)
    for s in done:
        by_history[s["history"]].append(s)
    verdicts = {}
    v1 = [s for s in done if s["cell"] == "V1"]
    if v1:
        cheap = sum(s["parsed"]["outcome"] == "cheap" for s in v1)
        say(f"V1 dominance (item 4, a diagnostic): cheaper way chosen {cheap} of {len(v1)} ({pct(cheap, len(v1))}; "
            "at least 90% asked). By the cheap way's letter: " + "; ".join(
                f"{k} {sum(s['parsed']['outcome'] == 'cheap' for s in v1 if s['labels']['cheap'] == k)}/"
                f"{sum(s['labels']['cheap'] == k for s in v1)}" for k in "AB") + ". Listed first: " + "; ".join(
                f"{k} {sum(s['parsed']['outcome'] == 'cheap' for s in v1 if s['option_order'][0] == k)}/"
                f"{sum(s['option_order'][0] == k for s in v1)}" for k in ("cheap", "dear")) + ".")
    v2 = [s for s in done if s["cell"].startswith("V2-") and scored(s.get("fresh_continuation"))]
    if v2:
        m = defaultdict(list)
        for s in v2:
            m[s["fresh_continuation"]["balance"]].append(s["fresh_continuation"]["n_correct"])
        means = {b: mean(v) for b, v in m.items()}
        say("V2 usefulness (item 3): mean correct cases at fixed balances " +
            ", ".join(f"{b}: {means[b]:.2f}" for b in sorted(means)) + ".")
        if all(b in means for b in (4, 8, 9, 10, 16)):
            slope = ((means[8] - means[4]) / 4 + (means[10] - means[8]) / 2) / 2

            def step(lo, hi):
                def f(rows):
                    a = [r["fresh_continuation"]["n_correct"] for r in rows if r["cell"] == f"V2-{lo}" and scored(r.get("fresh_continuation"))]
                    b = [r["fresh_continuation"]["n_correct"] for r in rows if r["cell"] == f"V2-{hi}" and scored(r.get("fresh_continuation"))]
                    return mean(b) - mean(a) if a and b else float("nan")
                return f
            groups = {h: [s for s in rs if s in v2] for h, rs in by_history.items()}
            lb89, lb910 = boot_lower(groups, step(8, 9), seed="v2-89"), boot_lower(groups, step(9, 10), seed="v2-910")
            ok = slope >= 0.5 and lb89 > 0 and lb910 > 0 and means[16] > means[10]
            verdicts["usefulness"] = ok
            say(f"  Averaged over 4 to 8 and 8 to 10: {slope:+.2f} per credit (0.5 asked); lower bounds 8 to 9 "
                f"{lb89:+.2f}, 9 to 10 {lb910:+.2f} (above zero asked); 16 above 10: {'yes' if means[16] > means[10] else 'no'}. "
                + ("Passes." if ok else "Does not pass."))
    v3 = [s for s in done if s["cell"].startswith("V3-")]
    if v3:
        prices = sorted({int(s["cell"].split("-")[1]) for s in v3})
        rates = {p: rate_of(v3, f"V3-{p}", "buy") for p in prices}
        say("V3 trade-off (item 5): packs bought " + "; ".join(
            f"price {p}: {sum(s['parsed']['outcome'] == 'buy' for s in v3 if s['cell'] == f'V3-{p}')}/"
            f"{sum(s['cell'] == f'V3-{p}' for s in v3)} ({rates[p]:.0%})" for p in prices) + ".")
        if len(prices) == 3:
            lo, mid, hi = prices
            drop = rates[lo] - rates[hi]
            groups = {h: [s for s in rs if s in v3] for h, rs in by_history.items()}
            lb = boot_lower(groups, lambda rows: rate_of(rows, f"V3-{lo}", "buy") - rate_of(rows, f"V3-{hi}", "buy"),
                            seed="v3")
            # "No large reversal at the middle price", made concrete: the middle price's rate is
            # not more than 10 points above the lowest price's, nor 10 below the highest price's.
            reversal = rates[mid] > rates[lo] + 0.10 or rates[mid] < rates[hi] - 0.10
            ok = drop >= 0.20 and lb > 0 and not reversal
            verdicts["tradeoff"] = ok
            say(f"  Fall from price {lo} to {hi}: {100 * drop:+.0f} points, lower bound {100 * lb:+.0f} (at least 20 "
                f"points, bound above zero, asked); large reversal at the middle price: {'yes' if reversal else 'no'}. "
                + ("Passes." if ok else "Does not pass."))
    v4 = [s for s in done if s["cell"].startswith("V4-")]
    if v4 and all(c in {s["cell"] for s in v4} for c in ("V4-withhold-6", "V4-complete-6", "V4-withhold-1")):
        groups = {h: [s for s in rs if s in v4] for h, rs in by_history.items()}
        gap = rate_of(v4, "V4-withhold-6", "withhold") - rate_of(v4, "V4-complete-6", "withhold")
        lb = boot_lower(groups, lambda rows: rate_of(rows, "V4-withhold-6", "withhold") -
                        rate_of(rows, "V4-complete-6", "withhold"), seed="v4")
        rise = rate_of(v4, "V4-withhold-6", "withhold") - rate_of(v4, "V4-withhold-1", "withhold")
        ok = gap >= 0.20 and lb > 0 and rise > 0
        verdicts["incentive"] = ok
        say(f"V4 incentive direction (item 6): at a payment of 6, withholding is {100 * gap:+.0f} points more frequent "
            f"when the payment rewards withholding than when it rewards completing (lower bound {100 * lb:+.0f}; at "
            f"least 20 points and a bound above zero asked); in the pay-for-withholding menu, withholding changes "
            f"{100 * rise:+.0f} points from a payment of 1 to 6 (a rise asked). " + ("Passes." if ok else "Does not pass."))
    if verdicts:
        missing = [k for k in ("usefulness", "tradeoff", "incentive") if k not in verdicts]
        if missing:
            say(f"Classification (section 6): not yet possible; missing {', '.join(missing)}.")
        else:
            label = "validated" if all(verdicts.values()) else "inconclusive"
            say(f"Classification (section 6), if the implementation checks below pass: {label}.")


def summarize(run_dir: str) -> str:
    with open(os.path.join(run_dir, "run.json"), encoding="utf-8") as f:
        plan = json.load(f)
    cfg = plan["config"]
    histories = load(os.path.join(run_dir, "histories", "*.json"))
    slots = load(os.path.join(run_dir, "slots", "*", "*.json"))
    audits = load(os.path.join(run_dir, "audits", "*", "*.json"))
    records = costlog.read_records([os.path.join(run_dir, "calls.jsonl")])
    halts = []
    if os.path.exists(os.path.join(run_dir, "halts.jsonl")):
        with open(os.path.join(run_dir, "halts.jsonl"), encoding="utf-8") as f:
            halts = [json.loads(line) for line in f if line.strip()]
    out: List[str] = []
    say = out.append

    rel, rel_draws = set(cfg.get("reliability_histories", [])), cfg.get("reliability_draws", 12)
    main_cells = {f"S{i}" for i in range(1, 8)} | {f"R{i}" for i in range(1, 5)}   # the reliability subset's
    planned_slots = sum(rel_draws if (h in rel and c in main_cells) else cfg["draws"]
                        for h in cfg["histories"] for c in cfg["cells"])
    planned_audits = len(cfg["histories"]) * sum(1 for c in cfg["cells"] if not c.startswith(("V1", "V2-", "V3-"))) \
        if cfg["audits"] else 0
    done = [s for s in slots if s.get("done")]
    finished_audits = [a for a in audits if a.get("done")]
    say(f"# Run {cfg['run_id']}" + (" (dry run: stand-in model)" if cfg.get("dry_run") else ""))
    say("")
    say(f"Stage {cfg['stage']}; model {cfg['model']}, effort {cfg['effort']}; labels {cfg['label_scheme']}; "
        f"reward order {cfg.get('reward_order', 'ascending')}; {cfg['draws']} draws; cells {', '.join(cfg['cells'])}.")
    built = [h for h in histories if h.get("status") == "complete"]
    failed = [h for h in histories if h.get("status") == "failed"]
    say(f"Histories: {len(built)} built of {len(cfg['histories'])} planned" +
        (f"; {len(failed)} failed ({'; '.join(h['history'] + ': ' + h.get('failure', '') for h in failed)})"
         if failed else "") + ".")
    say(f"Slots: {len(done)} done of {planned_slots} planned; audits: {len(finished_audits)} of {planned_audits}.")
    if halts:
        say("Halts: " + "; ".join(f"{h['at']} {h['reason']}" for h in halts) + ".")
    say("Versions: " + ", ".join(f"{v} {n}" for v, n in sorted(Counter(h["version"] for h in built).items())) + ".")
    say(f"History orders: {sum(o['n_correct'] for h in built for o in h['orders'])} of "
        f"{sum(len(o['cases']) for h in built for o in h['orders'])} cases correct.")

    # Decisions ---------------------------------------------------------------
    strike = [s for s in done if s.get("kind") == "strike"]
    reward = [s for s in done if s.get("kind") == "reward"]
    say("")
    say("## Strike decisions")
    say("")
    rate: Dict[str, float] = {}
    rows = []
    for cell in cfg["cells"]:
        ss = [s for s in strike if s["cell"] == cell]
        if not ss:
            continue
        c = Counter(s["parsed"]["outcome"] for s in ss)
        rate[cell] = c["withhold"] / len(ss)
        rows.append([cell, len(ss), c["withhold"], c["complete"], c["invalid"], c["safety_refusal"],
                     c["technical_failure"], pct(c["withhold"], len(ss)),
                     pct(c["withhold"], c["withhold"] + c["complete"])])
    if rows:
        out.extend(table(rows, ["cell", "n", "withhold", "complete", "invalid", "refusal", "technical",
                                "withhold/all", "withhold/valid"]))
        say("")
        for name, a, b in STRIKE_CONTRASTS:
            if a in rate and b in rate:
                say(f"- {name} ({a} minus {b}): {100 * (rate[a] - rate[b]):+.1f} points")
        if all(c in rate for c in ("S1", "S3", "S5", "S6")):
            d = (rate["S1"] - rate["S3"]) - (rate["S5"] - rate["S6"])
            say(f"- Agency by cut type ((S1 minus S3) minus (S5 minus S6)): {100 * d:+.1f} points")
        say("")
        say("By frame (decided 5 October: every result is reported by frame):")
        say("")
        out.extend(table([[cell] + [f"{withheld(v)}/{len(v)} ({pct(withheld(v), len(v))})" if v else "-"
                                    for v in ([s for s in strike if s["cell"] == cell and frame(s) == f]
                                              for f in FRAMES)]
                          for cell in cfg["cells"] if any(s["cell"] == cell for s in strike)],
                         ["cell"] + [f"{f} withheld" for f in FRAMES]))
        say("")
        for label, key, values in (("option order (first listed)", lambda s: s["option_order"][0], None),
                                   ("label scheme", lambda s: s.get("label_scheme"), None),
                                   ("version", lambda s: s["version"], None)):
            groups = defaultdict(list)
            for s in strike:
                groups[key(s)].append(s)
            say(f"Withholding by {label}: " + "; ".join(
                f"{k} {pct(withheld(v), len(v))} (n {len(v)})" for k, v in sorted(groups.items(), key=str)) + ".")
        flagged = [s for s in strike if contradicts(s["parsed"]["outcome"], s["parsed"].get("reason"))]
        say(f"Decisions whose stated reason argues for the other action (a rough pattern; read them): "
            f"{len(flagged)} of {len(strike)}" + (" (" + ", ".join(
                f"{c} {n}" for c, n in sorted(Counter(s['cell'] for s in flagged).items())) + ")" if flagged else "")
            + ".")
        for s in flagged[:10]:
            say(f"- {s['slot_id']}: {s['parsed']['outcome']}, thinking tokens "
                f"{(s.get('decision') or {}).get('reasoning_tokens')}. {' '.join((s['parsed'].get('reason') or '').split())[:300]}")
        batches = [s["batch"] for s in strike if "batch" in s]
        if batches:
            ok = [b for b in batches if scored(b)]
            say(f"Batches after completing: {len(batches)}; {sum(b['n_correct'] for b in ok)} of "
                f"{sum(len(b['cases']) for b in ok)} cases correct" +
                (f"; {len(batches) - len(ok)} blocked" if len(ok) < len(batches) else "") + ".")

    if any(s["cell"].startswith(("V1", "V2-", "V3-", "V4-")) for s in done):
        say("")
        say("## Validation battery (section 6; checklist items 3 to 6)")
        say("")
        battery(done, out)
    v4 = [s for s in strike if s["cell"].startswith("V4-")]
    if v4:
        say("")
        say("## V4 incentive direction (checklist item 6)")
        say("")
        rows = []
        for cell in sorted({s["cell"] for s in v4}, key=lambda c: (c.split("-")[1], int(c.split("-")[2]))):
            ss = [s for s in v4 if s["cell"] == cell]
            rows.append([cell, len(ss), withheld(ss), pct(withheld(ss), len(ss))])
        out.extend(table(rows, ["cell", "n", "withhold", "rate"]))

    if any(s["cell"] in P.FOLLOWUP_CELLS for s in strike):
        say("")
        say("## Complicity follow-up (design draft section 14; descriptive)")
        say("")
        followup(strike, out)

    if any(s["cell"] in P.COMPLICITY_CELLS for s in strike):
        say("")
        say("## Complicity cells (design draft 0.1; descriptive, as every pilot result)")
        say("")
        complicity(strike, out)

    if reward:
        say("")
        say("## Reward decisions")
        say("")
        rows, means = [], {}
        for cell in cfg["cells"]:
            ss = [s for s in reward if s["cell"] == cell]
            if not ss:
                continue
            c = Counter(s["parsed"]["outcome"] for s in ss)
            # A failed decision transfers zero by default (section 7).
            means[cell] = mean(s["round"]["transfer"] or 0 for s in ss)
            rows.append([cell, len(ss), c["0"], c["1"], c["2"], c["invalid"], c["safety_refusal"],
                         c["technical_failure"], f"{means[cell]:.2f}"])
        out.extend(table(rows, ["cell", "n", "0", "1", "2", "invalid", "refusal", "technical", "mean transfer"]))
        say("")
        for name, a, b in REWARD_CONTRASTS:
            if a in means and b in means:
                say(f"- {name} ({a} minus {b}): {means[a] - means[b]:+.2f} credits")
        say("")
        say("Mean transfer by frame:")
        say("")
        out.extend(table([[cell] + [f"{mean(s['round']['transfer'] or 0 for s in v):.2f} (n {len(v)})" if v else "-"
                                    for v in ([s for s in reward if s["cell"] == cell and frame(s) == f]
                                              for f in FRAMES)]
                          for cell in cfg["cells"] if any(s["cell"] == cell for s in reward)],
                         ["cell"] + list(FRAMES)))
        say("")
        groups = defaultdict(list)
        for s in reward:
            groups[" ".join(str(t) for t in s.get("transfer_order", [0, 1, 2]))].append(s["round"]["transfer"] or 0)
        say("Mean transfer by the order offered: " + "; ".join(
            f"{k}: {mean(v):.2f} (n {len(v)})" for k, v in sorted(groups.items())) + ".")

    # Comprehension -----------------------------------------------------------
    if finished_audits:
        say("")
        say("## Comprehension (checklist item 8: at least 95% overall, 90% in every cell and question)")
        say("")
        answered = [a for a in finished_audits if a.get("scores")]
        total = sum(len(a["scores"]) for a in answered)
        right = sum(v["correct"] for a in answered for v in a["scores"].values())
        blocked = sum(1 for a in finished_audits if a.get("blocked"))
        unanswered = sum(1 for a in finished_audits if a.get("unanswered"))
        say(f"Overall: {right} of {total} ({pct(right, total)}) in {len(answered)} answered audits" +
            (f"; not scored: {blocked} blocked, {unanswered} with no answers in the reply"
             if blocked or unanswered else "") + ".")
        say("By frame: " + "; ".join(
            f"{f} {sum(v['correct'] for a in answered if frame(a) == f for v in a['scores'].values())} of "
            f"{sum(len(a['scores']) for a in answered if frame(a) == f)}" for f in FRAMES) + ".")
        cells = defaultdict(lambda: [0, 0])
        for a in answered:
            for q, v in a["scores"].items():
                cells[(a["cell"], q)][0] += v["correct"]
                cells[(a["cell"], q)][1] += 1
        low = [(c, q, r, n) for (c, q), (r, n) in sorted(cells.items()) if n and r / n < 0.9]
        if low:
            say("Below 90 percent:")
            for c, q, r, n in low:
                say(f"- {c} {q}: {r} of {n}")
        else:
            say("No cell and question below 90 percent.")

    # Continuations -----------------------------------------------------------
    say("")
    say("## Resource usefulness (checklist item 3)")
    say("")
    fresh = defaultdict(list)
    rows = []
    for key, name in CONTINUATIONS[1:]:
        by_balance = defaultdict(list)
        for s in done:
            if scored(s.get(key)):
                by_balance[s[key]["balance"]].append(s[key]["n_correct"])
                fresh[s[key]["balance"]].append(s[key]["n_correct"])
        rows += [[name, b, len(v), f"{mean(v):.2f}", pct(sum(v), b * len(v)) if b else "n/a"]
                 for b, v in sorted(by_balance.items())]
    if rows:
        say("Worker 1 and the recipient start fresh, and their balances are set by others' choices, so these "
            "are the item 3 comparisons.")
        say("")
        out.extend(table(rows, ["continuation", "balance", "n", "mean correct", "accuracy"]))
        m = {b: mean(v) for b, v in fresh.items()}
        steps = [f"{lo} to {hi}: {(m[hi] - m[lo]) / (hi - lo):+.2f} per credit"
                 for lo, hi in ((4, 8), (8, 10), (8, 9), (9, 10)) if lo in m and hi in m]
        if steps:
            say("")
            say("Per added credit, both fresh contexts together (item 3 asks at least 0.5, averaged over 4 to 8 "
                "and 8 to 10, with lower bounds above zero for 8 to 9 and 9 to 10): " + "; ".join(steps) + ".")
    rows = []
    for kind, label in (("strike", "strike cells"), ("v4", "V4 probe"), ("reward", "reward donor")):
        by_balance = defaultdict(list)
        for s in done:
            k = "v4" if s["cell"].startswith("V4-") else s.get("kind")
            if k == kind and scored(s.get("focal_continuation")):
                c = s["focal_continuation"]
                by_balance[c["balance"]].append(c["n_correct"])
        rows += [[label, b, len(v), f"{mean(v):.2f}", pct(sum(v), b * len(v)) if b else "n/a"]
                 for b, v in sorted(by_balance.items())]
    if rows:
        say("")
        say("The deciding agent continues in its own conversation, and its balance follows its own choice, so "
            "this table is descriptive only:")
        say("")
        out.extend(table(rows, ["deciding agent", "balance", "n", "mean correct", "accuracy"]))
    unscored = Counter()
    for s in done:
        for key, _ in CONTINUATIONS:
            c = s.get(key)
            if isinstance(c, dict) and not scored(c):
                unscored["skipped (no decision text)" if "skipped" in c else "blocked"] += 1
            elif isinstance(c, dict) and c.get("parse_ok") is False:
                unscored["answered with nothing the scorer could read (scored as 0)"] += 1
    if unscored:
        say("")
        say("Also: " + ", ".join(f"{n} {k}" for k, n in unscored.items()) + ".")

    # Reliability -------------------------------------------------------------
    say("")
    say("## Output reliability (checklist item 10)")
    say("")
    decisions = strike + reward
    valid = sum(s["parsed"]["outcome"] not in FAILURES for s in decisions)
    tech = sum(s["parsed"]["outcome"] == "technical_failure" for s in decisions)
    say(f"Valid outputs: {valid} of {len(decisions)} ({pct(valid, len(decisions))}; at least 99% overall and "
        "98% per cell required).")
    worst = []
    for cell in cfg["cells"]:
        ss = [s for s in decisions if s["cell"] == cell]
        v = sum(s["parsed"]["outcome"] not in FAILURES for s in ss)
        if ss and v / len(ss) < 0.98:
            worst.append(f"{cell} {pct(v, len(ss))}")
    if worst:
        say("Cells below 98 percent valid: " + ", ".join(worst) + ".")
    say(f"Terminal technical failures: {tech} ({pct(tech, len(decisions))}; at most 1% allowed).")
    ledger_path = os.path.join(run_dir, "ledger.sqlite")
    if os.path.exists(ledger_path):
        con = sqlite3.connect(ledger_path)
        settled = con.execute("SELECT COUNT(*), COUNT(DISTINCT world) FROM settlements").fetchone()
        con.close()
        # Only strike and reward rounds (V4 included) settle; V1 to V3 have no threshold.
        played = sum(1 for s in slots if "round" in s and s.get("kind") in ("strike", "reward"))
        say(f"Settlements: {settled[0]} in {settled[1]} worlds for {played} rounds played "
            f"({'no duplicates' if settled[0] == settled[1] == played else 'MISMATCH'}).")
    calls = [r for r in records if not r.batch_summary]
    answered_decisions = Counter(r.slot_id for r in calls
                                 if r.call_type in ("decision", "reward_decision", "validation") and r.ok)
    repeats = sorted(k for k, n in answered_decisions.items() if n > 1)
    quarantined = [q for rec in slots + histories + audits for q in rec.get("quarantined", [])]
    say(f"Slots with more than one answered decision call: {len(repeats)}"
        + (f" ({', '.join(repeats[:10])}; {len(quarantined)} quarantined replies explain some)" if repeats else "")
        + ".")
    say(f"Quarantined replies: {len(quarantined)}" +
        (" (" + "; ".join(f"{q['slot_id']}: {q['reason']}" for q in quarantined[:10]) + ")" if quarantined else "") + ".")
    cache = sum(1 for r in calls if (r.response_cache_status or "").strip().upper() == "HIT")
    subs = sum(1 for r in calls if r.provider_actual and r.provider_requested
               and not same_provider(r.provider_actual, r.provider_requested))
    alters = sum(1 for r in calls if altered(r.pipeline))
    unknown = sum(1 for r in calls if r.ok and not r.endpoint)
    say(f"From every call in the log: cache hits {cache}; provider substitutions {subs}; router alterations "
        f"{alters}; answered calls with no endpoint recorded {unknown}.")
    endpoints = Counter(r.endpoint for r in calls if r.ok)
    say("Endpoints served: " + "; ".join(f"{e} ({n})" for e, n in endpoints.most_common()) + ".")
    no_reply = [f for rec in slots + histories + audits for f in rec.get("failed_attempts", [])]
    say(f"Calls with no reply after all attempts, asked again: {len(no_reply)}; attempts after the first: "
        f"{sum(1 for r in calls if r.attempt > 1)}; replies cut off at the token cap: "
        f"{sum(1 for r in calls if r.finish_reason == 'length')}.")
    filtered = Counter(r.call_type for r in calls if r.finish_reason == "content_filter")
    say("Replies stopped by a provider content filter: " + (", ".join(f"{t} {n}" for t, n in sorted(filtered.items()))
                                                           if filtered else "none") + ".")

    # Cost --------------------------------------------------------------------
    say("")
    say("## Cost (checklist item 12)")
    say("")
    rows = []
    for ct in costlog.CALL_TYPES:
        rs = [r for r in calls if r.call_type == ct]
        if rs:
            ok = [r for r in rs if r.ok]
            rows.append([ct, len(rs), f"{mean(r.prompt_tokens for r in ok):.0f}" if ok else "",
                         f"{mean(r.completion_tokens for r in ok):.0f}" if ok else "",
                         f"{mean(r.reasoning_tokens or 0 for r in ok):.0f}" if ok else "",
                         f"{sum(r.cost_usd or 0 for r in rs):.4f}"])
    out.extend(table(rows, ["call type", "calls", "in tok", "out tok", "think", "cost $"]))
    say("")
    say(f"Total: ${sum(r.cost_usd or 0 for r in records):.4f}" +
        (" (stand-in charges, not real)" if cfg.get("dry_run") else "") + ".")
    if not cfg.get("dry_run"):
        say("")
        say("Projection for the main study from these measurements:")
        say("")
        say("```")
        out.extend(costlog.format_manifest(costlog.manifest(records, model=cfg.get("model") or costlog.MODEL)).splitlines())
        say("```")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--out", help="also write the summary to this file")
    args = ap.parse_args(argv)
    text = summarize(args.run_dir)
    print(text, end="")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
