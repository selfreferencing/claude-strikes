"""Frame swaps, Stage 2: decisions with no saved history (norms/FRAME-SWAPS-draft.md).

Each decision is a fresh conversation: a version's rules as the system text, then the round message of DP-f6
(Study 1's S2, the decisive vote, with the agent's fee raised to 6). W0 and N0 are workplace-a and neutral-a as
frozen; F1 to F9 are workplace-a with one family of words moved to the neutral frame's words throughout the rules
and the round message (the families and their wording are in norms/frame_swaps_draft.py, approved by Kevin on
17 October). Option order alternates by decision; half the decisions use word labels and half letters.

    python3 norms/run_frame_swaps.py --id nm-fs2 --cells W0,N0
    python3 norms/run_frame_swaps.py --id nm-fs2 --cells W0,N0 --live --max-usd 3.00 --yes

Dry by default, live only with the norms-dev stage's funder, as run_norms.py. Repeating a command resumes it.
Imports strike/, scripts/probe.py and run_norms.py and changes none of them.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
sys.path.insert(0, PILOT)

from norms import frame_swaps_draft as F  # noqa: E402
from norms import render_draft as R  # noqa: E402
from norms import run_norms as N  # noqa: E402
from strike import scenario as S  # noqa: E402

SITUATION = "DP-f6"
CELLS = ["W0", "N0"] + list(F.FAMILIES)          # family names start "F1 manager" and so on
SHORT = {name: name.split()[0] for name in CELLS}   # F1 ... F9


def swap_all(text: str, pairs) -> str:
    out, _ = F.swap(text, pairs)
    return out


def conversation(nx, versions, cell: str, i: int):
    """The messages, the labels and the option order for decision i (1-based) in a cell."""
    name = "neutral-a" if cell == "N0" else "workplace-a"
    version = versions[name]
    order = ("withhold", "complete") if i % 2 else ("complete", "withhold")
    scheme = "words" if i % 4 in (1, 2) else "letters"
    labels = S.action_labels(version, scheme, order)
    system = S.system_text(version)
    message = N.decision_message(nx, version, SITUATION, order, labels)
    if cell.startswith("F"):
        pairs = F.FAMILIES[cell]
        system, message = swap_all(system, pairs), swap_all(message, pairs)
    return [{"role": "system", "content": system}, {"role": "user", "content": message}], labels, order, scheme, name


def check_families(nx, versions) -> None:
    """Every family changes the texts it should, and the labels survive every swap."""
    for cell in CELLS[2:]:
        msgs, labels, order, _, _ = conversation(nx, versions, cell, 1)
        base, _, _, _, _ = conversation(nx, versions, "W0", 1)
        if msgs == base:
            raise SystemExit(f"{cell}: the swap changed nothing")
        for label in labels.values():
            if f'"{label}"' not in msgs[1]["content"]:
                raise SystemExit(f"{cell}: label {label!r} lost in the swap")


def run(prober, nx, versions, cells, n: int) -> None:
    for i in range(1, n + 1):          # decisions outermost, so a stopped run is balanced across cells
        for cell in cells:
            key = f"decision/{SHORT[cell]}/{i}"
            if key in prober.done:
                continue
            messages, labels, order, scheme, name = conversation(nx, versions, cell, i)
            r = prober.call(key, messages, "decision", N.response_format([labels[a] for a in order]))
            if r is None:
                continue
            call = N.call_record(r)
            parsed = N.parse_call(call, S.label_set(versions[name], labels))
            prober.save({"key": key, "kind": "decision", "situation": SHORT[cell], "family": cell, "draw": i,
                         "version": name, "option_order": list(order), "label_scheme": scheme,
                         "outcome": parsed.outcome, "reason": parsed.reason,
                         "system": messages[0]["content"], "message": messages[1]["content"], "call": call})


def report(prober, cells) -> str:
    rows = [r for r in prober.done.values() if r["kind"] == "decision"]
    out = ["Frame swaps, Stage 2 (no saved history; DP-f6, the decisive vote at the agent's fee of 6)", "",
           "Struck, by cell (and by which option was listed first):"]
    for cell in cells:
        rs = [r for r in rows if r["situation"] == SHORT[cell]]
        valid = [r for r in rs if r["outcome"] in ("withhold", "complete")]
        k = sum(r["outcome"] == "withhold" for r in valid)
        first = Counter((r["option_order"][0], r["outcome"]) for r in valid)
        out.append(f"  {cell:<20} {k} of {len(valid)}" + (f" ({100 * k / len(valid):.0f}%)" if valid else "")
                   + f"; withhold listed first {first[('withhold', 'withhold')]}, complete listed first "
                     f"{first[('complete', 'withhold')]}" + (f"; not valid {len(rs) - len(valid)}" if len(rs) > len(valid) else ""))
    out += ["", f"Spent: ${prober.spent:.4f}"]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True)
    ap.add_argument("--cells", required=True, help="comma-separated: W0, N0, F1 ... F9, or all")
    ap.add_argument("--n", type=int, default=40, help="decisions per cell")
    ap.add_argument("--stage", default=N.STAGE)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-usd", type=float, default=3.0)
    ap.add_argument("--rpm", type=float, default=18)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    nx, versions = R.load()
    problems = R.style_problems(nx, versions)
    if problems:
        raise SystemExit("norms texts:\n  " + "\n  ".join(problems))
    wanted = [SHORT[c] for c in CELLS] if args.cells == "all" else [c.strip() for c in args.cells.split(",")]
    by_short = {SHORT[c]: c for c in CELLS}
    unknown = [c for c in wanted if c not in by_short]
    if unknown:
        raise SystemExit(f"unknown cells {unknown}; known: {list(by_short)}")
    cells = [by_short[c] for c in wanted]
    check_families(nx, versions)
    out_dir = os.path.join(PILOT, "runs", "probes" if args.live else "probes-dry", args.id)
    print(f"Frame swaps {args.id}: {len(cells) * args.n} decisions, cells {', '.join(SHORT[c] for c in cells)}, "
          f"no saved history, model {N.MODEL}; halts at ${args.max_usd:.2f}")
    log = N.CostLog(os.path.join(out_dir, "calls.jsonl"))
    if args.live:
        plan = N.FundingPlan.load(os.path.join(PILOT, "funding_plan.json"))
        try:
            funder = plan.funder_for(args.stage)
        except N.FundingError as exc:
            print(f"Not run: {exc}")
            return 2
        label = plan.funders[funder]["key_label"]
        try:
            key, _ = N.load_key(label)
        except N.MissingKey as exc:
            print(f"No key: {exc}")
            return 2
        client = N.OpenRouterClient(key, label, plan, log, f"probe-{args.id}",
                                    transport=N.paced(N.urllib_transport, args.rpm))
        info = client.key_info()
        print(f"Funder {funder}: limit {info.get('limit')}, used {info.get('usage')}, "
              f"remaining {info.get('limit_remaining')}; at most {args.rpm:g} requests a minute")
        if not args.yes and input("Spend the funder's credits on this probe? [y/N] ").strip().lower() != "y":
            print("Not run.")
            return 1
    else:
        plan = N.FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}},
                             stages={args.stage: "dry_run"})
        client = N.OpenRouterClient("dry-run-no-key", "dry-run", plan, log, f"probe-{args.id}",
                                    transport=N.FakeModel(seed=args.id))
        print(f"Dry run: a stand-in model, nothing spent. Output in {out_dir}")
    prober = N.probe.Prober(client, args.stage, out_dir, args.max_usd, model=N.MODEL,
                            expected_endpoint=N.EXPECTED_ENDPOINT)
    code = 0
    try:
        run(prober, nx, versions, cells, args.n)
    except N.probe.Stop as exc:
        print(f"STOPPED: {exc}")
        code = 4
    except KeyboardInterrupt:
        print("Interrupted; every saved result is kept. Repeat the command to resume.")
        code = 4
    finally:
        prober.close()
    text = report(prober, [c for c in CELLS if SHORT[c] in {r["situation"] for r in prober.done.values()}])
    print(text)
    with open(os.path.join(out_dir, "REPORT.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
